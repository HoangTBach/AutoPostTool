from pathlib import Path

from src.configs.path import DOWNLOAD_DIR, RESULT_DIR, ensure_app_dirs
from src.configs.reports import REPORT_FILES


# ----- Report Paths -----
def get_report_paths(feature: str) -> tuple[Path, Path]:
    feature = feature.strip().lower()

    if feature not in REPORT_FILES:
        raise ValueError(f"Unknown report feature: {feature}")

    ensure_app_dirs()

    files = REPORT_FILES[feature]
    result_file = DOWNLOAD_DIR / files["result"]
    devlog_file = RESULT_DIR / files["devlog"]

    return result_file, devlog_file
