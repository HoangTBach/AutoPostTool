import zipfile
from copy import copy

from datetime import datetime
from pathlib import Path
import traceback as traceback_module

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.utils.exceptions import InvalidFileException

from src.configs.path import DEVLOG_DIR, RESULT_DIR

RESULT_HEADERS = [
    "_task_id",
    "post_order",
    "via_name",
    "page_name",
    "caption",
    "image",
    "comment",
    "post_status",
    "published_at",
    "post_url",
    "post_attempt_count",
    "post_retryable",
    "error",
    "page_status",
    "page_attempt_count",
    "page_ready_at",
    "page_error",
    "page_link",
    "page_retryable",
]

POST_RESULT_HEADERS = ("post_attempt_count", "post_retryable")

PAGE_RESULT_HEADERS = (
    "page_status",
    "page_attempt_count",
    "page_ready_at",
    "page_error",
    "page_link",
    "page_retryable",
)

DEVLOG_HEADERS = [
    "timestamp",
    "run_id",
    "post_order",
    "via_id",
    "profile_id",
    "page_id",
    "action",
    "status",
    "attempt",
    "error_type",
    "error_message",
    "traceback",
    "retryable",
]


# ----- Excel Report Styling -----
try:
    from src.themes.color import COLORS
except ImportError:
    # Fallback palette matching the application's theme tokens.
    COLORS = {
        "neutral": {"black": "#000000"},
        "slate": {
            50: "#F8FAFC",
            200: "#E2E8F0",
            800: "#1E293B",
            900: "#0F172A",
        },
        "blue": {50: "#EFF6FF", 300: "#93C5FD", 600: "#2563EB"},
        "emerald": {50: "#ECFDF5"},
        "green": {600: "#16A34A"},
        "red": {100: "#FEE2E2", 600: "#DC2626"},
        "amber": {50: "#FFFBEB", 600: "#D97706"},
    }

_HEADER_FILL = PatternFill(
    "solid",
    fgColor=COLORS["blue"][300].lstrip("#"),
)
_STATUS_COLORS = {
    "Published": (COLORS["emerald"][50], COLORS["green"][600]),
    "Done": (COLORS["emerald"][50], COLORS["green"][600]),
    "Captured": (COLORS["emerald"][50], COLORS["green"][600]),
    "Failed": (COLORS["red"][100], COLORS["red"][600]),
    "Error": (COLORS["red"][100], COLORS["red"][600]),
    "Unknown": (COLORS["amber"][50], COLORS["amber"][600]),
    "Running": (COLORS["blue"][50], COLORS["blue"][600]),
    "Started": (COLORS["blue"][50], COLORS["blue"][600]),
    "Skipped": (COLORS["slate"][200], COLORS["slate"][800]),
    "Stopped": (COLORS["slate"][200], COLORS["slate"][800]),
    "SUCCESS": (COLORS["emerald"][50], COLORS["green"][600]),
    "FAILED": (COLORS["red"][100], COLORS["red"][600]),
    "RUNNING": (COLORS["blue"][50], COLORS["blue"][600]),
    "PENDING": (COLORS["slate"][200], COLORS["slate"][800]),
    "INTERRUPTED": (COLORS["amber"][50], COLORS["amber"][600]),
    "Success": (COLORS["emerald"][50], COLORS["green"][600]),
    "Verified": (COLORS["emerald"][50], COLORS["green"][600]),
    "Sending": (COLORS["blue"][50], COLORS["blue"][600]),
    "Preparing": (COLORS["blue"][50], COLORS["blue"][600]),
    "Retrying": (COLORS["amber"][50], COLORS["amber"][600]),
    "Interrupted": (COLORS["amber"][50], COLORS["amber"][600]),
}

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
    "post_attempt_count": 20,
    "post_retryable": 18,
    "error": 55,
    "page_status": 16,
    "page_attempt_count": 18,
    "page_ready_at": 23,
    "page_error": 55,
    "page_link": 52,
    "page_retryable": 15,
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


def _font_with(cell, *, bold=None, color=None):
    """Keep the legacy report font while adjusting status emphasis."""
    font = copy(cell.font)
    if bold is not None:
        font.bold = bold
    if color is not None:
        font.color = color.lstrip("#")
    cell.font = font


