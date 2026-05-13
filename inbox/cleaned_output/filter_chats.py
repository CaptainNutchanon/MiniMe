import os
import json
import glob
import re

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
    """Re-decode thai text that was saved as latin1 instead of utf-8."""
    try:
        return text.encode('latin1').decode('utf-8')
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text

def clean_message(msg):
    """
    Apply the full cleaning pipeline to a single raw message dict.
    Returns a cleaned dict, or None if the message should be skipped.
    """
    # Require 'content', forbid 'call_duration'
    if 'content' not in msg or 'call_duration' in msg:
        return None

    sender  = fix_encoding(msg.get('sender_name', ''))
    content = fix_encoding(msg['content'])

    # Skip system / noise rows
    if any(phrase in content for phrase in SKIP_SUBSTRINGS):
        return None
    if content.startswith(SKIP_PREFIXES):
        return None

    # Strip URLs; skip if nothing remains
    content = URL_PATTERN.sub('', content).strip()
    if not content:
        return None

    return {'sender': sender, 'content': content, 'timestamp': msg['timestamp_ms']}

# ── Main ──────────────────────────────────────────────────────────────────────

root    = os.path.dirname(os.path.abspath(__file__))
out_dir = os.path.join(root, 'filtered_output')
os.makedirs(out_dir, exist_ok=True)

skipped = []

for filepath in glob.glob(os.path.join(root, '*.json')):
    filename = os.path.basename(filepath)

    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # ── Detect input format ──────────────────────────────────────────────────
    # Raw Facebook export  → dict with 'participants' and 'messages' keys
    # Already-cleaned file → flat list of {sender, content, timestamp}

    if isinstance(data, dict):
        # File-level filter: group chat (more than 2 participants)
        participants = data.get('participants', [])
        if len(participants) > 2:
            skipped.append(f'SKIP (group chat): {filename}')
            continue

        raw_messages = data.get('messages', [])
        cleaned = [c for msg in raw_messages if (c := clean_message(msg))]

    elif isinstance(data, list):
        # Already-cleaned flat list — re-apply content filters only
        cleaned = []
        for msg in data:
            content = msg.get('content', '')
            if any(phrase in content for phrase in SKIP_SUBSTRINGS):
                continue
            if content.startswith(SKIP_PREFIXES):
                continue
            content = URL_PATTERN.sub('', content).strip()
            if not content:
                continue
            cleaned.append({
                'sender':    msg.get('sender', ''),
                'content':   content,
                'timestamp': msg.get('timestamp', 0),
            })
    else:
        skipped.append(f'SKIP (unknown format): {filename}')
        continue

    # File-level filter: empty chat
    if not cleaned:
        skipped.append(f'SKIP (empty after cleaning): {filename}')
        continue

    # File-level filter: solo monologue (≤1 unique sender)
    unique_senders = {msg['sender'] for msg in cleaned}
    if len(unique_senders) <= 1:
        skipped.append(f'SKIP (monologue): {filename}')
        continue

    # File-level filter: group chat proxy for already-cleaned files (>2 senders)
    if isinstance(data, list) and len(unique_senders) > 2:
        skipped.append(f'SKIP (group chat, {len(unique_senders)} senders): {filename}')
        continue

    # Save valid 1-on-1 conversation
    out_path = os.path.join(out_dir, filename)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2)

    print(f'OK  {filename}: {len(cleaned)} messages ({len(unique_senders)} senders)')

print()
for s in skipped:
    print(s)
