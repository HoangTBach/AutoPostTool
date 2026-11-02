from pathlib import Path
import re

from openpyxl import load_workbook  # type: ignore

from src.configs.path import DATA_FILE
from src.utils.cmd_log import cmd_log

# ----- Required Columns -----
SHEET_COLUMNS = {
    "ADSPOWER": ("profile_id", "profile_uid", "profile_name"),
    "VIA": ("via_id", "via_name", "profile_id"),
    "PAGE": ("page_id", "page_name", "page_link", "via_id"),
    "PAGE_POST": (
        "post_id",
        "page_id",
        "post_order",
        "caption",
        "media",
        "comment",
    ),
}


# ----- File -----
def _resolve_data_path(file_path=None) -> Path:
    return Path(file_path or DATA_FILE).expanduser().resolve()


def get_data_file_stamp(file_path=None) -> tuple[int, int]:
    path = _resolve_data_path(file_path)

    if not path.is_file():
        raise FileNotFoundError(f"Excel file not found: {path}")

    stat = path.stat()
    return stat.st_mtime_ns, stat.st_size


# ----- Load -----
def load_page_rows(file_path=None) -> list[dict]:
    path = _resolve_data_path(file_path)

    cmd_log("INFO", f"Reading Excel file: {path}")

    if not path.is_file():
        raise FileNotFoundError(f"Excel file not found: {path}")

    workbook = load_workbook(
        path,
        read_only=True,
        data_only=True,
        keep_links=False,
    )

    try:
        sheets = {name.strip().upper(): workbook[name] for name in workbook.sheetnames}

        missing_sheets = [name for name in SHEET_COLUMNS if name not in sheets]

        if missing_sheets:
            raise ValueError(f"Missing required sheets: {', '.join(missing_sheets)}")

        data = {
            name: _sheet_to_dicts(
                sheets[name],
                columns,
                name == "PAGE_POST",
            )
            for name, columns in SHEET_COLUMNS.items()
        }

        profile_map = _build_map(data["ADSPOWER"], "profile_id", "ADSPOWER")
        via_map = _build_map(data["VIA"], "via_id", "VIA")
        page_map = _build_map(data["PAGE"], "page_id", "PAGE")
        posts = data["PAGE_POST"]

        if not posts:
            raise ValueError("PAGE_POST has no data rows.")

        selected_posts = [
            post for post in posts if post.get("page_id") or post.get("post_order")
        ]

        if not selected_posts:
            raise ValueError(
                "No selected posts found in PAGE_POST. "
                "Fill both page_id and post_order for the posts "
                "you want to publish."
            )

        rows = []
        seen_tasks = set()

        for post in posts:
            row_number = post["_row_number"]
            post_id = post["post_id"]
            page_id = post["page_id"]
            post_order = post["post_order"]

            # Skip captions that have not been selected.
            if not page_id and not post_order:
                continue

            load_errors = []

            page = page_map.get(page_id) if page_id else None
            page_found = page is not None

            if page_id and page is None:
                load_errors.append(f"page_id '{page_id}' was not found in PAGE.")

            via_id = page.get("via_id", "") if page else ""
            via = None
            via_found = False

            if page and via_id:
                via = via_map.get(via_id)
                via_found = via is not None

                if not via_found:
                    load_errors.append(
                        f"via_id '{via_id}' referenced by "
                        f"page_id '{page_id}' was not found in VIA."
                    )

            profile_id = via.get("profile_id", "") if via else ""
            profile = None
            profile_found = False

            if via and profile_id:
                profile = profile_map.get(profile_id)
                profile_found = profile is not None

                if not profile_found:
                    load_errors.append(
                        f"profile_id '{profile_id}' referenced by "
                        f"via_id '{via_id}' was not found in ADSPOWER."
                    )

            profile = profile or {}
            page_name = (page.get("page_name") or page_id) if page else ""

            task_id = f"{post_id}|{profile_id}|{via_id}|{page_id}"

            if task_id in seen_tasks:
                load_errors.append(
                    f"Duplicate task '{post_id}' for page_id '{page_id}'."
                )
            else:
                seen_tasks.add(task_id)

            rows.append(
                {
                    "task_id": task_id,
                    "post_id": post_id,
                    "page_id": page_id,
                    "post_order": post_order,
                    "caption": post["caption"],
                    "media": post["media"],
                    "comment": post["comment"],
                    "profile_id": profile_id,
                    "profile_uid": profile.get("profile_uid", ""),
                    "profile_name": profile.get("profile_name", ""),
                    "via_id": via_id,
                    "via_name": via.get("via_name", "") if via else "",
                    "page": page_name,
                    "page_name": page_name,
                    "page_link": page.get("page_link", "") if page else "",
                    "_excel_row": row_number,
                    "_load_errors": load_errors,
                    "_page_found": page_found,
                    "_via_found": via_found,
                    "_profile_found": profile_found,
                }
            )

        return rows

    finally:
        workbook.close()


