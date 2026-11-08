import re
from pathlib import Path
from urllib.parse import urlparse

from src.utils.cmd_log import cmd_log

# ----- Media Formats -----
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
PROJECT_ROOT = Path(__file__).resolve().parents[3]


# ----- Errors -----
class PageAutoValidationError(ValueError):
    pass


# ----- Helpers -----
def _clean(value) -> str:
    return str(value or "").strip()


def _parse_post_order(value) -> int | None:
    if value is None or isinstance(value, bool):
        return None

    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return None

    if not number.is_integer() or number < 1:
        return None

    return int(number)


def _resolve_media_path(value, media_root=None) -> Path:
    path = Path(_clean(value)).expanduser()

    if path.is_absolute():
        return path.resolve()

    root = Path(media_root).expanduser() if media_root else PROJECT_ROOT

    if not root.is_absolute():
        root = PROJECT_ROOT / root

    return (root / path).resolve()


def _is_facebook_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
        hostname = (parsed.hostname or "").lower()
    except ValueError:
        return False

    is_facebook_domain = hostname == "facebook.com" or hostname.endswith(
        ".facebook.com"
    )

    return parsed.scheme in {"http", "https"} and is_facebook_domain


def _row_label(row: dict, index: int) -> str:
    post_id = _clean(row.get("post_id"))
    page_id = _clean(row.get("page_id"))

    details = []

    if post_id:
        details.append(f"post_id={post_id}")

    if page_id:
        details.append(f"page_id={page_id}")

    suffix = f" ({', '.join(details)})" if details else ""
    return f"Row {row.get('_excel_row') or index}{suffix}"


# ----- Validate One Row -----
def validate_row(row: dict, media_root=None) -> dict:
    if not isinstance(row, dict):
        raise PageAutoValidationError("Row data must be a dictionary.")

    errors = []

    raw_load_errors = row.get("_load_errors") or []
    if isinstance(raw_load_errors, str):
        raw_load_errors = [raw_load_errors]

    load_errors = [_clean(message) for message in raw_load_errors if _clean(message)]
    errors.extend(load_errors)

    post_id = _clean(row.get("post_id"))
    page_id = _clean(row.get("page_id"))
    via_id = _clean(row.get("via_id"))
    profile_id = _clean(row.get("profile_id"))
    profile_uid = _clean(row.get("profile_uid"))
    page_name = _clean(row.get("page_name") or row.get("page"))
    page_link = _clean(row.get("page_link"))
    caption = _clean(row.get("caption"))
    media_value = _clean(row.get("media"))
    post_order = _parse_post_order(row.get("post_order"))

    page_found = bool(row.get("_page_found", True))
    via_found = bool(row.get("_via_found", True))
    profile_found = bool(row.get("_profile_found", True))

    if not post_id:
        errors.append("post_id is missing.")

    if not page_id:
        errors.append("page_id is missing.")

    if page_found:
        if not via_id:
            errors.append("Page-to-Via mapping is missing.")
        elif not via_found:
            if not any("via_id" in message.lower() for message in load_errors):
                errors.append("Page-to-Via mapping is invalid.")
        elif not profile_id:
            errors.append("Via-to-AdsPower profile mapping is missing.")
        elif not profile_found:
            if not any("profile_id" in message.lower() for message in load_errors):
                errors.append("Via references an unknown AdsPower profile.")
        elif not profile_uid:
            errors.append("AdsPower profile UID is missing.")

        if not page_name:
            errors.append("Page name is missing.")

        if not page_link or not _is_facebook_url(page_link):
            errors.append("A valid Facebook Page URL is required.")

    if post_order is None:
        errors.append("post_order must be a positive integer.")

    if not caption:
        errors.append("Caption is required.")

    if not media_value:
        errors.append("Media file path is required.")

    media_path = None

    if media_value:
        try:
            media_path = _resolve_media_path(
                media_value,
                media_root=media_root,
            )

            if not media_path.is_file():
                errors.append(f"Media file does not exist: {media_path}")
            else:
                if media_path.suffix.lower() not in SUPPORTED_MEDIA_EXTENSIONS:
                    errors.append(f"Unsupported media format: {media_path.suffix}")

                if media_path.stat().st_size == 0:
                    errors.append(f"Media file is empty: {media_path}")
                else:
                    with media_path.open("rb") as media_file:
                        if not media_file.read(1):
                            errors.append(f"Media file is empty: {media_path}")

        except OSError as error:
            errors.append(f"Cannot read media file: {error}")
        except (TypeError, ValueError) as error:
            errors.append(f"Invalid media path: {error}")

    if errors:
        raise PageAutoValidationError(" ".join(errors))

    validated_row = dict(row)
    validated_row["post_order"] = post_order
    validated_row["page_name"] = page_name
    validated_row["_validated_media"] = str(media_path)

    return validated_row


