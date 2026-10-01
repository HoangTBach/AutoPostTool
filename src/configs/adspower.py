import os
from pathlib import Path

# ----- Path -----
ROOT_DIR = Path(__file__).resolve().parents[2]

ADSPOWER_SETTINGS_FILE = ROOT_DIR / "data" / "adspower_settings.json"


# ----- AdsPower -----
ADSPOWER_DEFAULT_URL = "127.0.0.1:50325"

ADSPOWER_TIMEOUT = 3

ADSPOWER_API_KEY = os.getenv(
    "ADSPOWER_API_KEY",
    "",
)