# ----- Sheet -----
def _sheet_to_dicts(
    sheet,
    required_columns: tuple[str, ...],
    exact_columns: bool = False,
) -> list[dict]:
    header_row = list(
        next(
            sheet.iter_rows(min_row=1, max_row=1, values_only=True),
            (),
        )
    )

    while header_row and (header_row[-1] is None or not str(header_row[-1]).strip()):
        header_row.pop()

    if not header_row:
        raise ValueError(f"Sheet {sheet.title} has no header row.")

    headers = [_normalize_header(value) for value in header_row]

    if any(not header for header in headers):
        raise ValueError(f"Sheet {sheet.title} contains an empty column header.")

    if len(headers) != len(set(headers)):
        raise ValueError(f"Sheet {sheet.title} contains duplicate column headers.")

    missing = [column for column in required_columns if column not in headers]
    unexpected = [column for column in headers if column not in required_columns]

    if exact_columns and (missing or unexpected):
        details = []

        if missing:
            details.append(f"missing: {', '.join(missing)}")

        if unexpected:
            details.append(f"unexpected: {', '.join(unexpected)}")

        raise ValueError(
            f"Sheet {sheet.title} must contain exactly these columns: "
            f"{', '.join(required_columns)}. {'; '.join(details)}."
        )

    if missing:
        raise ValueError(
            f"Sheet {sheet.title} is missing required columns: "
            f"{', '.join(missing)}."
        )

    records = []

    for row_number, values in enumerate(
        sheet.iter_rows(min_row=2, values_only=True),
        start=2,
    ):
        values = list(values[: len(headers)])
        values.extend([""] * (len(headers) - len(values)))

        record = {header: _clean_value(value) for header, value in zip(headers, values)}

        if not any(record.values()):
            continue

        record["_row_number"] = row_number
        records.append(record)

    return records


# ----- Mapping -----
def _build_map(rows: list[dict], key: str, sheet_name: str) -> dict[str, dict]:
    result = {}

    for row in rows:
        value = row[key]
        row_number = row["_row_number"]

        if not value:
            continue

        if value in result:
            previous_row = result[value]["_row_number"]
            raise ValueError(
                f"{sheet_name} has duplicate {key} '{value}' "
                f"at rows {previous_row} and {row_number}."
            )

        result[value] = row

    return result


# ----- Value -----
def _normalize_header(value) -> str:
    return re.sub(r"\s+", "_", str(value or "").strip().lower())


def _clean_value(value) -> str:
    if value is None:
        return ""

    if isinstance(value, float) and value.is_integer():
        return str(int(value))

    return str(value).strip()


def _parse_post_order(value, row_number: int) -> int:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(
            f"PAGE_POST row {row_number}: " "post_order must be a positive integer."
        ) from None

    if not number.is_integer() or number < 1:
        raise ValueError(
            f"PAGE_POST row {row_number}: " "post_order must be a positive integer."
        )

    return int(number)
