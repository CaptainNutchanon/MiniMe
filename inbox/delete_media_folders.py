import os
import shutil

TARGET_NAMES = {'audio', 'photos', 'videos'}
root = os.path.dirname(os.path.abspath(__file__))

for dirpath, dirnames, _ in os.walk(root, topdown=True):
    for name in list(dirnames):
        if name in TARGET_NAMES:
            full_path = os.path.join(dirpath, name)
            try:
                shutil.rmtree(full_path)
                print(f'Deleted: {full_path}')
            except Exception as e:
                print(f'Error deleting {full_path}: {e}')
            dirnames.remove(name)  # skip descending into deleted folder
