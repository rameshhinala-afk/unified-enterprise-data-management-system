import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("UDMS_DATA_DIR", BASE_DIR / "data"))
SOURCE_DIR = DATA_DIR / "source"
DB_PATH = DATA_DIR / "udms.db"
API_HOST = os.environ.get("UDMS_API_HOST", "127.0.0.1")
API_PORT = int(os.environ.get("UDMS_API_PORT", 8000))
