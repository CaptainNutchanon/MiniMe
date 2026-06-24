import glob
import json
import os
import re
import sys
from pathlib import Path

from config import FILTERED_DIR, RAW_DATA_DIR

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from minime_core.runtime_env import configure_utf8

configure_utf8()

SKIP_SUBSTRINGS = {
    "sent an attachment",
    "ส่งไฟล์แนบ",
    "แชร์โพสต์",
    "แชร์สตอรี่",
    "shared a story",
    "quiet mode",
    "started an audio call",
    "started a video chat",
    "missed an audio call",
    "missed a video chat",
    "Call ended",
    "sent a live location",
    "ส่งตำแหน่งที่ตั้งแบบเรียลไทม์",
    "changed the theme",
    "Audio call started",
}
SKIP_PREFIXES = ("Reacted ", "Liked ")
URL_PATTERN = re.compile(
    r"https?://\S+|"
    r"\b(?:www\.|facebook\.com|instagram\.com|youtu(?:be\.com|\.be))\S*",
    re.IGNORECASE,
)


def fix_encoding(text):
    """Re-decode Thai text that was saved as latin1 instead of utf-8."""
    try:
        return text.encode("latin1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def clean_message(msg):
    if "content" not in msg or "call_duration" in msg:
        return None

    sender = fix_encoding(msg.get("sender_name", ""))
    content = fix_encoding(msg["content"])
    content = content.replace(" (edited)", "").replace("(edited)", "")

    if any(phrase in content for phrase in SKIP_SUBSTRINGS):
        return None
    if content.startswith(SKIP_PREFIXES):
        return None

    content = URL_PATTERN.sub("", content).strip()
    if not content:
        return None

    return {"sender": sender, "content": content, "timestamp": msg["timestamp_ms"]}


def short_name_from_stem(stem):
    return re.sub(r"_\d+$", "", stem)


def conversation_sources(raw_dir):
    """Support both raw folder layout and optional 02/03 flattened layout."""
    sources = []

    # Recommended layout:
    # data/raw_data/<conversation>/message_1.json
    for conv_dir in sorted(glob.glob(os.path.join(raw_dir, "*"))):
        if not os.path.isdir(conv_dir):
            continue
        short_name = short_name_from_stem(os.path.basename(conv_dir))
        json_files = sorted(glob.glob(os.path.join(conv_dir, "message_*.json")))

        # Optional layout after running step 02 but before step 03.
        if not json_files:
            json_files = sorted(glob.glob(os.path.join(conv_dir, "*.json")))
        if json_files:
            sources.append((short_name, json_files))

    # Optional layout after running step 02 + 03:
    # data/raw_data/<short_name>_1.json
    flat_groups = {}
    for filepath in sorted(glob.glob(os.path.join(raw_dir, "*.json"))):
        stem = os.path.splitext(os.path.basename(filepath))[0]
        short_name = short_name_from_stem(stem)
        flat_groups.setdefault(short_name, []).append(filepath)
    sources.extend((short_name, files) for short_name, files in sorted(flat_groups.items()))

    return sources


def load_raw_parts(json_files):
    all_raw_messages = []
    participants = []
    for filepath in json_files:
        with open(filepath, "r", encoding="utf-8") as file:
            data = json.load(file)
        if not participants:
            participants = data.get("participants", [])
        all_raw_messages.extend(data.get("messages", []))
    return participants, all_raw_messages


def main():
    raw_dir = os.path.normpath(RAW_DATA_DIR)
    out_dir = os.path.normpath(FILTERED_DIR)
    os.makedirs(out_dir, exist_ok=True)

    if not os.path.isdir(raw_dir):
        raise SystemExit(f"Raw data directory not found: {raw_dir}")

    skipped = []
    used_names = {}
    written = 0

    for short_name, json_files in conversation_sources(raw_dir):
        participants, all_raw_messages = load_raw_parts(json_files)

        if len(participants) > 2:
            skipped.append(f"SKIP (group chat, {len(participants)} participants): {short_name}")
            continue

        cleaned = [cleaned for msg in all_raw_messages if (cleaned := clean_message(msg))]
        if not cleaned:
            skipped.append(f"SKIP (empty after cleaning): {short_name}")
            continue

        unique_senders = {msg["sender"] for msg in cleaned}
        if len(unique_senders) <= 1:
            skipped.append(f"SKIP (monologue): {short_name}")
            continue

        if short_name in used_names:
            used_names[short_name] += 1
            out_filename = f"{short_name}_{used_names[short_name]}.json"
        else:
            used_names[short_name] = 1
            out_filename = f"{short_name}.json"

        out_path = os.path.join(out_dir, out_filename)
        with open(out_path, "w", encoding="utf-8") as file:
            json.dump(cleaned, file, ensure_ascii=False, indent=2)

        written += 1
        parts = len(json_files)
        print(
            f"OK  {out_filename}: {len(cleaned)} messages ({len(unique_senders)} senders)"
            + (f"  [{parts} parts merged]" if parts > 1 else "")
        )

    print()
    for item in skipped:
        print(item)
    print(f"\nDone - {written:,} conversations written to {out_dir}")


if __name__ == "__main__":
    main()
