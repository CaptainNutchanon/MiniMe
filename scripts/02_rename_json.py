import argparse
import glob
import os

from config import RAW_DATA_DIR


def main():
    """
    Optional legacy step.

    Renames JSON files inside each Instagram conversation folder using the
    conversation folder prefix. This is useful only if you want to flatten
    raw_data with step 03 afterwards.
    """
    parser = argparse.ArgumentParser(description="Rename raw Instagram chat JSON files before optional flattening.")
    parser.add_argument("--apply", action="store_true", help="Actually rename files. Without this, only preview changes.")
    args = parser.parse_args()

    raw_dir = os.path.normpath(RAW_DATA_DIR)
    if not os.path.isdir(raw_dir):
        raise SystemExit(f"Raw data directory not found: {raw_dir}")

    renamed = 0
    for folder_name in os.listdir(raw_dir):
        folder = os.path.join(raw_dir, folder_name)
        if not os.path.isdir(folder):
            continue

        name = folder_name.split("_", 1)[0]
        json_files = sorted(glob.glob(os.path.join(folder, "*.json")))

        for index, json_file in enumerate(json_files, 1):
            suffix = f"_{index}" if len(json_files) > 1 else ""
            new_path = os.path.join(folder, f"{name}{suffix}.json")
            if os.path.abspath(json_file) == os.path.abspath(new_path):
                continue
            if os.path.exists(new_path):
                print(f"Skip existing target: {new_path}")
                continue
            if args.apply:
                os.rename(json_file, new_path)
            renamed += 1
            action = "Renamed" if args.apply else "Would rename"
            print(f"{action}: {json_file} -> {new_path}")

    mode = "renamed" if args.apply else "would rename"
    print(f"Done - {mode} {renamed:,} files")
    if not args.apply:
        print("Run again with --apply to make these changes.")


if __name__ == "__main__":
    main()
