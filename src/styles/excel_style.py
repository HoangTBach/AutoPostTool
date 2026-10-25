from copy import copy

from openpyxl.styles import PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from src.themes.color import COLORS


# ----- Header -----
def _to_argb(color: str) -> str:
    value = color.strip().lstrip("#")

    if len(value) == 6:
        return f"FF{value.upper()}"

    if len(value) == 8:
        return value.upper()

    raise ValueError(f"Invalid HEX color: {color!r}")


_HEADER_FILL = PatternFill(
    fill_type="solid",
    fgColor=_to_argb(COLORS["blue"][300]),
)

_NO_FILL = PatternFill()


# ----- Status font colors -----
_STATUS_COLORS = {
    "published": COLORS["green"][600],
    "done": COLORS["green"][600],
    "captured": COLORS["green"][600],
    "success": COLORS["green"][600],
    "failed": COLORS["red"][600],
    "error": COLORS["red"][600],
    "unknown": COLORS["amber"][600],
    "running": COLORS["blue"][600],
    "started": COLORS["blue"][600],
    "skipped": COLORS["slate"][800],
    "stopped": COLORS["slate"][800],
    "queued": COLORS["slate"][800],
    "pending": COLORS["slate"][800],
}


# ----- Column widths -----
_RESULT_WIDTHS = {
    "_task_id": 18,
    "post_order": 13,
    "via_name": 23,
    "page_name": 28,
    "caption": 65,
    "media": 52,
    "comment": 48,
    "post_status": 17,
    "published_at": 23,
    "post_url": 52,
    "error": 55,
}

_DEVLOG_WIDTHS = {
    "timestamp": 23,
    "run_id": 40,
    "post_order": 13,
    "via_id": 18,
    "profile_id": 18,
    "page_id": 18,
    "action": 29,
    "status": 17,
    "attempt": 12,
    "error_type": 25,
    "error_message": 70,
    "traceback": 90,
    "retryable": 14,
}


# ----- Text wrapping -----
_WRAP_HEADERS = {
    "caption",
    "media",
    "comment",
    "post_url",
    "error",
    "error_message",
    "traceback",
}


def _style_data_row(
    sheet: Worksheet,
    row_index: int,
    headers: list,
    status_header: str,
) -> None:
    status_header_key = str(status_header or "").strip().lower()

    for column_index, header in enumerate(headers, start=1):
        header_key = str(header or "").strip().lower()

        cell = sheet.cell(
            row=row_index,
            column=column_index,
        )

        # Wrap long text.
        if header_key in _WRAP_HEADERS:
            alignment = copy(cell.alignment)
            alignment.wrap_text = True
            alignment.vertical = "top"
            cell.alignment = alignment

        # Status: change font color only, no background fill.
        if header_key == status_header_key:
            status = str(cell.value or "").strip().lower()

            status_color = _STATUS_COLORS.get(
                status,
                COLORS["neutral"]["black"],
            )

            cell.fill = copy(_NO_FILL)

            font = copy(cell.font)
            font.color = _to_argb(status_color)
            cell.font = font

            alignment = copy(cell.alignment)
            alignment.horizontal = "center"
            alignment.vertical = "center"
            cell.alignment = alignment


def _style_sheet(
    sheet: Worksheet,
    widths: dict,
    status_header: str,
) -> None:
    headers = [cell.value for cell in sheet[1]]

    for column_index, header in enumerate(headers, start=1):
        header_key = str(header or "").strip().lower()

        cell = sheet.cell(
            row=1,
            column=column_index,
        )

        cell.fill = copy(_HEADER_FILL)

        font = copy(cell.font)
        font.bold = True
        cell.font = font

        alignment = copy(cell.alignment)
        alignment.horizontal = "center"
        alignment.vertical = "center"
        alignment.wrap_text = True
        cell.alignment = alignment

        # Column width.
        width = widths.get(header_key)

        if width is not None:
            column_letter = get_column_letter(column_index)
            sheet.column_dimensions[column_letter].width = width

    sheet.freeze_panes = "A2"

    for row_index in range(2, sheet.max_row + 1):
        _style_data_row(
            sheet,
            row_index,
            headers,
            status_header,
        )


def style_result_sheet(sheet: Worksheet) -> None:
    _style_sheet(
        sheet=sheet,
        widths=_RESULT_WIDTHS,
        status_header="post_status",
    )


def style_devlog_sheet(sheet: Worksheet) -> None:
    _style_sheet(
        sheet=sheet,
        widths=_DEVLOG_WIDTHS,
        status_header="status",
    )


def style_result_row(
    sheet: Worksheet,
    row_index: int,
) -> None:
    headers = [cell.value for cell in sheet[1]]

    _style_data_row(
        sheet,
        row_index,
        headers,
        status_header="post_status",
    )


def style_devlog_row(
    sheet: Worksheet,
    row_index: int,
) -> None:
    headers = [cell.value for cell in sheet[1]]

    _style_data_row(
        sheet,
        row_index,
        headers,
        status_header="status",
    )
