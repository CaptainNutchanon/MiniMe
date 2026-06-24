from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw_data"
FILTERED_DIR = DATA_DIR / "filtered"
OUTPUT_DIR = DATA_DIR / "output"

ASSISTANT_NAME = "กัปปิตัน"
SESSION_GAP_MS = 3_600_000
