import os
import shutil

from config import RAW_DATA_DIR

# ── Step 1: Delete media folders from raw Instagram chat export ──────────────
# Run this first after dropping your Instagram export into data/raw/

TARGET_NAMES = {'audio', 'photos', 'videos'}

raw_dir = os.path.normpath(RAW_DATA_DIR)

if not os.path.isdir(raw_dir):
    raise SystemExit(f"Raw data directory not found: {raw_dir}")

for dirpath, dirnames, _ in os.walk(raw_dir, topdown=True):
    for name in list(dirnames):
        if name in TARGET_NAMES:
            full_path = os.path.join(dirpath, name)
            try:
                shutil.rmtree(full_path)
                print(f'Deleted: {full_path}')
            except Exception as e:
                print(f'Error deleting {full_path}: {e}')
            dirnames.remove(name)  # skip descending into deleted folder
