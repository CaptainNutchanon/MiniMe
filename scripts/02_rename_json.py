import os
import glob

# ── Step 2: Rename JSON files inside each sub-folder ──────────────────────────
# Prefixes each JSON file with its parent folder name (before the first underscore)
# e.g. pimminuch_abc123/message_1.json → pimminuch_abc123/pimminuch.json

raw_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'raw'))

for folder_name in os.listdir(raw_dir):
    folder = os.path.join(raw_dir, folder_name)
    if not os.path.isdir(folder):
        continue

    name = folder_name.split('_', 1)[0]
    json_files = glob.glob(os.path.join(folder, '*.json'))

    for i, json_file in enumerate(json_files, 1):
        suffix = f'_{i}' if len(json_files) > 1 else ''
        new_path = os.path.join(folder, f'{name}{suffix}.json')
        os.rename(json_file, new_path)
        print(f'{json_file} -> {new_path}')
