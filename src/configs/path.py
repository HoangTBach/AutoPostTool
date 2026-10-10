from pathlib import Path

from PySide6.QtCore import QStandardPaths

# ----- Root -----
ROOT_DIR = Path(__file__).resolve().parents[2]


# ----- Data -----
DATA_DIR = ROOT_DIR / "data"
RESULT_DIR = DATA_DIR / "result"
DATA_FILE = DATA_DIR / "Databook.xlsx"


# ----- Downloads -----
_download_dir = QStandardPaths.writableLocation(
    QStandardPaths.StandardLocation.DownloadLocation
)
DOWNLOAD_DIR = Path(_download_dir) if _download_dir else Path.home() / "Downloads"


# ----- Directories -----
def ensure_app_dirs():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
