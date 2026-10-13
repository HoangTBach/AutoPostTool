from pathlib import Path
from urllib.parse import urlparse

IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".bmp",
}

VIDEO_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".m4v",
    ".avi",
    ".mkv",
    ".webm",
}

SUPPORTED_MEDIA_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS


def validate_row(row: dict) -> str:
    if not str(row.get("caption") or "").strip():
        raise ValueError("Caption is required.")

    page_link = str(row.get("page_link") or "").strip()
    parsed = urlparse(page_link)

    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("A valid Facebook Page URL is required.")

    image_value = str(row.get("image") or "").strip()
    if not image_value:
        raise ValueError("Media file path is required.")

    image_path = Path(image_value).expanduser()

    if not image_path.is_file():
        raise ValueError(f"Media file does not exist: {image_path}")

    if image_path.suffix.lower() not in SUPPORTED_MEDIA_EXTENSIONS:
        raise ValueError(f"Unsupported media format: {image_path.suffix}")

    try:
        with image_path.open("rb") as image_file:
            if not image_file.read(1):
                raise ValueError("Media file is empty.")
    except OSError as error:
        raise ValueError(f"Cannot read image file: {error}") from error

    return str(image_path.resolve())
