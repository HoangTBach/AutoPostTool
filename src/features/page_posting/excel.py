from pathlib import Path

from openpyxl import load_workbook

# ----- Paths -----
ROOT_DIR = Path(__file__).resolve().parents[3]

DATA_FILE = ROOT_DIR / "data" / "Databook.xlsx"


# ----- Load Page Rows -----
def load_page_rows():
    if not DATA_FILE.exists():
        raise FileNotFoundError(f"Cannot find: {DATA_FILE}")

    workbook = load_workbook(
        DATA_FILE,
        data_only=True,
        read_only=True,
    )

    try:
        # ----- Sheets -----
        page_sheet = workbook["PAGE"]
        post_sheet = workbook["PAGE_POST"]

        pages = sheet_to_dicts(page_sheet)

        posts = sheet_to_dicts(post_sheet)

        # ----- Page Map -----
        page_map = {}

        for page in pages:
            page_id = clean_value(page.get("page_id"))

            if not page_id:
                continue

            page["_page_order"] = page["_row_order"]

            page_map[page_id] = page

        # ----- Build Rows -----
        rows = []

        for post in posts:
            page_id = clean_value(post.get("page_id"))

            if not page_id:
                continue

            if not has_post_data(post):
                continue

            page = page_map.get(page_id)

            if not page:
                continue

            post_id = clean_value(post.get("post_id"))

            # ----- Task ID -----
            task_id = create_task_id(
                post_id=post_id,
                page_id=page_id,
                row_order=post["_row_order"],
            )

            rows.append(
                {
                    "no": 0,
                    # ----- Task -----
                    "task_id": task_id,
                    # ----- Table Data -----
                    "page": (clean_value(page.get("page_name")) or page_id),
                    "caption": clean_value(post.get("caption")),
                    "image": clean_value(post.get("image")),
                    "comment": clean_value(post.get("comment")),
                    "status": "",
                    # ----- Page Data -----
                    "page_id": page_id,
                    "page_order": page["_page_order"],
                    "page_status": clean_value(page.get("status")),
                    "page_link": clean_value(page.get("page_link")),
                    "via_id": clean_value(page.get("via_id")),
                    # ----- Post Data -----
                    "post_id": post_id,
                    "post_order": get_order(post.get("post_order")),
                    # Chỉ dùng nội bộ để sort
                    "_post_row_order": post["_row_order"],
                }
            )

        rows.sort(
            key=lambda row: (
                row["post_order"],
                row["page_order"],
                row["_post_row_order"],
            )
        )

        # ----- Reset No -----
        for index, row in enumerate(
            rows,
            start=1,
        ):
            row["no"] = index

            row.pop(
                "_post_row_order",
                None,
            )

        return rows

    finally:
        workbook.close()


# ----- Sheet To Dicts -----
def sheet_to_dicts(sheet):
    values = sheet.iter_rows(values_only=True)

    try:
        headers = next(values)

    except StopIteration:
        return []

    # ----- Headers -----
    headers = [clean_value(header) for header in headers]

    data = []

    for row_order, values_row in enumerate(
        values,
        start=1,
    ):
        # ----- Skip Empty Row -----
        if not any(value is not None and str(value).strip() for value in values_row):
            continue

        row = {"_row_order": row_order}

        for index, header in enumerate(headers):
            if not header:
                continue

            value = values_row[index] if index < len(values_row) else None

            row[header] = value

        data.append(row)

    return data


# ----- Has Post Data -----
def has_post_data(post):
    fields = (
        "post_id",
        "caption",
        "image",
        "comment",
    )

    return any(clean_value(post.get(field)) for field in fields)


# ----- Create Task ID -----
def create_task_id(
    post_id: str,
    page_id: str,
    row_order: int,
):

    if post_id:
        return f"{post_id}|{page_id}"

    return f"ROW{row_order}|{page_id}"


# ----- Clean Value -----
def clean_value(value):
    if value is None:
        return ""

    return str(value).strip()


# ----- Get Order -----
def get_order(value):
    if value is None or value == "":
        return float("inf")

    try:
        return int(value)

    except (TypeError, ValueError):
        return float("inf")