def format_validation_errors(
    errors: list[str],
    limit: int = 3,
    one_line: bool = False,
) -> str:
    if not errors:
        return ""

    examples = []

    for error in errors[:limit]:
        message = " ".join(str(error).split())

        if len(message) > 180:
            message = message[:177] + "..."

        examples.append(message)

    remaining = len(errors) - len(examples)

    if one_line:
        message = f"Page Auto validation: {len(errors)} row(s) skipped."

        if examples:
            message += " Examples: " + " | ".join(examples)

        if remaining:
            message += f" | {remaining} more error(s) omitted."

        return message

    message = f"{len(errors)} row(s) skipped due to validation errors."

    if examples:
        message += "\n\nExamples:\n- " + "\n- ".join(examples)

    if remaining:
        message += f"\n... and {remaining} more error(s)."

    return message


# ----- Validate All Rows -----
def validate_page_rows(
    rows: list[dict],
    media_root=None,
    *,
    return_errors: bool = False,
) -> list[dict] | tuple[list[dict], list[str]]:
    if not rows:
        raise PageAutoValidationError("No Page Auto data was found in Excel.")

    validated_rows = []
    errors = []
    seen_task_ids = set()

    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            errors.append(f"Row {index}: Row data must be a dictionary.")
            continue

        label = _row_label(row, index)

        page_id = _clean(row.get("page_id"))
        post_order_value = _clean(row.get("post_order"))

        # Ignore captions that have not been selected.
        if not page_id and not post_order_value:
            continue

        # A selected post must have both assignment fields.
        if not page_id or not post_order_value:
            errors.append(
                f"{label}: page_id and post_order must both be "
                "filled or both be blank."
            )
            continue

        try:
            validated_row = validate_row(
                row,
                media_root=media_root,
            )
        except PageAutoValidationError as error:
            errors.append(f"{label}: {error}")
            continue

        task_id = _clean(validated_row.get("task_id"))

        if task_id and task_id in seen_task_ids:
            errors.append(f"{label}: Duplicate task_id: {task_id}")
            continue

        if task_id:
            seen_task_ids.add(task_id)

        validated_rows.append(validated_row)

    if errors:
        cmd_log(
            "WARNING",
            format_validation_errors(errors, one_line=True),
        )

    if return_errors:
        return validated_rows, errors

    return validated_rows


def _notification_reason(message: str) -> str:
    message = message.lower()

    if "page_id and post_order must both be filled" in message:
        return "Incomplete post assignment"

    if "was not found in page" in message:
        return "Invalid Page reference"

    if "via_id" in message and (
        "was not found in via" or "mapping is missing" or "mapping is invalid"
    ):
        return "Invalid Via mapping"

    if "profile_id" in message and "was not found in adspower" in message:
        return "Invalid AdsPower profile reference"

    if "post_id is missing" in message:
        return "Missing post ID"

    if "post_order must be a positive integer" in message:
        return "Invalid post order"

    return "Invalid Excel data"


def format_validation_notification(errors: list[str]) -> str:
    if not errors:
        return ""

    grouped = {}

    for error in errors:
        text = str(error).strip()
        match = re.search(r"\bpost_id=([^,)]+)", text, re.IGNORECASE)
        post_id = match.group(1).strip() if match else ""

        detail_match = re.search(r"\):\s*(.*)$", text)
        if detail_match:
            detail = detail_match.group(1).strip()
        else:
            _, separator, detail = text.partition(": ")
            if not separator:
                detail = text

        reason = _notification_reason(detail)
        grouped.setdefault(reason, []).append(post_id)

    reason, post_ids = max(grouped.items(), key=lambda item: len(item[1]))
    row_word = "row" if len(errors) == 1 else "rows"
    message = f"{len(errors)} {row_word} skipped: {reason}"

    visible_ids = list(dict.fromkeys(pid for pid in post_ids if pid))[:3]

    if visible_ids:
        ids_text = ", ".join(visible_ids)
        remaining = len(post_ids) - min(3, len(post_ids))

        if remaining > 0:
            ids_text += f" +{remaining}"

        message += f" ({ids_text})"

    other_count = len(errors) - len(post_ids)
    if other_count:
        message += f"; {other_count} other issue(s)"

    return message + "."


def format_import_error_notification(error: str) -> str:
    text = " ".join(str(error).split())
    lower_text = text.lower()

    if "no valid page auto jobs were created" in lower_text:
        reason = _notification_reason(text)

        count_match = re.search(
            r"\b(\d+)\s+(?:rows?|row\(s\)|validation errors?)",
            text,
            re.IGNORECASE,
        )

        if count_match:
            count = int(count_match.group(1))
        else:
            row_numbers = set(re.findall(r"\bRow\s+(\d+)\b", text, re.IGNORECASE))
            omitted_match = re.search(
                r"(?:\+)?(\d+)\s+more",
                text,
                re.IGNORECASE,
            )
            count = len(row_numbers)

            if omitted_match:
                count += int(omitted_match.group(1))

        if count:
            row_word = "row" if count == 1 else "rows"
            return f"{count} {row_word} skipped: {reason}."

        return f"Import failed: {reason}."

    if "no page auto jobs were created" in lower_text:
        return "No valid jobs. Check post_order, page_id, and via_id."

    return text[:117].rstrip() + "..." if len(text) > 120 else text
