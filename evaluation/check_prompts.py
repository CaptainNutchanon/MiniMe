"""
evaluation/check_prompts.py

Validate prompts.jsonl and check for data contamination against train/val sets.

Checks:
  - JSONL parses without error
  - Every row has `id`, `category`, `turns`
  - Every `turns` list ends with a user message
  - No duplicate `id`s
  - No test prompt is a verbatim copy of any message in train.jsonl or val.jsonl

Usage:
  python evaluation/check_prompts.py
  python evaluation/check_prompts.py --prompts evaluation/prompts.jsonl
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PROMPTS_FILE = ROOT / "evaluation" / "prompts.jsonl"
TRAIN_FILE = ROOT / "data" / "output" / "train.jsonl"
VAL_FILE = ROOT / "data" / "output" / "val.jsonl"

# Minimum content length to check for contamination.
# Ultra-short phrases like "ว่า" (3 chars), "อยู่" (4 chars), "ว่าไง" (5 chars)
# are common Thai greetings that naturally appear in both train data and test prompts.
# Only flag verbatim matches for longer, more specific content.
MIN_CONTENT_LEN_FOR_CONTAMINATION_CHECK = 10

VALID_CATEGORIES = {
    "identity",
    "bot_identity",
    "greeting",
    "food_game_travel",
    "emotion_support",
    "privacy_status",
    "open_ended",
    "multi_turn",
}


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    errors = []
    with path.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append((i, json.loads(line)))
            except json.JSONDecodeError as e:
                errors.append(f"  Line {i}: {e}")
    return rows, errors


def extract_all_messages(sessions: list[tuple]) -> set[str]:
    """Extract all message content strings from train/val sessions."""
    messages = set()
    for _, session in sessions:
        for msg in session.get("messages", []):
            content = str(msg.get("content", "")).strip()
            if content:
                messages.add(content)
    return messages


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate evaluation prompts and check contamination.")
    parser.add_argument("--prompts", default=str(PROMPTS_FILE))
    parser.add_argument("--train", default=str(TRAIN_FILE))
    parser.add_argument("--val", default=str(VAL_FILE))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    prompts_path = Path(args.prompts)
    train_path = Path(args.train)
    val_path = Path(args.val)

    print("=" * 60)
    print("MiniMe Prompt Validation + Contamination Check")
    print("=" * 60)

    # -- Load prompts --
    print(f"\n[1/4] Loading prompts from {prompts_path}...")
    if not prompts_path.exists():
        print(f"  ERROR: File not found: {prompts_path}")
        sys.exit(1)

    prompt_rows, parse_errors = load_jsonl(prompts_path)
    if parse_errors:
        print(f"  JSONL parse errors ({len(parse_errors)}):")
        for e in parse_errors:
            print(e)
        sys.exit(1)
    print(f"  OK: {len(prompt_rows)} prompts loaded, 0 parse errors")

    # -- Structural validation --
    print("\n[2/4] Structural validation...")
    structural_errors = []
    ids_seen = {}
    category_counts: dict[str, int] = {}

    for line_no, row in prompt_rows:
        pid = row.get("id")
        cat = row.get("category")
        turns = row.get("turns")

        if not pid:
            structural_errors.append(f"  Line {line_no}: missing `id`")
        if not cat:
            structural_errors.append(f"  Line {line_no} ({pid}): missing `category`")
        elif cat not in VALID_CATEGORIES:
            structural_errors.append(f"  Line {line_no} ({pid}): unknown category `{cat}`")

        if not isinstance(turns, list) or len(turns) == 0:
            structural_errors.append(f"  Line {line_no} ({pid}): `turns` must be non-empty list")
        else:
            last_turn = turns[-1]
            if last_turn.get("role") != "user":
                structural_errors.append(f"  Line {line_no} ({pid}): last turn must be role=user, got {last_turn.get('role')!r}")
            for t in turns:
                if t.get("role") not in ("user", "assistant"):
                    structural_errors.append(f"  Line {line_no} ({pid}): invalid role {t.get('role')!r}")

        if pid:
            if pid in ids_seen:
                structural_errors.append(f"  Line {line_no}: duplicate id `{pid}` (first seen line {ids_seen[pid]})")
            else:
                ids_seen[pid] = line_no

        if cat:
            category_counts[cat] = category_counts.get(cat, 0) + 1

    if structural_errors:
        print(f"  FAILED — {len(structural_errors)} errors:")
        for e in structural_errors:
            print(e)
        sys.exit(1)

    print(f"  OK: All {len(prompt_rows)} prompts have valid structure, 0 duplicate IDs")
    print("\n  Category distribution:")
    for cat, count in sorted(category_counts.items()):
        print(f"    {cat}: {count}")

    # -- Contamination check --
    print("\n[3/4] Loading train/val sets for contamination check...")
    train_rows, _ = load_jsonl(train_path) if train_path.exists() else ([], [])
    val_rows, _ = load_jsonl(val_path) if val_path.exists() else ([], [])
    train_messages = extract_all_messages(train_rows)
    val_messages = extract_all_messages(val_rows)
    all_known = train_messages | val_messages
    print(f"  Train messages: {len(train_messages)}")
    print(f"  Val messages  : {len(val_messages)}")

    print("\n[4/4] Checking for verbatim contamination...")
    contaminated = []
    for _, row in prompt_rows:
        pid = row.get("id", "")
        for turn in row.get("turns", []):
            content = str(turn.get("content", "")).strip()
            if len(content) >= MIN_CONTENT_LEN_FOR_CONTAMINATION_CHECK and content in all_known:
                contaminated.append(f"  {pid}: turn content found in train/val: {content!r}")

    if contaminated:
        print(f"  WARNING: {len(contaminated)} verbatim matches found:")
        for c in contaminated:
            print(c)
        print("  Review these prompts — they may lead to inflated test scores.")
    else:
        print(f"  OK: No verbatim matches found in train/val ({len(all_known)} messages checked)")

    print("\n" + "=" * 60)
    status = "PASSED" if not structural_errors else "FAILED"
    warn = " (with contamination warnings)" if contaminated else ""
    print(f"Validation: {status}{warn}")
    print(f"Total prompts : {len(prompt_rows)}")
    print(f"Unique IDs    : {len(ids_seen)}")
    print("=" * 60)

    if contaminated:
        sys.exit(2)  # Warning exit code, not error


if __name__ == "__main__":
    main()
