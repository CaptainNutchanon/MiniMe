import glob
import json
import os
import sys
from pathlib import Path

from config import ASSISTANT_NAME, FILTERED_DIR, OUTPUT_DIR, SESSION_GAP_MS

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from minime_core.runtime_env import configure_utf8

configure_utf8()

def get_role(sender):
    return "assistant" if sender == ASSISTANT_NAME else "user"


def split_into_sessions(messages):
    sessions, current = [], []
    for msg in messages:
        if current and (msg["timestamp"] - current[-1]["timestamp"]) > SESSION_GAP_MS:
            sessions.append(current)
            current = []
        current.append(msg)
    if current:
        sessions.append(current)
    return sessions


def format_session(messages):
    turns = []
    for msg in messages:
        role = get_role(msg["sender"])
        if turns and turns[-1]["role"] == role:
            turns[-1]["content"] += " " + msg["content"]
        else:
            turns.append({"role": role, "content": msg["content"]})

    while turns and turns[0]["role"] == "assistant":
        turns.pop(0)

    roles = {turn["role"] for turn in turns}
    if "user" not in roles or "assistant" not in roles:
        return None
    return turns


def main():
    input_dir = os.path.normpath(FILTERED_DIR)
    output_dir = os.path.normpath(OUTPUT_DIR)
    output_path = os.path.join(output_dir, "base_data.jsonl")
    os.makedirs(output_dir, exist_ok=True)

    total_sessions = 0
    with open(output_path, "w", encoding="utf-8") as out_f:
        for filepath in sorted(glob.glob(os.path.join(input_dir, "*.json"))):
            source = os.path.basename(filepath)
            with open(filepath, "r", encoding="utf-8") as f:
                messages = json.load(f)

            if not isinstance(messages, list) or not messages:
                continue

            messages.sort(key=lambda message: message["timestamp"])
            for session_index, session_msgs in enumerate(split_into_sessions(messages)):
                chat = format_session(session_msgs)
                if chat is None:
                    continue
                row = {
                    "source": source,
                    "session_index": session_index,
                    "session_start_ms": session_msgs[0]["timestamp"],
                    "session_end_ms": session_msgs[-1]["timestamp"],
                    "messages": chat,
                }
                out_f.write(json.dumps(row, ensure_ascii=False) + "\n")
                total_sessions += 1

    print(f"Done - {total_sessions:,} sessions written to {output_path}")


if __name__ == "__main__":
    main()
