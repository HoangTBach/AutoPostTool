import os
import subprocess
import sys
from pathlib import Path


# ----- Open Directory -----
def open_directory(path: str | Path):
    directory = Path(path)

    if not directory.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")

    if not directory.is_dir():
        raise NotADirectoryError(f"Not a directory: {directory}")

    if sys.platform == "win32":
        os.startfile(directory)
        return

    if sys.platform == "darwin":
        subprocess.Popen(["open", str(directory)])
        return

    subprocess.Popen(["xdg-open", str(directory)])