def _style_data_row(
    sheet,
    row_index: int,
    status_header: str | tuple[str, ...],
) -> None:
    """Apply the previous report's plain rows and centered status values."""
    headers = {str(cell.value): cell.column for cell in sheet[1] if cell.value}
    status_headers = (
        {status_header}
        if isinstance(status_header, str)
        else set(status_header)
    )
    centered_headers = {
        "post_order", "attempt", "retryable", "published_at",
        "timestamp", "post_status", "status", "page_status",
        "post_attempt_count", "post_retryable", "page_attempt_count",
        "page_retryable", "page_ready_at",
    }

    sheet.row_dimensions[row_index].height = 15.75
    for cell in sheet[row_index]:
        header = str(sheet.cell(1, cell.column).value or "")
        # Match the old workbook: plain rows, no alternating fills or borders.
        cell.fill = PatternFill(fill_type=None)
        cell.border = Border()
        cell.font = Font(name="Calibri", size=11, color="000000")
        cell.alignment = Alignment(
            vertical="center",
            horizontal="center" if header in centered_headers else "left",
            wrap_text=True,
        )
        if header in {"timestamp", "published_at", "page_ready_at"}:
            cell.number_format = "dd/mm/yyyy hh:mm:ss"

        # Keep the newer report's clickable post link without changing the
        # legacy font, fill, and alignment.
        if header == "post_url":
            url = str(cell.value or "").strip()
            if url.startswith(("https://", "http://")):
                cell.hyperlink = url
            elif cell.hyperlink is not None:
                cell.hyperlink = None

    for header in status_headers:
        index = headers.get(header)
        if not index:
            continue
        cell = sheet.cell(row_index, index)
        colors = _STATUS_COLORS.get(str(cell.value or ""))
        if colors:
            _font_with(cell, bold=True, color=colors[1])
            cell.alignment = Alignment(
                vertical="center", horizontal="center", wrap_text=True
            )


def _style_worksheet(sheet, widths: dict, status_header: str | tuple[str, ...]) -> None:
    """Reproduce the old Results/DevLog presentation, not RUN_STATE."""
    if sheet.max_column < 1:
        return

    sheet.sheet_view.showGridLines = True
    sheet.freeze_panes = "A2"
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    sheet.sheet_view.zoomScale = 90
    sheet.row_dimensions[1].height = 15.75

    for cell in sheet[1]:
        cell.fill = _HEADER_FILL
        cell.font = Font(name="Calibri", size=11, bold=True, color="000000")
        cell.border = Border()
        cell.alignment = Alignment(
            vertical="center", horizontal="center", wrap_text=True
        )

    for column_index in range(1, sheet.max_column + 1):
        header = str(sheet.cell(1, column_index).value or "")
        width_key = "media" if header == "image" else header
        sheet.column_dimensions[get_column_letter(column_index)].width = widths.get(
            width_key, 18
        )
        if header == "error" or column_index == 11:
            sheet.column_dimensions[get_column_letter(column_index)].hidden = False

    # The original report used no AutoFilter and showed grid lines.
    sheet.auto_filter.ref = None
    sheet.auto_filter.filterColumn = []

    for row_index in range(2, sheet.max_row + 1):
        _style_data_row(sheet, row_index, status_header)


def _format_workbook(
    path: Path, sheet_name: str, widths: dict, status_header: str | tuple[str, ...]
) -> None:
    workbook = load_workbook(path)
    try:
        if sheet_name in workbook.sheetnames:
            _style_worksheet(workbook[sheet_name], widths, status_header)
            workbook.save(path)
    finally:
        workbook.close()


def _is_workbook_valid(
    path: Path,
    required_sheet: str | None = None,
) -> bool:
    if not path.is_file():
        return False

    workbook = None

    try:
        workbook = load_workbook(
            path,
            read_only=True,
            data_only=True,
        )

        return required_sheet is None or required_sheet in workbook.sheetnames
    except (
        zipfile.BadZipFile,
        InvalidFileException,
        EOFError,
        KeyError,
    ):
        return False
    finally:
        if workbook is not None:
            workbook.close()


