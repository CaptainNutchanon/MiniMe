import json
import random
import sys
from pathlib import Path

def split_data(input_file: str):
    input_path = Path(input_file)
    if not input_path.exists():
        print(f"Error: Input file '{input_file}' not found.")
        sys.exit(1)
        
    output_dir = input_path.parent
    train_path = output_dir / "train.jsonl"
    val_path = output_dir / "val.jsonl"
    
    sessions = []
    
    print(f"Reading from {input_path}...")
    with open(input_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                sessions.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"Warning: Skipping malformed JSON at line {line_num}")
                continue
                
    random.seed(42)
    random.shuffle(sessions)
    
    total_sessions = len(sessions)
    if total_sessions == 0:
        print("Error: No valid sessions found.")
        sys.exit(1)
        
    train_size = int(0.95 * total_sessions)
    train_sessions = sessions[:train_size]
    val_sessions = sessions[train_size:]
    
    with open(train_path, 'w', encoding='utf-8') as f:
        for session in train_sessions:
            f.write(json.dumps(session, ensure_ascii=False) + '\n')
            
    with open(val_path, 'w', encoding='utf-8') as f:
        for session in val_sessions:
            f.write(json.dumps(session, ensure_ascii=False) + '\n')
            
    print("\n" + "="*30)
    print("        SPLIT SUMMARY")
    print("="*30)
    print(f"Total sessions:           {total_sessions}")
    print(f"Train sessions (95%):     {len(train_sessions)}")
    print(f"Validation sessions (5%): {len(val_sessions)}")
    print(f"\nSaved train data to: {train_path}")
    print(f"Saved validation data to: {val_path}")

if __name__ == '__main__':
    if sys.stdout.encoding.lower() != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
        
    # By default, reads the tagged output from step 06
    base_dir = Path(__file__).parent.parent
    default_input = str(base_dir / "data" / "output" / "tagged_data.jsonl")
    input_file = sys.argv[1] if len(sys.argv) > 1 else default_input
    
    split_data(input_file)
