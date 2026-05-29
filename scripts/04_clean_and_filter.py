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
    "sent a live location", "ส่งตำแหน่งที่ตั้งแบบเรียลไทม์",
    "changed the theme",
    "Audio call started",
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
raw_dir  = os.path.normpath(os.path.join(base, '..', 'data', 'raw_data'))
out_dir  = os.path.normpath(os.path.join(base, '..', 'data', 'filtered'))
os.makedirs(out_dir, exist_ok=True)

skipped = []

# ── Group message_N.json files by their parent conversation folder ─────────
conv_dirs = [
    d for d in glob.glob(os.path.join(raw_dir, '*'))
    if os.path.isdir(d)
]

used_names = {}  # short_name -> count, for conflict resolution

for conv_dir in sorted(conv_dirs):
    conv_name  = os.path.basename(conv_dir)
    short_name = re.sub(r'_\d+$', '', conv_name)  # strip trailing numeric ID
    json_files = sorted(glob.glob(os.path.join(conv_dir, 'message_*.json')))

    if not json_files:
        continue

    # ── Merge all message_N.json parts into one message list ─────────────────
    all_raw_messages = []
    participants = []
    for filepath in json_files:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not participants:
            participants = data.get('participants', [])
        all_raw_messages.extend(data.get('messages', []))

    # ── Conversation-level filter: group chats ────────────────────────────────────────────
    if len(participants) > 2:
        skipped.append(f'SKIP (group chat, {len(participants)} participants): {short_name}')
        continue

    # ── Message-level cleaning ────────────────────────────────────────────────
    cleaned = [c for msg in all_raw_messages if (c := clean_message(msg))]

    # ── Conversation-level filter: empty or monologue ────────────────────────────────────
    if not cleaned:
        skipped.append(f'SKIP (empty after cleaning): {short_name}')
        continue

    unique_senders = {msg['sender'] for msg in cleaned}
    if len(unique_senders) <= 1:
        skipped.append(f'SKIP (monologue): {short_name}')
        continue

    # ── Resolve filename conflicts ────────────────────────────────────────────────────────────────
    if short_name in used_names:
        used_names[short_name] += 1
        out_filename = f'{short_name}_{used_names[short_name]}.json'
    else:
        used_names[short_name] = 1
        out_filename = f'{short_name}.json'

    # ── Save merged conversation using short username name ──────────────────────────
    out_path = os.path.join(out_dir, out_filename)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2)

    parts = len(json_files)
    print(f'OK  {out_filename}: {len(cleaned)} messages ({len(unique_senders)} senders)'
          + (f'  [{parts} parts merged]' if parts > 1 else ''))

print()
for s in skipped:
    print(s)
