import os
import shutil

root = os.path.dirname(os.path.abspath(__file__))

for name in os.listdir(root):
    folder = os.path.join(root, name)
    if not os.path.isdir(folder):
        continue

    for file in os.listdir(folder):
        if file.endswith('.json'):
            src = os.path.join(folder, file)
            dst = os.path.join(root, file)
            shutil.move(src, dst)
            print(f'Moved: {src} -> {dst}')

    try:
        shutil.rmtree(folder)
        print(f'Deleted: {folder}')
    except Exception as e:
        print(f'Error deleting {folder}: {e}')
