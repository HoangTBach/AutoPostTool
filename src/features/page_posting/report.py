import zipfile

from datetime import datetime
from pathlib import Path
import traceback as traceback_module

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
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
_HEADER_FONT = Font(
    name="Aptos",
    size=10,
    bold=True,
    color=COLORS["slate"][900].lstrip("#"),
)
_BODY_FONT = Font(
    name="Aptos",
    size=10,
    color=COLORS["slate"][800].lstrip("#"),
)
_HEADER_BORDER = Border(
    bottom=Side(
        style="medium",
        color=COLORS["blue"][600].lstrip("#"),
    ),
)
_BODY_BORDER = Border(
    bottom=Side(
        style="thin",
        color=COLORS["slate"][200].lstrip("#"),
    ),
)
_ALT_ROW_FILL = PatternFill(
    "solid",
    fgColor=COLORS["slate"][50].lstrip("#"),
)
_NO_FILL = PatternFill(fill_type=None)

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


def _style_data_row(sheet, row_index: int, status_header: str) -> None:
    headers = {
        str(cell.value): cell.column for cell in sheet[1] if cell.value is not None
    }
    status_column = headers.get(status_header)

    for cell in sheet[row_index]:
        cell.fill = _ALT_ROW_FILL if row_index % 2 == 0 else _NO_FILL
        cell.font = _BODY_FONT
        cell.alignment = Alignment(vertical="top", wrap_text=True)
        cell.border = _BODY_BORDER

        header = str(sheet.cell(1, cell.column).value or "")
        if header in {"timestamp", "published_at"} and isinstance(cell.value, datetime):
            cell.number_format = "yyyy-mm-dd hh:mm:ss"

        if header == "post_url":
            url = str(cell.value or "").strip()
            if url.startswith(("https://", "http://")):
                cell.hyperlink = url
                cell.font = Font(
                    name="Aptos",
                    size=10,
                    color=COLORS["blue"][600].lstrip("#"),
                    underline="single",
                )

    if status_column:
        status_cell = sheet.cell(row_index, status_column)
        status = str(status_cell.value or "").strip()
        status_colors = _STATUS_COLORS.get(status)
        if status_colors:
            # Keep the row's normal alternating background.
            # Status styling changes font color only, not the cell fill.
            _, font_color = status_colors
            status_cell.font = Font(
                name="Aptos",
                size=10,
                bold=True,
                color=font_color.lstrip("#"),
            )
            status_cell.alignment = Alignment(
                horizontal="center",
                vertical="center",
                wrap_text=True,
            )


def _style_worksheet(sheet, widths: dict, status_header: str) -> None:
    if sheet.max_column < 1:
        return

    sheet.sheet_view.showGridLines = False
    sheet.freeze_panes = "A2"

    headers = {
        str(cell.value): cell.column for cell in sheet[1] if cell.value is not None
    }

    for cell in sheet[1]:
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
        cell.alignment = Alignment(
            horizontal="center",
            vertical="center",
            wrap_text=True,
        )
        cell.border = _HEADER_BORDER

    sheet.row_dimensions[1].height = 30

    for column_index in range(1, sheet.max_column + 1):
        header = str(sheet.cell(1, column_index).value or "")
        width_key = "media" if header == "image" else header
        width = widths.get(width_key, max(14, min(len(header) + 4, 24)))
        column_letter = get_column_letter(column_index)
        sheet.column_dimensions[column_letter].width = width

        if header == "error":
            sheet.column_dimensions[column_letter].hidden = False

    for row_index in range(2, sheet.max_row + 1):
        _style_data_row(sheet, row_index, status_header)

    if sheet.max_row >= 1:
        sheet.auto_filter.ref = (
            f"A1:{get_column_letter(sheet.max_column)}{sheet.max_row}"
        )


def _format_workbook(
    path: Path, sheet_name: str, widths: dict, status_header: str
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


def _now():
    return datetime.now().astimezone().replace(tzinfo=None)


class PageAutoReport:
    def __init__(self):
        self.devlog_path = Path(DEVLOG_DIR) / "PageAuto_DevLog.xlsx"
        self.result_path = Path(RESULT_DIR) / "PageAuto_Result.xlsx"

        self._ensure_result_file()
        self._ensure_devlog_file()

        # Apply formatting to both existing and newly-created workbooks.
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

            _style_data_row(sheet, target_row, "post_status")
            if sheet.max_row >= 1 and sheet.max_column >= 1:
                sheet.auto_filter.ref = (
                    f"A1:{get_column_letter(sheet.max_column)}{sheet.max_row}"
                )

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
            _style_data_row(sheet, sheet.max_row, "status")
            if sheet.max_row >= 1 and sheet.max_column >= 1:
                sheet.auto_filter.ref = (
                    f"A1:{get_column_letter(sheet.max_column)}{sheet.max_row}"
                )
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
