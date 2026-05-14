import os
import json
import glob

# ── Step 5: Build JSONL training file ─────────────────────────────────────────
# Reads filtered conversations from data/filtered/
# Splits into sessions by time gap, formats as OpenAI-style chat turns
# Outputs to data/output/training_data.jsonl

ASSISTANT_NAME = "กัปปิตัน"
SESSION_GAP_MS = 3_600_000  # 1 hour gap = new session

SYSTEM_MSG = {
    "role": "system",
    "content": (
        "คุณคือ 'กัปปิตัน' นักศึกษาชายไทย พูดจาตรงๆ สั้น กระชับ ใช้ภาษาวัยรุ่นและคำแสลงเป็นปกติ "
        "ชอบแซวเพื่อน มีอารมณ์ขัน บางทีตอบห้วนแต่ไม่ได้โกรธ แค่เป็นสไตล์ "
        "ใช้คำอย่าง 'เครๆ' 'ชัว' 'รู้เรื่อง' 'ดิวะ' เป็นประจำ "
        "ใส่อิโมจิบ้างตามอารมณ์ ไม่เยอะเกิน "
        "ถ้าเพื่อนด่ามาก็ด่ากลับแบบขำๆ ไม่ซีเรียส "
        "ตอบเป็นภาษาไทยเท่านั้น สั้นและเป็นธรรมชาติเหมือนแชทจริง"
    )
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def get_role(sender):
    return "assistant" if sender == ASSISTANT_NAME else "user"

def split_into_sessions(messages):
    """Split a sorted message list into sessions based on time gaps."""
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
    """
    Merge consecutive same-role messages, then build the chat turn list.
    Returns None if the session lacks both a user and an assistant turn.
    """
    turns = []
    for msg in messages:
        role = get_role(msg["sender"])
        if turns and turns[-1]["role"] == role:
            turns[-1]["content"] += " " + msg["content"]
        else:
            turns.append({"role": role, "content": msg["content"]})

    # Trim leading assistant turns
    while turns and turns[0]["role"] == "assistant":
        turns.pop(0)

    # Validate: must have at least one of each role
    roles = {t["role"] for t in turns}
    if "user" not in roles or "assistant" not in roles:
        return None

    return [SYSTEM_MSG] + turns

# ── Main ──────────────────────────────────────────────────────────────────────

base        = os.path.dirname(os.path.abspath(__file__))
input_dir   = os.path.normpath(os.path.join(base, '..', 'data', 'filtered'))
output_dir  = os.path.normpath(os.path.join(base, '..', 'data', 'output'))
output_path = os.path.join(output_dir, 'training_data.jsonl')
os.makedirs(output_dir, exist_ok=True)

total_sessions = 0

with open(output_path, "w", encoding="utf-8") as out_f:
    for filepath in glob.glob(os.path.join(input_dir, "*.json")):
        with open(filepath, "r", encoding="utf-8") as f:
            messages = json.load(f)

        if not isinstance(messages, list) or not messages:
            continue

        messages.sort(key=lambda m: m["timestamp"])

        for session_msgs in split_into_sessions(messages):
            chat = format_session(session_msgs)
            if chat is None:
                continue

            out_f.write(json.dumps({"messages": chat}, ensure_ascii=False) + "\n")
            total_sessions += 1

print(f"Done — {total_sessions:,} sessions written to {output_path}")
