import json
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
from pathlib import Path

# ── Step 4b: Filter romantic sessions from girlfriend conversations ────────────
# Reads pimmu.json and pvnotpv.json from data/filtered/
# Removes sessions where the assistant used romantic keywords
# Overwrites the files in-place so the rest of the pipeline works unchanged

ASSISTANT_NAME = "กัปปิตัน"
SESSION_GAP_MS = 3_600_000  # 1 hour = new session

GF_FILES = ["pimmu.json", "pvnotpv.json"]

ROMANTIC_KEYWORDS = [
    "รักนะ", "รักเลย", "รักมาก", "รักที่สุด",
    "ที่รัก", "หวานใจ",
    "ฝันดีคับ",
    "กอด", "จูบ", "หอม",
    "น่ารักมาก",
    "💕", "💖", "💗", "💓", "🥰", "😘",
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def split_into_sessions(messages):
    """Split sorted message list into sessions based on time gap."""
    sessions, current = [], []
    for msg in messages:
        if current and (msg["timestamp"] - current[-1]["timestamp"]) > SESSION_GAP_MS:
            sessions.append(current)
            current = []
        current.append(msg)
    if current:
        sessions.append(current)
    return sessions

def is_romantic_session(session):
    """Return True if assistant used any romantic keyword in this session."""
    for msg in session:
        if msg["sender"] == ASSISTANT_NAME:
            content = msg["content"]
            for keyword in ROMANTIC_KEYWORDS:
                if keyword in content:
                    return True
    return False

# ── Main ──────────────────────────────────────────────────────────────────────

base         = Path(__file__).parent.parent
filtered_dir = base / "data" / "filtered"

print("=" * 55)
print("  Step 4b — Filter Romantic Sessions (Girlfriend Only)")
print("=" * 55)

total_removed = 0
total_kept    = 0

for filename in GF_FILES:
    filepath = filtered_dir / filename
    if not filepath.exists():
        print(f"\n  [SKIP] {filename} not found")
        continue

    with open(filepath, "r", encoding="utf-8") as f:
        messages = json.load(f)

    if not isinstance(messages, list) or not messages:
        print(f"\n  [SKIP] {filename} is empty")
        continue

    messages.sort(key=lambda m: m["timestamp"])
    sessions = split_into_sessions(messages)

    kept_sessions    = []
    removed_sessions = []

    for session in sessions:
        if is_romantic_session(session):
            removed_sessions.append(session)
        else:
            kept_sessions.append(session)

    # Flatten kept sessions back to flat message list
    kept_messages = [msg for session in kept_sessions for msg in session]

    # Overwrite file with filtered messages
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(kept_messages, f, ensure_ascii=False, indent=2)

    removed = len(removed_sessions)
    kept    = len(kept_sessions)
    total   = len(sessions)
    total_removed += removed
    total_kept    += kept

    print(f"\n  >> {filename}")
    print(f"     Sessions ทั้งหมด : {total:,}")
    print(f"     เก็บไว้          : {kept:,}  ({kept/total*100:.1f}%)")
    print(f"     ตัดออก (romantic): {removed:,}  ({removed/total*100:.1f}%)")
    print(f"     Messages ที่เหลือ: {len(kept_messages):,}")

print()
print("=" * 55)
print(f"  รวมตัดออก : {total_removed:,} sessions")
print(f"  รวมเก็บไว้: {total_kept:,} sessions")
print()
print("  Done — รัน 05_build_jsonl.py ต่อได้เลย")
print("=" * 55)
