import os
import glob

for folder in os.listdir('.'):
    if not os.path.isdir(folder):
        continue

    name = folder.split('_', 1)[0]
    json_files = glob.glob(os.path.join(folder, '*.json'))

    for i, json_file in enumerate(json_files, 1):
        suffix = f'_{i}' if len(json_files) > 1 else ''
        new_path = os.path.join(folder, f'{name}{suffix}.json')
        os.rename(json_file, new_path)
        print(f'{json_file} -> {new_path}')