def _backup_invalid_file(path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = path.with_name(f"{path.stem}.invalid_{timestamp}{path.suffix}")

    counter = 1

    while backup_path.exists():
        backup_path = path.with_name(
            f"{path.stem}.invalid_{timestamp}_{counter}{path.suffix}"
        )
        counter += 1

    path.replace(backup_path)
    return backup_path


def _set_excel_value(sheet, row_index: int, column_index: int, value) -> None:
    """Write user-controlled data as text instead of Excel formulas."""
    cell = sheet.cell(row_index, column_index, value)
    if isinstance(value, str) and value.startswith("="):
        cell.data_type = "s"


def _now():
    return datetime.now().astimezone().replace(tzinfo=None)


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


class PageAutoReport:
    def __init__(self):
        self.devlog_path = Path(DEVLOG_DIR) / "PageAuto_DevLog.xlsx"
        self.result_path = Path(RESULT_DIR) / "PageAuto_Result.xlsx"

        self._ensure_result_file()
        self._ensure_result_columns()
        self._ensure_devlog_file()

        # Apply formatting to both existing and newly-created workbooks.
        _format_workbook(
            self.result_path,
            "Results",
            _RESULT_WIDTHS,
            ("post_status", "page_status"),
        )
        _format_workbook(
            self.devlog_path,
            "DevLog",
            _DEVLOG_WIDTHS,
            "status",
        )

        self.results = self._read_results()

    def _ensure_result_file(self):
        self.result_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        if self.result_path.exists():
            if not self.result_path.is_file():
                raise RuntimeError(f"Result path is not a file: {self.result_path}")

            if not _is_workbook_valid(
                self.result_path,
                required_sheet="Results",
            ):
                _backup_invalid_file(self.result_path)

        if self.result_path.exists():
            return

        workbook = Workbook()

        try:
            sheet = workbook.active
            sheet.title = "Results"
            sheet.append(RESULT_HEADERS)
            workbook.save(self.result_path)
        finally:
            workbook.close()

    def _ensure_result_columns(self) -> None:
        """Add Page-switch columns without changing existing posting history."""
        workbook = load_workbook(self.result_path)

        try:
            sheet = workbook["Results"]
            headers = [cell.value for cell in sheet[1]]
            next_column = max(
                (index for index, header in enumerate(headers, start=1) if header),
                default=0,
            ) + 1
            changed = False

            for header in (*PAGE_RESULT_HEADERS, *POST_RESULT_HEADERS):
                if header not in headers:
                    sheet.cell(1, next_column, header)
                    headers.append(header)
                    next_column += 1
                    changed = True

            if changed:
                workbook.save(self.result_path)
        finally:
            workbook.close()

    def _ensure_devlog_file(self):
        self.devlog_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        if self.devlog_path.exists():
            if not self.devlog_path.is_file():
                raise RuntimeError(f"DevLog path is not a file: {self.devlog_path}")

            if not _is_workbook_valid(self.devlog_path):
                _backup_invalid_file(self.devlog_path)

        if self.devlog_path.exists():
            workbook = load_workbook(self.devlog_path)

            try:
                if "DevLog" not in workbook.sheetnames:
                    workbook.create_sheet("DevLog").append(DEVLOG_HEADERS)

                if "RUN_STATE" not in workbook.sheetnames:
                    workbook.create_sheet("RUN_STATE").append(["key", "value"])

                workbook.save(self.devlog_path)
            finally:
                workbook.close()

            return

        workbook = Workbook()

        try:
            sheet = workbook.active
            sheet.title = "DevLog"
            sheet.append(DEVLOG_HEADERS)

            state = workbook.create_sheet("RUN_STATE")
            state.append(["key", "value"])

            workbook.save(self.devlog_path)
        finally:
            workbook.close()

    def _read_results(self) -> dict:
        workbook = load_workbook(
            self.result_path,
            read_only=True,
            data_only=True,
        )

        try:
            sheet = workbook["Results"]
            headers = [cell.value for cell in sheet[1]]
            positions = {name: index for index, name in enumerate(headers)}
            results = {}

            for values in sheet.iter_rows(min_row=2, values_only=True):
                task_id = (
                    values[positions["_task_id"]] if "_task_id" in positions else None
                )

                if not task_id:
                    continue

                def value(header: str, default=None):
                    index = positions.get(header)
                    return values[index] if index is not None else default

                results[str(task_id)] = {
                    "post_status": value("post_status", ""),
                    "published_at": value("published_at"),
                    "post_url": value("post_url", ""),
                    "post_attempt_count": value("post_attempt_count", 0) or 0,
                    "post_retryable": _as_bool(value("post_retryable", False)),
                    "error": value("error", ""),
                    "page_name": value("page_name", ""),
                    "page_link": value("page_link", ""),
                    "page_status": value("page_status", ""),
                    "page_attempt_count": value("page_attempt_count", 0) or 0,
                    "page_ready_at": value("page_ready_at"),
                    "page_error": value("page_error", ""),
                    "page_retryable": _as_bool(value("page_retryable", False)),
                }

            return results
        finally:
            workbook.close()

    def get_result(self, task_id: str) -> dict:
        return self.results.get(str(task_id), {}).copy()

    def upsert_result(
        self,
        row: dict,
        status: str,
        published_at=None,
        post_url="",
        error="",
        attempt: int | None = None,
        retryable: bool = False,
    ) -> None:
        task_id = str(row.get("task_id") or "")
        if not task_id:
            raise ValueError("Cannot save a result without task_id.")

        workbook = load_workbook(self.result_path)

        try:
            sheet = workbook["Results"]
            headers = [cell.value for cell in sheet[1]]

            if "_task_id" not in headers:
                raise ValueError("PageAuto_Result.xlsx is missing the _task_id column.")

            task_column = headers.index("_task_id") + 1
            target_row = None

            for row_index in range(2, sheet.max_row + 1):
                value = sheet.cell(row_index, task_column).value
                if str(value or "") == task_id:
                    target_row = row_index
                    break

            if target_row is None:
                target_row = sheet.max_row + 1

            comment = str(row.get("comment") or "").strip()
            if not comment:
                comment = "No comment (skipped)"

            values = {
                "_task_id": task_id,
                "post_order": row.get("post_order"),
                "via_name": row.get("via_name", ""),
                "page_name": row.get("page", row.get("page_name", "")),
                "caption": row.get("caption", ""),
                "image": row.get("image", row.get("media", "")),
                "media": row.get("media", row.get("image", "")),
                "comment": comment,
                "post_status": status,
                "post_attempt_count": int(attempt or 0),
                "post_retryable": bool(retryable),
                "published_at": published_at,
                "post_url": post_url or "",
                "error": error or "",
            }

            for column, header in enumerate(headers, start=1):
                if header in values:
                    _set_excel_value(sheet, target_row, column, values[header])

            _style_data_row(sheet, target_row, "post_status")

            workbook.save(self.result_path)

            result = self.results.setdefault(task_id, {})
            result.update(
                {
                    "post_status": status,
                    "post_attempt_count": int(attempt or 0),
                    "post_retryable": bool(retryable),
                    "published_at": published_at,
                    "post_url": post_url or "",
                    "error": error or "",
                }
            )
        finally:
            workbook.close()

    def upsert_page_result(
        self,
        row: dict,
        status: str,
        attempt: int = 0,
        error: str = "",
        retryable: bool = False,
        ready_at=None,
    ) -> None:
        """Save Page-switch progress without touching post_status or post history."""
        task_id = str(row.get("task_id") or "").strip()
        if not task_id:
            raise ValueError("Cannot save a Page result without task_id.")

        page_name = str(row.get("page_name") or row.get("page") or "").strip()
        page_link = str(row.get("page_link") or "").strip()
        media = str(row.get("media") or row.get("image") or "").strip()
        comment = str(row.get("comment") or "").strip() or "No comment (skipped)"
        status = str(status or "").strip().upper()

        if status not in {
            "PENDING",
            "RUNNING",
            "SUCCESS",
            "FAILED",
            "INTERRUPTED",
        }:
            raise ValueError(f"Invalid Page status: {status}")

        if status == "SUCCESS" and ready_at is None:
            ready_at = _now()
        elif status != "SUCCESS":
            ready_at = None

        workbook = load_workbook(self.result_path)

        try:
            sheet = workbook["Results"]
            headers = [cell.value for cell in sheet[1]]
            positions = {header: index + 1 for index, header in enumerate(headers)}

            if "_task_id" not in positions:
                raise ValueError("PageAuto_Result.xlsx is missing the _task_id column.")

            target_row = None
            task_column = positions["_task_id"]

            for row_index in range(2, sheet.max_row + 1):
                if str(sheet.cell(row_index, task_column).value or "") == task_id:
                    target_row = row_index
                    break

            if target_row is None:
                target_row = sheet.max_row + 1

            values = {
                "_task_id": task_id,
                "post_order": row.get("post_order"),
                "via_name": row.get("via_name", ""),
                "page_name": page_name,
                "caption": row.get("caption", ""),
                "image": media,
                "media": media,
                "comment": comment,
                "page_link": page_link,
                "page_status": status,
                "page_attempt_count": max(
                    0,
                    int(attempt or 0),
                ),
                "page_ready_at": ready_at,
                "page_error": str(error or ""),
                "page_retryable": bool(retryable),
            }

            for header, value in values.items():
                column = positions.get(header)
                if column is not None:
                    _set_excel_value(sheet, target_row, column, value)

            _style_data_row(sheet, target_row, ("post_status", "page_status"))
            workbook.save(self.result_path)

            result = self.results.setdefault(
                task_id,
                {
                    "post_status": "",
                    "published_at": None,
                    "post_url": "",
                    "error": "",
                },
            )
            result.update(
                {
                    "page_name": page_name,
                    "page_link": page_link,
                    "page_status": status,
                    "page_attempt_count": max(
                        0,
                        int(attempt or 0),
                    ),
                    "page_ready_at": ready_at,
                    "page_error": str(error or ""),
                    "page_retryable": bool(retryable),
                }
            )
        finally:
            workbook.close()

    def log_event(
        self,
        row: dict,
        run_id: str,
        action: str,
        status: str,
        attempt: int = 0,
        error=None,
        retryable: bool = False,
    ) -> None:
        error_type = type(error).__name__ if error else ""
        error_message = str(error) if error else ""
        trace = ""

        if error:
            trace = "".join(
                traceback_module.format_exception(
                    type(error),
                    error,
                    error.__traceback__,
                )
            )

        values = [
            _now(),
            run_id,
            row.get("post_order"),
            row.get("via_id", ""),
            row.get("profile_id", ""),
            row.get("page_id", ""),
            action,
            status,
            attempt,
            error_type,
            error_message,
            trace,
            retryable,
        ]

        workbook = load_workbook(self.devlog_path)

        try:
            sheet = workbook["DevLog"]
            sheet.append(values)
            for column_index, value in enumerate(values, start=1):
                if isinstance(value, str) and value.startswith("="):
                    sheet.cell(sheet.max_row, column_index).data_type = "s"
            _style_data_row(sheet, sheet.max_row, "status")
            workbook.save(self.devlog_path)
        finally:
            workbook.close()

    def next_attempt(self, row: dict) -> int:
        action = f"publish:{row.get('post_id', '')}"

        workbook = load_workbook(
            self.devlog_path,
            read_only=True,
            data_only=True,
        )

        try:
            sheet = workbook["DevLog"]
            headers = [cell.value for cell in sheet[1]]
            action_index = headers.index("action")
            attempt_index = headers.index("attempt")
            highest = 0

            for values in sheet.iter_rows(min_row=2, values_only=True):
                if values[action_index] != action:
                    continue

                try:
                    highest = max(
                        highest,
                        int(values[attempt_index] or 0),
                    )
                except (TypeError, ValueError):
                    pass

            return highest + 1
        finally:
            workbook.close()

    def get_state(self) -> dict:
        workbook = load_workbook(
            self.devlog_path,
            read_only=True,
            data_only=True,
        )

        try:
            sheet = workbook["RUN_STATE"]
            return {
                str(key): value
                for key, value in sheet.iter_rows(
                    min_row=2,
                    values_only=True,
                )
                if key
            }
        finally:
            workbook.close()

    def set_state(self, state: dict) -> None:
        workbook = load_workbook(self.devlog_path)

        try:
            sheet = workbook["RUN_STATE"]
            current_rows = {}

            for row_index in range(2, sheet.max_row + 1):
                key = sheet.cell(row_index, 1).value
                if key:
                    current_rows[str(key)] = row_index

            for key, value in state.items():
                row_index = current_rows.get(key)

                if row_index is None:
                    row_index = sheet.max_row + 1

                sheet.cell(row_index, 1, key)
                sheet.cell(row_index, 2, value)

            workbook.save(self.devlog_path)
        finally:
            workbook.close()