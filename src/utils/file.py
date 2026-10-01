import os
from pathlib import Path


# ----- Open Directory -----
def open_directory(
    directory: str | Path,
):
    directory = Path(directory)

    if not directory.exists():
        raise FileNotFoundError(f"Cannot find: {directory}")

    os.startfile(directory)
