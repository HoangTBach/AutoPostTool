import traceback as traceback_module
import zipfile
from copy import copy
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook, load_workbook  # type: ignore
from openpyxl.styles import Alignment, PatternFill  # type: ignore
from openpyxl.utils import get_column_letter  # type: ignore
from openpyxl.utils.exceptions import InvalidFileException  # type: ignore

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
    "error",
]

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
_HEADER_COLOR = COLORS.get("neutral", {}).get("black") or COLORS.get("slate", {}).get(
    900, "#0F172A"
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
}

_RESULT_WIDTHS = {
    "_task_id": 18,
    "post_order": 13,
    "via_name": 23,
    "page_name": 28,
    "caption": 65,
    "media": 52,
    "image": 52,
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


def _font_with(cell, *, bold=None, color=None):
    """Preserve the current font family and size while changing emphasis/color."""
    font = copy(cell.font)
    if bold is not None:
        font.bold = bold
    if color is not None:
        font.color = color.lstrip("#")
    cell.font = font


def _style_sheet(sheet, widths=None, status_column=None):
    """Apply the legacy report style without changing worksheet values."""
    widths = widths or {}
    sheet.sheet_view.showGridLines = True
    sheet.freeze_panes = "A2"
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    sheet.sheet_view.zoomScale = 90
    sheet.row_dimensions[1].height = 15.75

    for dimension in sheet.column_dimensions.values():
        if dimension.index == "K":
            dimension.hidden = False

    for cell in sheet[1]:
        cell.fill = _HEADER_FILL
        _font_with(cell, bold=True, color=_HEADER_COLOR)
        cell.alignment = Alignment(
            vertical="center",
            horizontal="center",
            wrap_text=True,
        )

    header_positions = {str(cell.value): cell.column for cell in sheet[1] if cell.value}

    for index, cell in enumerate(sheet[1], start=1):
        if cell.value is None:
            continue
        header = str(cell.value)
        width_key = "media" if header == "image" else header
        letter = get_column_letter(index)
        sheet.column_dimensions[letter].width = widths.get(width_key, 18)

    sheet.auto_filter.ref = None
    sheet.auto_filter.filterColumn = []
    status_index = header_positions.get(status_column) if status_column else None
    date_indices = {
        header_positions[name]
        for name in ("timestamp", "published_at")
        if name in header_positions
    }

    for row in sheet.iter_rows(min_row=2):
        sheet.row_dimensions[row[0].row].height = 15.75

        for cell in row:
            cell.alignment = Alignment(
                vertical="center",
                horizontal="left",
                wrap_text=True,
            )
            cell.fill = PatternFill(fill_type=None)

            header = str(sheet.cell(1, cell.column).value or "")
            if header in {
                "post_order",
                "attempt",
                "retryable",
                "published_at",
                "timestamp",
                "post_status",
                "status",
            }:
                cell.alignment = Alignment(
                    vertical="center",
                    horizontal="center",
                    wrap_text=True,
                )

            if cell.column in date_indices and isinstance(cell.value, datetime):
                cell.number_format = "dd/mm/yyyy hh:mm:ss"

        if status_index:
            status_cell = sheet.cell(row[0].row, status_index)
            colors = _STATUS_COLORS.get(str(status_cell.value or "").strip())
            if colors:
                _font_with(status_cell, bold=True, color=colors[1])
                status_cell.alignment = Alignment(
                    vertical="center",
                    horizontal="center",
                    wrap_text=True,
                )


def _format_workbook(
    path: Path,
    sheet_name: str,
    widths: dict,
    status_header: str | None = None,
) -> None:
    workbook = load_workbook(path)
    try:
        if sheet_name in workbook.sheetnames:
            _style_sheet(workbook[sheet_name], widths, status_header)
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


def _now():
    return datetime.now().astimezone().replace(tzinfo=None)


class PageAutoReport:
    def __init__(self):
        self.devlog_path = Path(DEVLOG_DIR) / "PageAuto_DevLog.xlsx"
        self.result_path = Path(RESULT_DIR) / "PageAuto_Result.xlsx"

        self._ensure_result_file()
        self._ensure_devlog_file()

        # Apply the legacy formatting to existing and newly-created workbooks.
        _format_workbook(
            self.result_path,
            "Results",
            _RESULT_WIDTHS,
            "post_status",
        )
        _format_workbook(
            self.devlog_path,
            "DevLog",
            _DEVLOG_WIDTHS,
            "status",
        )
        _format_workbook(
            self.devlog_path,
            "RUN_STATE",
            {"key": 32, "value": 42},
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

                results[str(task_id)] = {
                    "post_status": (
                        values[positions["post_status"]]
                        if "post_status" in positions
                        else ""
                    ),
                    "published_at": (
                        values[positions["published_at"]]
                        if "published_at" in positions
                        else None
                    ),
                    "post_url": (
                        values[positions["post_url"]] if "post_url" in positions else ""
                    ),
                    "error": (
                        values[positions["error"]] if "error" in positions else ""
                    ),
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
                "image": row.get("image", ""),
                "comment": comment,
                "post_status": status,
                "published_at": published_at,
                "post_url": post_url or "",
                "error": error or "",
            }

            for column, header in enumerate(headers, start=1):
                if header in values:
                    sheet.cell(target_row, column, values[header])

            _style_sheet(sheet, _RESULT_WIDTHS, "post_status")
            workbook.save(self.result_path)

            self.results[task_id] = {
                "post_status": status,
                "published_at": published_at,
                "post_url": post_url or "",
                "error": error or "",
            }
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
            _style_sheet(sheet, _DEVLOG_WIDTHS, "status")
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

            _style_sheet(sheet, {"key": 32, "value": 42})
            workbook.save(self.devlog_path)
        finally:
            workbook.close()
