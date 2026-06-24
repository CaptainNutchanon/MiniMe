import json
import random
import sys
from collections import defaultdict
from pathlib import Path

from config import OUTPUT_DIR

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from minime_core.runtime_env import configure_utf8

configure_utf8()

VAL_RATIO = 0.10
MIN_SESSIONS_FOR_VAL = 10
SPLIT_SEED = 42


def session_sort_key(indexed_session):
    index, session = indexed_session
    start_ms = session.get("session_start_ms")
    if isinstance(start_ms, int):
        return (start_ms, index)
    return (index, index)


def val_count_for_source(total_sessions: int) -> int:
    if total_sessions < MIN_SESSIONS_FOR_VAL:
        return 0
    return max(1, int(total_sessions * VAL_RATIO + 0.5))


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
                
    total_sessions = len(sessions)
    if total_sessions == 0:
        print("Error: No valid sessions found.")
        sys.exit(1)

    sessions_by_source = defaultdict(list)
    for index, session in enumerate(sessions):
        source = session.get("source") or "unknown"
        sessions_by_source[source].append((index, session))

    train_sessions = []
    val_sessions = []
    source_summary = []
    for source in sorted(sessions_by_source):
        source_sessions = sorted(sessions_by_source[source], key=session_sort_key)
        total_for_source = len(source_sessions)
        val_count = val_count_for_source(total_for_source)
        train_part = [session for _, session in source_sessions[: total_for_source - val_count]]
        val_part = [session for _, session in source_sessions[total_for_source - val_count :]]
        train_sessions.extend(train_part)
        val_sessions.extend(val_part)
        source_summary.append((source, total_for_source, len(train_part), len(val_part)))

    random.Random(SPLIT_SEED).shuffle(train_sessions)
    
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
    print(f"Split mode:               source-preserved chronological")
    print(f"Validation target:        {VAL_RATIO:.0%}")
    print(f"Min sessions for val:     {MIN_SESSIONS_FOR_VAL}")
    print(f"Train sessions:           {len(train_sessions)}")
    print(f"Validation sessions:      {len(val_sessions)}")
    print(f"Sources total:            {len(source_summary)}")
    print(f"Sources with val:         {sum(1 for _, _, _, val_count in source_summary if val_count)}")
    print(f"Sources train only:       {sum(1 for _, _, _, val_count in source_summary if not val_count)}")
    print("\nTop source splits:")
    for source, total_for_source, train_count, val_count in sorted(source_summary, key=lambda item: item[1], reverse=True)[:15]:
        print(f"  {source}: total={total_for_source}, train={train_count}, val={val_count}")
    print(f"\nSaved train data to: {train_path}")
    print(f"Saved validation data to: {val_path}")

if __name__ == '__main__':
    # By default, reads the base JSONL from step 05.
    default_input = str(OUTPUT_DIR / "base_data.jsonl")
    input_file = sys.argv[1] if len(sys.argv) > 1 else default_input
    
    split_data(input_file)
