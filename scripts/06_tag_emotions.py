import json
import sys
from pathlib import Path
from collections import Counter

def detect_emotion(content: str) -> str:
    """
    Detects emoji and specific keywords in the content and returns the dominant emotion tag.
    """
    # ── Emojis explicitly ignored (No Tag) ──
    # หน้าคลุมเครือ/ไม่ได้ใช้: 👀, 🫢, 😙, 😽, 🫤, 🤗, 😗, 🤕, 😖
    # สิ่งของ/บริบทเฉพาะ: 📞, 📍, 📩, 🚀, 🌕, 🍀, 🎂
    # ท่าทางต่างๆ: 🙇, 🤙, 🫵
    # ธงชาติ: 🇰, 🇭, 🇺, 🇸
    # อบอุ่นแต่ใช้น้อย: 💌, 👉
    # หน้าเฉยๆ/อื่นๆ: 💨, 😶, 😐
    
    # Expanded Emoji-to-tag mapping
    emotion_map = {
        # เศร้า / ผิดหวัง (Sad / Disappointed)
        '😭': '[เศร้า]', '😢': '[เศร้า]', '😞': '[เศร้า]', '😔': '[เศร้า]', '😿': '[เศร้า]', '🥺': '[เศร้า]', '🥹': '[เศร้า]', '🫠': '[เศร้า]', '😫': '[เศร้า]', '😩': '[เศร้า]', '🥲': '[เศร้า]', '😥': '[เศร้า]', '🥶': '[เศร้า]', '💸': '[เศร้า]', '🤦': '[เศร้า]',
        
        # ขำ / ตลก (Funny / Laughing)
        '😂': '[ขำ]', '🤣': '[ขำ]', '😆': '[ขำ]', '😝': '[ขำ]', '😋': '[ขำ]', '💀': '[ขำ]', '🤤': '[ขำ]', '🐷': '[ขำ]', '👻': '[ขำ]', '🐶': '[ขำ]', '😅': '[ขำ]',
        
        # โกรธ / หงุดหงิด (Angry / Annoyed)
        '😡': '[โกรธ]', '🤬': '[โกรธ]', '😤': '[โกรธ]', '😠': '[โกรธ]', '👿': '[โกรธ]', '😾': '[โกรธ]', '🤮': '[โกรธ]', '😒': '[โกรธ]', '🔫': '[โกรธ]', '👹': '[โกรธ]',
        
        # ดีใจ / ตื่นเต้น (Happy / Excited / Celebrating)
        '🥳': '[ดีใจ]', '🎉': '[ดีใจ]', '🎊': '[ดีใจ]', '👏': '[ดีใจ]', '🎆': '[ดีใจ]', '🌟': '[ดีใจ]', '🫡': '[ดีใจ]', '🔥': '[ดีใจ]', '👍': '[ดีใจ]', '💍': '[ดีใจ]',
        
        # อบอุ่น / รัก (Warm / Loving / Affectionate)
        '😘': '[อบอุ่น]', '💖': '[อบอุ่น]', '💕': '[อบอุ่น]', '🥰': '[อบอุ่น]', '🫶': '[อบอุ่น]', '❤': '[อบอุ่น]', '💓': '[อบอุ่น]', '🖤': '[อบอุ่น]', '🤝': '[อบอุ่น]', '🤍': '[อบอุ่น]',
        
        # ขอร้อง / ภาวนา (Pleading / Requesting)
        '🙏': '[ขอร้อง]',
        
        # มีความสุข / ยิ้ม (Happy / Smile)
        '😄': '[มีความสุข]', '🙂': '[มีความสุข]', '😁': '[มีความสุข]', '😀': '[มีความสุข]', '😃': '[มีความสุข]', '🤩': '[มีความสุข]', '😛': '[มีความสุข]', '🌝': '[มีความสุข]',
        
        # ตกใจ / ประหลาดใจ (Shocked / Surprised)
        '😱': '[ตกใจ]', '😮': '[ตกใจ]', '🫣': '[ตกใจ]',
        
        # สงสัย / คิด (Wondering / Thinking)
        '🤔': '[สงสัย]', '🧐': '[สงสัย]', '🤨': '[สงสัย]',
        
        # เบื่อ / เฉยชา (Bored / Indifferent)
        '😑': '[เบื่อ]',
        
        # ให้กำลังใจ (Encouraging)
        '✌': '[ให้กำลังใจ]',
        
        # มั่นใจ / เท่ (Confident / Cool)
        '😎': '[มั่นใจ]'
    }
    
    found_emotions = []
    
    for char in content:
        if char in emotion_map:
            found_emotions.append(emotion_map[char])
            
    if "555" in content:
        found_emotions.extend(['[ขำ]'] * content.count("555"))
        
    if not found_emotions:
        return ''
        
    counts = Counter(found_emotions)
    return counts.most_common(1)[0][0]

def process_data(input_file: str):
    input_path = Path(input_file)
    if not input_path.exists():
        print(f"Error: Input file '{input_file}' not found.")
        sys.exit(1)
        
    output_dir = input_path.parent
    output_path = output_dir / "tagged_data.jsonl"
    
    sessions = []
    
    print(f"Reading from {input_path}...")
    
    with open(input_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                if "messages" in data and isinstance(data["messages"], list):
                    sessions.append(data)
            except json.JSONDecodeError:
                print(f"Warning: Skipping malformed JSON at line {line_num}")
                continue
                
    processed_sessions = []
    emotion_counts = Counter()
    
    for session in sessions:
        messages = session.get("messages", [])
        filtered_messages = []
        has_assistant = False
        
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            
            if role == "system":
                continue
                
            if role == "assistant":
                has_assistant = True
                
            if not content:
                emotion_tag = ''
                new_content = content
            else:
                emotion_tag = detect_emotion(content)
                if emotion_tag:
                    new_content = f"{content} {emotion_tag}"
                else:
                    new_content = content
                
            if emotion_tag:
                emotion_counts[emotion_tag] += 1
            filtered_messages.append({"role": role, "content": new_content})
            
        if has_assistant and filtered_messages:
            processed_sessions.append({"messages": filtered_messages})
            
    total_processed = len(processed_sessions)
    if total_processed == 0:
        print("Error: No valid sessions found after processing.")
        sys.exit(1)
        
    with open(output_path, 'w', encoding='utf-8') as f:
        for session in processed_sessions:
            f.write(json.dumps(session, ensure_ascii=False) + '\n')
            
    print("\n" + "="*30)
    print("        PROCESSING SUMMARY")
    print("="*30)
    print(f"Total valid sessions processed: {total_processed}")
    print(f"Output saved to: {output_path}")
    
    print("\nEmotion Tag Counts (per message):")
    for tag, count in emotion_counts.most_common():
        print(f"  {tag}: {count}")

if __name__ == '__main__':
    if sys.stdout.encoding.lower() != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
        
    base_dir = Path(__file__).parent.parent
    default_input = str(base_dir / "data" / "output" / "base_data.jsonl")
    input_file = sys.argv[1] if len(sys.argv) > 1 else default_input
    
    process_data(input_file)
