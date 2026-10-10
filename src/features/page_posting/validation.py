from pathlib import Path
from urllib.parse import urlparse

SUPPORTED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}


def validate_row(row: dict) -> str:
    if not str(row.get("caption") or "").strip():
        raise ValueError("Caption is required.")

    page_link = str(row.get("page_link") or "").strip()
    parsed = urlparse(page_link)

    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("A valid Facebook Page URL is required.")

    image_value = str(row.get("image") or "").strip()
    if not image_value:
        raise ValueError("Image file path is required.")

    image_path = Path(image_value).expanduser()

    if not image_path.is_file():
        raise ValueError(f"Image file does not exist: {image_path}")

    if image_path.suffix.lower() not in SUPPORTED_IMAGE_SUFFIXES:
        raise ValueError(f"Unsupported image format: {image_path.suffix}")

    try:
        with image_path.open("rb") as image_file:
            if not image_file.read(1):
                raise ValueError("Image file is empty.")
    except OSError as error:
        raise ValueError(f"Cannot read image file: {error}") from error

    return str(image_path.resolve())
