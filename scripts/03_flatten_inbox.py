import os
import shutil

# ── Step 3: Flatten raw inbox ─────────────────────────────────────────────────
# Moves all JSON files from sub-folders up to data/raw/ root, then deletes the sub-folders

raw_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'raw_data'))

for name in os.listdir(raw_dir):
    folder = os.path.join(raw_dir, name)
    if not os.path.isdir(folder):
        continue

    for file in os.listdir(folder):
        if file.endswith('.json'):
            src = os.path.join(folder, file)
            dst = os.path.join(raw_dir, file)
            shutil.move(src, dst)
            print(f'Moved: {src} -> {dst}')

    try:
        shutil.rmtree(folder)
        print(f'Deleted: {folder}')
    except Exception as e:
        print(f'Error deleting {folder}: {e}')
