import json
import random
import sys
from pathlib import Path
from collections import Counter

def detect_emotion(content: str) -> str:
    """
    Detects emoji and specific keywords ("555") in the content and returns the dominant emotion tag.
    """
    # Emoji-to-tag mapping
    emotion_map = {
        '😭': '[เศร้า]', '😢': '[เศร้า]', '😞': '[เศร้า]', '😔': '[เศร้า]', '😿': '[เศร้า]', '🥺': '[เศร้า]',
        '😂': '[ขำ]', '🤣': '[ขำ]', 
        '😡': '[โกรธ]', '🤬': '[โกรธ]', '😤': '[โกรธ]',
        '🥳': '[ดีใจ]', '🎉': '[ดีใจ]', '🎊': '[ดีใจ]', '👏': '[ดีใจ]', '🎆': '[ดีใจ]', '🌟': '[ดีใจ]',
        '😘': '[อบอุ่น]', '❤️': '[อบอุ่น]', '💖': '[อบอุ่น]', '💕': '[อบอุ่น]', '💗': '[อบอุ่น]',
        '🙏': '[ขอร้อง]',
        '😄': '[มีความสุข]', '😊': '[มีความสุข]', '🙂': '[มีความสุข]', '😁': '[มีความสุข]'
    }
    
    found_emotions = []
    
    # Check each character for mapped emojis
    for char in content:
        if char in emotion_map:
            found_emotions.append(emotion_map[char])
            
    # Check for "555" occurrences (includes "5555" as it will match "555")
    if "555" in content:
        # Add as many times as "555" appears to weight it appropriately
        found_emotions.extend(['[ขำ]'] * content.count("555"))
        
    # If no emoji/keyword found, default to [neutral]
    if not found_emotions:
        return '[neutral]'
        
    # Get the most frequent emotion type
    counts = Counter(found_emotions)
    dominant_emotion = counts.most_common(1)[0][0]
    return dominant_emotion

def process_data(input_file: str):
    input_path = Path(input_file)
    if not input_path.exists():
        print(f"Error: Input file '{input_file}' not found.")
        sys.exit(1)
        
    output_dir = input_path.parent
    train_path = output_dir / "train.jsonl"
    val_path = output_dir / "val.jsonl"
    
    sessions = []
    
    print(f"Reading from {input_path}...")
    
    # Read and parse JSONL
    with open(input_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                # Only keep lines with a "messages" list
                if "messages" in data and isinstance(data["messages"], list):
                    sessions.append(data)
            except json.JSONDecodeError:
                print(f"Warning: Skipping malformed JSON at line {line_num}")
                continue
                
    # Process sessions
    processed_sessions = []
    emotion_counts = Counter()
    
    for session in sessions:
        messages = session.get("messages", [])
        
        filtered_messages = []
        has_assistant = False
        
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            
            # Task 1: Remove system prompt
            if role == "system":
                continue
                
            if role == "assistant":
                has_assistant = True
                
            # Handle edge case: empty message content
            if not content:
                emotion_tag = '[neutral]'
                new_content = emotion_tag
            else:
                # Task 2: Add emotion tags from emoji
                emotion_tag = detect_emotion(content)
                new_content = f"{content} {emotion_tag}"
                
            emotion_counts[emotion_tag] += 1
            
            filtered_messages.append({
                "role": role,
                "content": new_content
            })
            
        # Handle edge case: keep only sessions with an assistant turn and at least one message
        if has_assistant and filtered_messages:
            processed_sessions.append({"messages": filtered_messages})
            
    # Task 3: Train/Validation split
    # Shuffle with random seed 42 before splitting
    random.seed(42)
    random.shuffle(processed_sessions)
    
    total_processed = len(processed_sessions)
    if total_processed == 0:
        print("Error: No valid sessions found after processing.")
        sys.exit(1)
        
    # Split 95% train / 5% validation
    train_size = int(0.95 * total_processed)
    train_sessions = processed_sessions[:train_size]
    val_sessions = processed_sessions[train_size:]
    
    # Output train.jsonl and val.jsonl (ensure_ascii=False to preserve Thai/Emoji)
    with open(train_path, 'w', encoding='utf-8') as f:
        for session in train_sessions:
            f.write(json.dumps(session, ensure_ascii=False) + '\n')
            
    with open(val_path, 'w', encoding='utf-8') as f:
        for session in val_sessions:
            f.write(json.dumps(session, ensure_ascii=False) + '\n')
            
    # Task 4: Print summary
    print("\n" + "="*30)
    print("        PROCESSING SUMMARY")
    print("="*30)
    print(f"Total valid sessions processed: {total_processed}")
    print(f"Train sessions (95%):           {len(train_sessions)}")
    print(f"Validation sessions (5%):       {len(val_sessions)}")
    
    print("\nEmotion Tag Counts (per message):")
    # Show counts sorted by frequency
    for tag, count in emotion_counts.most_common():
        print(f"  {tag}: {count}")
        
    print("\nSample Processed Sessions (first 3):")
    for i, session in enumerate(processed_sessions[:3]):
        print(f"\n--- Sample {i+1} ---")
        print(json.dumps(session, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    # Ensure stdout uses utf-8 to prevent UnicodeEncodeError in Windows terminals
    if sys.stdout.encoding.lower() != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
        
    # Default path if none provided (relative to project root)
    default_input = "data/output/training_data.jsonl"
    
    # Allow passing file path as argument
    input_file = sys.argv[1] if len(sys.argv) > 1 else default_input
    
    process_data(input_file)
