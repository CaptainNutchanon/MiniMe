import os
import json
import glob
import re

# Exact / substring phrases that mark a message as system noise
SKIP_SUBSTRINGS = {
    "sent an attachment", "ส่งไฟล์แนบ",
    "แชร์โพสต์", "แชร์สตอรี่",
    "shared a story",
    "quiet mode",
    "started an audio call", "started a video chat",
    "missed an audio call", "missed a video chat",
    "Call ended",
}

# Prefix-matched phrases (content starts with these)
SKIP_PREFIXES = ("Reacted ", "Liked ")

# Regex to detect URLs (standalone or embedded)
URL_PATTERN = re.compile(
    r'https?://\S+|'
    r'\b(?:www\.|facebook\.com|instagram\.com|youtu(?:be\.com|\.be))\S*',
    re.IGNORECASE
)

def fix_encoding(text):
    """Re-decode text that was mistakenly read as latin1 instead of utf-8."""
    try:
        return text.encode('latin1').decode('utf-8')
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text

def clean_messages(messages):
    cleaned = []
    for msg in messages:
        # Keep only messages with content and no call_duration
        if 'content' not in msg or 'call_duration' in msg:
            continue

        sender  = fix_encoding(msg.get('sender_name', ''))
        content = fix_encoding(msg['content'])

        # Skip system/noise — substring match or prefix match
        if any(phrase in content for phrase in SKIP_SUBSTRINGS):
            continue
        if content.startswith(SKIP_PREFIXES):
            continue

        # Strip URLs from content
        content = URL_PATTERN.sub('', content).strip()

        # Skip if nothing remains after stripping
        if not content:
            continue

        cleaned.append({
            'sender':    sender,
            'content':   content,
            'timestamp': msg['timestamp_ms'],
        })

    return cleaned

# ── Main ──────────────────────────────────────────────────────────────────────

root    = os.path.dirname(os.path.abspath(__file__))
out_dir = os.path.join(root, 'cleaned_output')
os.makedirs(out_dir, exist_ok=True)

for filepath in glob.glob(os.path.join(root, '*.json')):
    filename = os.path.basename(filepath)

    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    messages = data.get('messages', [])
    cleaned  = clean_messages(messages)

    out_path = os.path.join(out_dir, filename)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2)

    print(f'{filename}: {len(messages)} -> {len(cleaned)} messages')
