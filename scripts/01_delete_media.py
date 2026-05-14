import os
import shutil

# ── Step 1: Delete media folders from raw Facebook export ─────────────────────
# Run this first after dropping your Messenger export into data/raw/

TARGET_NAMES = {'audio', 'photos', 'videos'}

raw_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'raw'))

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
