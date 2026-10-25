from src.features.page_posting.helper import clean_value, get_id_number, get_number

REQUIRE_ACTIVE_STATUS = False


# ----- Jobs -----
def build_page_jobs(rows: list[dict]) -> list[dict]:
    grouped = {}
    seen_task_keys = set()
    duplicates = []

    for source_row in rows:
        if not isinstance(source_row, dict) or not _is_valid_row(source_row):
            continue

        row = source_row.copy()
        post_order = get_number(row.get("post_order"))
        via_id = clean_value(row.get("via_id"))
        page_id = clean_value(row.get("page_id"))
        post_id = clean_value(row.get("post_id"))
        profile_id = clean_value(row.get("profile_id"))

        row["post_order"] = post_order
        row["via_id"] = via_id
        row["page_id"] = page_id
        row["post_id"] = post_id

        task_id = clean_value(row.get("task_id"))
        if task_id:
            task_key = ("task_id", task_id)
        else:
            task_key = (
                "row",
                post_id,
                profile_id,
                via_id,
                page_id,
            )

        if task_key in seen_task_keys:
            duplicates.append(task_id or f"{post_id} / {page_id} / order {post_order}")
            continue

        seen_task_keys.add(task_key)

        order_group = grouped.setdefault(post_order, {})
        via_group = order_group.setdefault(via_id, [])
        via_group.append(row)

    if duplicates:
        duplicate_text = ", ".join(duplicates[:10])
        if len(duplicates) > 10:
            duplicate_text += f" (+{len(duplicates) - 10} more)"

        raise ValueError(f"Duplicate Page Auto tasks found: {duplicate_text}")

    jobs = []

    for post_order in sorted(grouped):
        via_groups = grouped[post_order]
        via_ids = sorted(
            via_groups,
            key=lambda via_id: (
                get_id_number(via_id),
                via_id,
            ),
        )

        for via_id in via_ids:
            page_rows = sorted(
                via_groups[via_id],
                key=lambda row: (
                    get_id_number(row.get("page_id")),
                    clean_value(row.get("page_id")),
                    clean_value(row.get("post_id")),
                ),
            )

            jobs.append(
                {
                    "post_order": post_order,
                    "via_id": via_id,
                    "rows": page_rows,
                }
            )

    return jobs


# ----- Rows -----
def flatten_page_jobs(jobs: list[dict]) -> list[dict]:
    rows = []

    for job in jobs:
        rows.extend(job["rows"])

    for index, row in enumerate(rows, start=1):
        row["no"] = index

    return rows


# ----- Filter -----
def _is_valid_row(row: dict) -> bool:
    post_order = get_number(row.get("post_order"))

    if post_order is None or post_order <= 0:
        return False

    if not clean_value(row.get("post_id")):
        return False

    if not clean_value(row.get("profile_id")):
        return False

    if not clean_value(row.get("via_id")):
        return False

    if not clean_value(row.get("page_id")):
        return False

    if not REQUIRE_ACTIVE_STATUS:
        return True

    profile_status = clean_value(row.get("profile_status")).upper()
    page_status = clean_value(row.get("page_status")).upper()

    return profile_status == "ACTIVE" and page_status == "ACTIVE"
