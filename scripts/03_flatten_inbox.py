import argparse
import os
import shutil

from config import RAW_DATA_DIR


def main():
    """
    Optional legacy step.

    Moves JSON files from each conversation folder up to data/raw_data and
    deletes the now-empty conversation folders. Step 04 supports this flat
    layout as well as the original folder layout.
    """
    parser = argparse.ArgumentParser(description="Flatten raw Instagram conversation folders.")
    parser.add_argument("--apply", action="store_true", help="Actually move files and delete folders. Without this, only preview changes.")
    args = parser.parse_args()

    raw_dir = os.path.normpath(RAW_DATA_DIR)
    if not os.path.isdir(raw_dir):
        raise SystemExit(f"Raw data directory not found: {raw_dir}")

    moved = 0
    deleted = 0
    for name in os.listdir(raw_dir):
        folder = os.path.join(raw_dir, name)
        if not os.path.isdir(folder):
            continue

        for filename in os.listdir(folder):
            if not filename.endswith(".json"):
                continue
            src = os.path.join(folder, filename)
            dst = os.path.join(raw_dir, filename)
            if os.path.exists(dst):
                base, ext = os.path.splitext(filename)
                counter = 2
                while os.path.exists(dst):
                    dst = os.path.join(raw_dir, f"{base}_{counter}{ext}")
                    counter += 1
            if args.apply:
                shutil.move(src, dst)
            moved += 1
            action = "Moved" if args.apply else "Would move"
            print(f"{action}: {src} -> {dst}")

        try:
            if args.apply:
                shutil.rmtree(folder)
            deleted += 1
            action = "Deleted" if args.apply else "Would delete"
            print(f"{action}: {folder}")
        except Exception as exc:
            print(f"Error deleting {folder}: {exc}")

    mode = "moved" if args.apply else "would move"
    delete_mode = "deleted" if args.apply else "would delete"
    print(f"Done - {mode} {moved:,} files and {delete_mode} {deleted:,} folders")
    if not args.apply:
        print("Run again with --apply to make these changes.")


if __name__ == "__main__":
    main()
