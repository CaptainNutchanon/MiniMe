import os
import json
import glob
import re

# ── Step 4: Clean + Filter conversations ──────────────────────────────────────
# Reads raw Facebook Messenger JSON from data/raw/
# Applies message-level cleaning AND conversation-level filtering
# Saves only valid 1-on-1 conversations to data/filtered/

# ── Config ────────────────────────────────────────────────────────────────────

SKIP_SUBSTRINGS = {
    "sent an attachment", "ส่งไฟล์แนบ",
    "แชร์โพสต์", "แชร์สตอรี่", "shared a story",
    "quiet mode",
    "started an audio call", "started a video chat",
    "missed an audio call", "missed a video chat",
    "Call ended",
}
SKIP_PREFIXES = ("Reacted ", "Liked ")

URL_PATTERN = re.compile(
    r'https?://\S+|'
    r'\b(?:www\.|facebook\.com|instagram\.com|youtu(?:be\.com|\.be))\S*',
    re.IGNORECASE
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def fix_encoding(text):
    """Re-decode Thai text that was saved as latin1 instead of utf-8."""
    try:
        return text.encode('latin1').decode('utf-8')
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text

def clean_message(msg):
    """
    Apply full cleaning pipeline to a single raw message dict.
    Returns a cleaned dict, or None if the message should be skipped.
    """
    if 'content' not in msg or 'call_duration' in msg:
        return None

    sender  = fix_encoding(msg.get('sender_name', ''))
    content = fix_encoding(msg['content'])

    if any(phrase in content for phrase in SKIP_SUBSTRINGS):
        return None
    if content.startswith(SKIP_PREFIXES):
        return None

    content = URL_PATTERN.sub('', content).strip()
    if not content:
        return None

    return {'sender': sender, 'content': content, 'timestamp': msg['timestamp_ms']}

# ── Main ──────────────────────────────────────────────────────────────────────

base     = os.path.dirname(os.path.abspath(__file__))
raw_dir  = os.path.normpath(os.path.join(base, '..', 'data', 'raw'))
out_dir  = os.path.normpath(os.path.join(base, '..', 'data', 'filtered'))
os.makedirs(out_dir, exist_ok=True)

skipped = []

for filepath in glob.glob(os.path.join(raw_dir, '*.json')):
    filename = os.path.basename(filepath)

    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # ── Conversation-level filter: group chats ───────────────────────────────
    participants = data.get('participants', [])
    if len(participants) > 2:
        skipped.append(f'SKIP (group chat, {len(participants)} participants): {filename}')
        continue

    # ── Message-level cleaning ───────────────────────────────────────────────
    raw_messages = data.get('messages', [])
    cleaned = [c for msg in raw_messages if (c := clean_message(msg))]

    # ── Conversation-level filter: empty or monologue ────────────────────────
    if not cleaned:
        skipped.append(f'SKIP (empty after cleaning): {filename}')
        continue

    unique_senders = {msg['sender'] for msg in cleaned}
    if len(unique_senders) <= 1:
        skipped.append(f'SKIP (monologue): {filename}')
        continue

    # ── Save valid 1-on-1 conversation ───────────────────────────────────────
    out_path = os.path.join(out_dir, filename)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2)

    print(f'OK  {filename}: {len(cleaned)} messages ({len(unique_senders)} senders)')

print()
for s in skipped:
    print(s)
