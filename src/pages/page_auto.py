import math
import time as _time_module

from pathlib import Path
from datetime import datetime
from openpyxl import load_workbook  # type: ignore

from PySide6.QtCore import (
    QTimer,
    QSettings,
    QLocale,
    QPropertyAnimation,
    QEasingCurve,
    Qt,
)


from PySide6.QtGui import QDoubleValidator

from PySide6.QtWidgets import (
    QFrame,
    QSizePolicy,
    QHBoxLayout,
    QLabel,
    QGridLayout,
    QVBoxLayout,
    QWidget,
    QFileDialog,
    QApplication,
)

from src.components.button import Button
from src.components.card import Card, StatCard, TableCard
from src.components.input import Input, InputMode
from src.components.file_path_input import FilePathInput
from src.components.page_header import PageHeader
from src.components.table import Table
from src.components.notification import NotificationManager
from src.configs.path import DEVLOG_DIR, MEDIA_DIR
from src.configs.table import PAGE_TABLE_COLUMNS
from src.configs.automation import (
    PAGE_AUTO_POST_DELAY,
    PAGE_AUTO_ORDER_DELAY,
)
from src.features.page_posting.worker import (
    PageAutoWorker,
    PageImportWorker,
    PagePreflightWorker,
)
from src.features.page_posting.validation import (
    format_import_error_notification,
    format_validation_notification,
)
from src.styles.page_auto_style import (
    PAGE_AUTO_STYLE,
    PAGE_AUTO_MARGIN,
    PAGE_AUTO_LAYOUT_SPACING,
    PAGE_AUTO_ACTION_SPACING,
    PAGE_AUTO_STAT_SPACING,
    PAGE_AUTO_CONTENT_SPACING,
    PAGE_AUTO_CONFIG_CARD_MARGINS,
    PAGE_AUTO_CONFIG_CARD_SPACING,
    PAGE_AUTO_CONFIG_BODY_SPACING,
    PAGE_AUTO_CONFIG_CONTROL_SPACING,
)
from src.utils.file import open_directory
from src.utils.report_paths import get_report_paths
from src.utils.cmd_log import cmd_log

ICON_DIR = Path(__file__).resolve().parent.parent / "assets" / "icons"


class PageAutoPage(QWidget):
    # ----- Settings -----
    MARGIN = PAGE_AUTO_MARGIN
    SPACING = PAGE_AUTO_LAYOUT_SPACING
    ACTION_SPACING = PAGE_AUTO_ACTION_SPACING
    STAT_SPACING = PAGE_AUTO_STAT_SPACING
    CONTENT_SPACING = PAGE_AUTO_CONTENT_SPACING

    def __init__(self, notifications=None):
        super().__init__()

        self._adspower_warning_shown = False
        self.worker = None
        self.preflight_worker = None

        self.settings = QSettings(
            QSettings.Format.IniFormat,
            QSettings.Scope.UserScope,
            "AutoPostTool",
            "AutoPostTool",
        )

        self.notifications = (
            notifications if notifications is not None else NotificationManager(self)
        )

        self.setObjectName("pageAutoContent")
        self.setStyleSheet(PAGE_AUTO_STYLE)

        # ----- State -----
        self.page_rows = []
        self.page_jobs = []
        self.validation_errors = []

        self.data_file_stamp = None
        self.data_signature = None

        self.import_worker = None
        self.run_worker = None

        self.importing = False
        self.running = False

        # ----- Header -----
        header = PageHeader(
            title="Page Auto",
            subtitle="Manage and publish posts across your Pages.",
        )

        # ----- Actions -----
        self.import_button = Button(
            text="Import Excel",
            icon=ICON_DIR / "upload.svg",
            variant="outline",
            color="green",
        )

        self.open_button = Button(
            text="Open Folder",
            icon=ICON_DIR / "folder-open.svg",
            variant="outline",
            color="blue",
        )

        self.config_button = Button(
            text="Config",
            icon=ICON_DIR / "settings.svg",
            variant="outline",
            color="gray",
        )

        self.summary_label = QLabel("0 rows • 0 page targets")
        self.summary_label.setObjectName("summary_label")

        self.run_button = Button(
            text="Run",
            icon=ICON_DIR / "play.svg",
            variant="primary",
            color="blue",
        )
        self.run_button.setVisible(False)

        self.stop_button = Button(
            text="Stop",
            icon=ICON_DIR / "square.svg",
            variant="primary",
            color="red",
        )

        action_layout = QHBoxLayout()
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(self.ACTION_SPACING)

        action_layout.addWidget(self.import_button)
        action_layout.addWidget(self.open_button)
        action_layout.addWidget(self.config_button)
        action_layout.addStretch()
        action_layout.addWidget(self.summary_label)
        action_layout.addWidget(self.run_button)
        action_layout.addWidget(self.stop_button)

        # ----- Config Card -----
        self.config_card = Card()

        self.config_card_layout = QVBoxLayout(self.config_card)
        self.config_card_layout.setContentsMargins(
            *PAGE_AUTO_CONFIG_CARD_MARGINS,
        )
        self.config_card_layout.setSpacing(PAGE_AUTO_CONFIG_CARD_SPACING)

        self._build_config_card()

        # ----- Config Card State -----
        self._config_expanded = False

        self.config_card.setMaximumHeight(0)
        self.config_card.setVisible(False)

        # ----- Config Card Animation -----
        self._config_animation = QPropertyAnimation(
            self.config_card,
            b"maximumHeight",
            self,
        )
        self._config_animation.setDuration(220)
        self._config_animation.setEasingCurve(
            QEasingCurve.Type.OutCubic,
        )
        self._config_animation.finished.connect(
            self._finish_config_animation,
        )

        # ----- Stats -----
        self.active_pages_card = StatCard(
            title="Active pages",
            value="0 / 0",
            description="0 pages need review",
            icon=ICON_DIR / "file-text.svg",
            color="blue",
        )

        self.published_card = StatCard(
            title="Posts published",
            value="0",
            description="Published today",
            icon=ICON_DIR / "earth.svg",
            color="green",
        )

        self.automation_card = StatCard(
            title="Next automation",
            value="--:--",
            description="Not scheduled",
            icon=ICON_DIR / "clock-3.svg",
            color="purple",
        )

        self.failed_card = StatCard(
            title="Failed posts",
            value="0",
            description="Needs attention",
            icon=ICON_DIR / "triangle-alert.svg",
            color="red",
        )

        stat_layout = QHBoxLayout()
        stat_layout.setContentsMargins(0, 0, 0, 0)
        stat_layout.setSpacing(self.STAT_SPACING)

        stat_layout.addWidget(self.active_pages_card, 1)

        stat_layout.addWidget(self.published_card, 1)

        stat_layout.addWidget(self.automation_card, 1)

        stat_layout.addWidget(self.failed_card, 1)

        # ----- Table -----
        self.table_card = TableCard(title="Page List")

        self.table = Table(columns=PAGE_TABLE_COLUMNS)

        self.table_card.set_table(self.table)
        self._render_empty_state()

        # ----- Content -----
        content = QWidget()

        content_layout = QVBoxLayout(content)

        content_layout.setContentsMargins(0, 0, 0, 0)

        content_layout.setSpacing(self.CONTENT_SPACING)

        content_layout.addLayout(action_layout)
        content_layout.addWidget(self.config_card)
        content_layout.addLayout(stat_layout)
        content_layout.addWidget(self.table_card, 1)

        # ----- Layout -----
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*self.MARGIN)
        layout.setSpacing(self.SPACING)

        layout.addWidget(header)
        layout.addWidget(content, 1)

        # ----- Events -----
        self.import_button.clicked.connect(self.import_excel)
        self.open_button.clicked.connect(self.open_result_folder)
        self.config_button.clicked.connect(self.toggle_config_card)
        self.run_button.clicked.connect(self.start_run)
        self.stop_button.clicked.connect(self.stop_run)

        self.update_action_state()

        self._progress_refresh_timer = QTimer(self)
        self._progress_refresh_timer.setSingleShot(True)
        self._progress_refresh_timer.setInterval(80)
        self._progress_refresh_timer.timeout.connect(self.refresh_page)

    # ----- Notification -----
    def _notify_adspower_warning(self, message: str = ""):
        if self._adspower_warning_shown:
            return

        self._adspower_warning_shown = True
        message = " ".join(str(message).split())

        self.notifications.warning(
            "AdsPower Connection Warning",
            message or "Check AdsPower connection and profile settings.",
            5000,
        )

    def _short_notification(self, message: str, limit: int = 120) -> str:
        message = " ".join(str(message).split())

        if len(message) <= limit:
            return message

        return message[: limit - 3].rstrip() + "..."

    # ----- Import Excel -----
    def import_excel(self):
        if self.importing or self.running:
            return

        self.importing = True
        self.update_action_state()

        self.import_worker = PageImportWorker(
            self.data_file_stamp,
            self.data_signature,
            media_folder=self.media_folder_input.path_input.text().strip(),
        )

        self.import_worker.result.connect(self.handle_import_result)
        self.import_worker.error.connect(self.handle_import_error)
        self.import_worker.finished.connect(self.clear_import_worker)

        self.import_worker.start()

    def handle_import_result(self, result: dict):
        self.data_file_stamp = result.get(
            "file_stamp",
            self.data_file_stamp,
        )
        self.data_signature = result.get(
            "signature",
            self.data_signature,
        )

        if not result.get("changed"):
            return

        validation_errors = result.get("validation_errors") or []
        self.validation_errors = validation_errors

        previous_rows = {
            row.get("task_id"): row for row in self.page_rows if row.get("task_id")
        }

        preserve_fields = (
            "post_id",
            "post_order",
            "profile_id",
            "profile_uid",
            "via_id",
            "page_id",
            "page_link",
            "caption",
            "media",
            "comment",
        )

        rows = result.get("rows", [])

        for row in rows:
            previous = previous_rows.get(row.get("task_id"))

            if (
                previous
                and not row.get("_media_resolution_error")
                and all(
                    previous.get(field) == row.get(field) for field in preserve_fields
                )
            ):
                row["status"] = previous.get("status", "")
                row["error"] = previous.get("error", "")

        self.page_rows = rows

        # Never allow Run when any selected row has validation errors.
        self.page_jobs = result.get("jobs", []) if not validation_errors else []

        self.refresh_page()

        if validation_errors:
            self.notifications.warning(
                "Excel Validation Failed",
                format_validation_notification(validation_errors),
                5000,
            )
            return

        page_targets = {
            str(row.get("page_id", "")).strip()
            for row in self.page_rows
            if str(row.get("page_id", "")).strip()
        }

        self.notifications.success(
            "Excel Import Success",
            f"{len(self.page_rows)} rows • " f"{len(page_targets)} page targets.",
            5000,
        )

    def handle_import_error(self, error: str):
        self.data_file_stamp = None
        self.data_signature = None
        self.validation_errors = []
        self.page_jobs = []
        self.page_rows = []

        self.refresh_page()

        self.notifications.error(
            "Excel Import Failed",
            format_import_error_notification(error),
            5000,
        )

    def clear_import_worker(self):
        if self.import_worker:
            self.import_worker.deleteLater()
            self.import_worker = None

        self.importing = False
        self.update_action_state()

    # ----- Config Card -----
    def _build_config_card(self):
        """Build editable timing and media-folder settings."""
        body = QWidget(self.config_card)
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(PAGE_AUTO_CONFIG_BODY_SPACING)

        # Left column: timing settings.
        timing_panel = QWidget(body)
        timing_layout = QGridLayout(timing_panel)
        timing_layout.setContentsMargins(0, 0, 0, 0)
        timing_layout.setHorizontalSpacing(PAGE_AUTO_CONFIG_CONTROL_SPACING)
        timing_layout.setVerticalSpacing(PAGE_AUTO_CONFIG_CONTROL_SPACING)
        timing_layout.setColumnStretch(0, 1)
        timing_layout.setColumnMinimumWidth(1, 70)
        timing_layout.setColumnMinimumWidth(2, 48)

        self.post_delay_input = self._create_delay_input(
            self._get_saved_delay_value(
                "page_auto/post_delay_minutes",
                PAGE_AUTO_POST_DELAY,
            )
        )
        self.order_delay_input = self._create_delay_input(
            self._get_saved_delay_value(
                "page_auto/order_delay_minutes",
                PAGE_AUTO_ORDER_DELAY,
            )
        )

        timing_layout.addWidget(
            self._create_config_label("Delay between pages"),
            0,
            0,
        )
        timing_layout.addWidget(self.post_delay_input, 0, 1)
        timing_layout.addWidget(self._create_unit_label(), 0, 2)

        timing_layout.addWidget(
            self._create_config_label("Delay between post orders"),
            1,
            0,
        )
        timing_layout.addWidget(self.order_delay_input, 1, 1)
        timing_layout.addWidget(self._create_unit_label(), 1, 2)

        # Right column: FilePathInput owns its label and folder button.
        media_panel = QWidget(body)
        media_layout = QGridLayout(media_panel)
        media_layout.setContentsMargins(0, 0, 0, 0)
        media_layout.setHorizontalSpacing(PAGE_AUTO_CONFIG_CONTROL_SPACING)
        media_layout.setVerticalSpacing(PAGE_AUTO_CONFIG_CONTROL_SPACING)
        media_layout.setColumnStretch(1, 1)

        media_folder = self._get_saved_media_folder()

        self.media_folder_label = self._create_config_label("Media folder")
        self.media_folder_input = FilePathInput(
            text=media_folder,
            variant="file_path",
            parent=media_panel,
        )

        self.media_folder_input.path_input.setToolTip(media_folder)
        self.media_folder_input.browse_button.clicked.connect(self.choose_media_folder)

        media_layout.addWidget(
            self.media_folder_label, 0, 0, Qt.AlignmentFlag.AlignVCenter
        )
        media_layout.addWidget(self.media_folder_input, 0, 1)

        self.config_divider = QFrame(body)
        self.config_divider.setObjectName("configDivider")
        self.config_divider.setFixedWidth(1)
        self.config_divider.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Expanding,
        )

        body_layout.addWidget(timing_panel, 1, Qt.AlignmentFlag.AlignTop)
        body_layout.addWidget(self.config_divider)
        body_layout.addWidget(media_panel, 1, Qt.AlignmentFlag.AlignTop)

        save_layout = QHBoxLayout()
        save_layout.setContentsMargins(0, 0, 0, 0)
        save_layout.addStretch()

        self.save_config_button = Button(
            text="Save",
            variant="primary",
            color="blue",
        )
        self.save_config_button.setMinimumWidth(72)
        self.save_config_button.clicked.connect(self.save_config)
        save_layout.addWidget(self.save_config_button)

        self.config_card_layout.addWidget(body)
        self.config_card_layout.addLayout(save_layout)

    def _get_saved_delay_value(self, key: str, default_value: float) -> float:
        try:
            value = float(self.settings.value(key, default_value))
        except (TypeError, ValueError):
            return float(default_value)

        if not math.isfinite(value) or not 0 <= value <= 10080:
            return float(default_value)

        return value

    def _get_saved_media_folder(self) -> str:
        saved_folder = self.settings.value(
            "page_auto/media_folder",
            None,
            type=str,
        )
        if not saved_folder:
            # Migrate the setting name used by older Page Auto config builds.
            saved_folder = self.settings.value(
                "page_auto/folder_path",
                str(MEDIA_DIR),
                type=str,
            )

        folder = Path(str(saved_folder or MEDIA_DIR)).expanduser()
        if not folder.is_dir():
            folder = Path(MEDIA_DIR)

        return str(folder.resolve())

    def _create_config_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("configLabel")
        return label

    def _create_unit_label(self) -> QLabel:
        label = QLabel("minutes")
        label.setObjectName("configUnitLabel")
        return label

    def _create_delay_input(self, value: float) -> Input:
        value = float(value)
        if not math.isfinite(value) or not 0 <= value <= 10080:
            value = 0.0

        display_value = f"{value:.2f}".rstrip("0").rstrip(".")
        delay_input = Input(
            text=display_value or "0",
            mode=InputMode.LOCKED,
        )
        delay_input.setAlignment(Qt.AlignmentFlag.AlignRight)
        delay_input.setMinimumWidth(70)
        delay_input.setMaximumWidth(70)
        delay_input.setToolTip("Set delay in minutes (0–10080).")

        validator = QDoubleValidator(0.0, 10080.0, 2, delay_input)
        validator.setNotation(QDoubleValidator.Notation.StandardNotation)
        validator.setLocale(QLocale.c())
        delay_input.setValidator(validator)
        return delay_input

    def choose_media_folder(self):
        current_text = self.media_folder_input.path_input.text().strip()
        current_folder = (
            Path(current_text).expanduser() if current_text else Path(MEDIA_DIR)
        )

        if not current_folder.is_dir():
            current_folder = Path(MEDIA_DIR)
        if not current_folder.is_dir():
            current_folder = Path.home()

        selected_folder = QFileDialog.getExistingDirectory(
            self,
            "Select Media Folder",
            str(current_folder),
            QFileDialog.Option.ShowDirsOnly,
        )
        if not selected_folder:
            return

        resolved_folder = str(Path(selected_folder).expanduser().resolve())
        self.media_folder_input.path_input.setText(resolved_folder)
        self.media_folder_input.path_input.setToolTip(resolved_folder)

    def save_config(self):
        if self.importing or self.running:
            return

        try:
            post_delay = float(self.post_delay_input.text().strip())
            order_delay = float(self.order_delay_input.text().strip())
        except (TypeError, ValueError):
            self.notifications.warning(
                "Invalid Page Auto Settings",
                "Enter a valid number for both delay values.",
                4000,
            )
            return

        for label, value in (
            ("Delay between pages", post_delay),
            ("Delay between post orders", order_delay),
        ):
            if not math.isfinite(value) or not 0 <= value <= 10080:
                self.notifications.warning(
                    "Invalid Page Auto Settings",
                    f"{label} must be between 0 and 10080 minutes.",
                    4000,
                )
                return

        folder_text = self.media_folder_input.path_input.text().strip()
        folder = Path(folder_text).expanduser() if folder_text else Path(MEDIA_DIR)

        if not folder.is_dir():
            self.notifications.warning(
                "Invalid Media Folder",
                f"The selected media folder does not exist: {folder}",
                5000,
            )
            return

        folder_text = str(folder.resolve())

        self.settings.setValue("page_auto/post_delay_minutes", post_delay)
        self.settings.setValue("page_auto/order_delay_minutes", order_delay)
        self.settings.setValue("page_auto/media_folder", folder_text)
        # Keep the legacy key in sync so older config screens can still read it.
        self.settings.setValue("page_auto/folder_path", folder_text)
        self.settings.sync()

        if self.settings.status() != QSettings.Status.NoError:
            self.notifications.error(
                "Page Auto Settings",
                "Could not save the configuration to QSettings.",
                5000,
            )
            return

        self.media_folder_input.path_input.setText(folder_text)
        self.media_folder_input.path_input.setToolTip(folder_text)
        self.notifications.success(
            "Page Auto Settings",
            "Configuration saved successfully.",
            3000,
        )

    def toggle_config_card(self):
        self._config_animation.stop()

        current_height = self.config_card.height()
        self._config_expanded = not self._config_expanded

        if self._config_expanded:
            self.config_card.setVisible(True)
            self.config_card.setMaximumHeight(current_height)

            target_height = max(
                self.config_card.sizeHint().height(),
                current_height,
            )

            self._config_animation.setStartValue(current_height)
            self._config_animation.setEndValue(target_height)

        else:
            self._config_animation.setStartValue(current_height)
            self._config_animation.setEndValue(0)

        self._config_animation.start()

    def _finish_config_animation(self):
        if self._config_expanded:
            self.config_card.setMaximumHeight(16777215)
        else:
            self.config_card.setVisible(False)
            self.config_card.setMaximumHeight(0)

    # ----- Page Data -----
    def _render_empty_state(self):
        """Show the same empty-table treatment used in Group Auto.

        Table.set_data() recreates its body children, so the placeholder must
        be rebuilt after refreshes that contain zero rows.
        """
        empty_state = QWidget(self.table.body)
        empty_state.setObjectName("pageEmptyState")
        empty_layout = QVBoxLayout(empty_state)
        empty_layout.setContentsMargins(16, 40, 16, 40)
        empty_layout.setSpacing(8)

        title = QLabel("No pages added yet")
        title.setObjectName("pageEmptyTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        subtitle = QLabel(
            "Import an Excel file to see your pages and post progress here."
        )
        subtitle.setObjectName("pageEmptySubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)

        empty_layout.addWidget(title)
        empty_layout.addWidget(subtitle)
        self.table.body_layout.addWidget(empty_state)

    def refresh_page(self):
        self.table.set_data(self.page_rows)
        if not self.page_rows:
            self._render_empty_state()

        self.update_summary()
        self.update_stats()
        self.update_action_state()

    def update_summary(self):
        page_targets = {
            row.get("page_id") for row in self.page_rows if row.get("page_id")
        }

        self.summary_label.setText(
            f"{len(self.page_rows)} rows • " f"{len(page_targets)} page targets"
        )

    def update_stats(self):
        page_status = {}

        for row in self.page_rows:
            page_id = row.get("page_id")

            if page_id and page_id not in page_status:
                page_status[page_id] = row.get("page_status", "")

        total_pages = len(page_status)

        active_pages = sum(
            1 for status in page_status.values() if status.upper() == "ACTIVE"
        )

        published = sum(1 for row in self.page_rows if row.get("status") == "Done")

        failed = sum(1 for row in self.page_rows if row.get("status") == "Error")

        self.active_pages_card.value_label.setText(f"{active_pages} / {total_pages}")

        self.active_pages_card.description_label.setText(
            "No pages loaded"
            if total_pages == 0
            else f"{total_pages - active_pages} pages need review"
        )

        self.published_card.value_label.setText(str(published))

        self.failed_card.value_label.setText(str(failed))

    # ----- Action State -----
    def update_action_state(self):
        # ----- Button State -----
        has_data = (
            bool(self.page_rows) and bool(self.page_jobs) and not self.validation_errors
        )
        busy = self.running

        if hasattr(self, "save_config_button"):
            self.save_config_button.setEnabled(not busy)
        if hasattr(self, "media_folder_input"):
            self.media_folder_input.browse_button.setEnabled(not busy)
        if hasattr(self, "post_delay_input"):
            self.post_delay_input.setEnabled(not busy)
        if hasattr(self, "order_delay_input"):
            self.order_delay_input.setEnabled(not busy)

        self.import_button.setEnabled(not busy)
        self.open_button.setEnabled(not busy)
        self.run_button.setVisible(has_data and not busy)
        self.run_button.setEnabled(has_data and not busy)

        self.stop_button.setVisible(self.running)

        active_workers = (
            getattr(self, "preflight_worker", None),
            getattr(self, "worker", None),
        )

        stop_requested = bool(
            getattr(self, "_stop_requested", False)
            or any(
                getattr(worker, "stop_requested", False)
                for worker in active_workers
                if worker is not None
            )
        )
        self.stop_button.setEnabled(self.running and not stop_requested)

        # ----- Automation Timer -----
        if not hasattr(self, "_automation_timer"):
            self._automation_state_cache = {}
            self._automation_state_last_read = 0.0

            self._automation_timer = QTimer(self)
            self._automation_timer.setInterval(1_000)
            self._automation_timer.timeout.connect(self.update_action_state)

        if not self._automation_timer.isActive():
            self._automation_timer.start()

        # ----- Refresh RUN_STATE Cache -----
        monotonic_now = _time_module.monotonic()

        if monotonic_now - self._automation_state_last_read >= 5:
            self._automation_state_last_read = monotonic_now
            state_file = Path(DEVLOG_DIR) / "PageAuto_DevLog.xlsx"

            if not state_file.is_file():
                self._automation_state_cache = {}
            else:
                try:
                    workbook = load_workbook(
                        state_file,
                        read_only=True,
                        data_only=True,
                    )

                    try:
                        state = {}

                        if "RUN_STATE" in workbook.sheetnames:
                            for key, value in workbook["RUN_STATE"].iter_rows(
                                min_row=2,
                                values_only=True,
                            ):
                                if key:
                                    state[str(key).strip()] = value

                        self._automation_state_cache = state
                    finally:
                        workbook.close()

                except Exception:
                    pass

        # ----- Parse Cached RUN_STATE -----
        state = self._automation_state_cache
        wait_type = str(state.get("wait_type") or "").strip().upper()

        try:
            last_completed_order = int(float(state.get("last_completed_order")))
        except (TypeError, ValueError):
            last_completed_order = None

        try:
            raw_next_order_at = state.get("next_order_at")

            if raw_next_order_at:
                next_order_at = datetime.fromisoformat(str(raw_next_order_at))

                if next_order_at.tzinfo is None:
                    next_order_at = next_order_at.astimezone()
                else:
                    next_order_at = next_order_at.astimezone()
            else:
                next_order_at = None

        except (TypeError, ValueError):
            next_order_at = None

        try:
            raw_next_page_at = state.get("next_page_at")

            if raw_next_page_at:
                next_page_at = datetime.fromisoformat(str(raw_next_page_at))
                next_page_at = next_page_at.astimezone()
            else:
                next_page_at = None

        except (TypeError, ValueError):
            next_page_at = None

        # ----- Check Next Post Order -----
        has_next_order = False

        if last_completed_order is not None:
            for job in self.page_jobs:
                try:
                    order = int(float(job.get("post_order")))
                except (TypeError, ValueError):
                    continue

                if order > last_completed_order:
                    has_next_order = True
                    break

        # ----- Update Automation Card -----
        now = datetime.now().astimezone()

        if wait_type == "PAGE" and next_page_at is not None:
            next_deadline = next_page_at
            description_prefix = "Next Page"
        elif wait_type == "ORDER" and next_order_at is not None:
            next_deadline = next_order_at
            description_prefix = "Next Post Order"
        elif has_next_order and next_order_at is not None:
            # Compatibility with RUN_STATE files written by older versions.
            next_deadline = next_order_at
            description_prefix = "Next Post Order"
        else:
            next_deadline = None

        if next_deadline is not None:
            self.automation_card.value_label.setText(next_deadline.strftime("%H:%M"))

            remaining_seconds = int((next_deadline - now).total_seconds())

            if remaining_seconds > 0:
                minutes, seconds = divmod(remaining_seconds, 60)

                if minutes:
                    description = (
                        f"{description_prefix} in {minutes} min " f"{seconds:02d} sec"
                    )
                else:
                    description = f"{description_prefix} in {seconds} sec"
            else:
                description = "Continuing now" if self.running else "Ready to continue"

            self.automation_card.description_label.setText(description)

        else:
            self.automation_card.value_label.setText("--:--")
            self.automation_card.description_label.setText("Not scheduled")

            if not self.running and self._automation_timer.isActive():
                self._automation_timer.stop()

    # ----- Open Result Folder -----
    def open_result_folder(self):
        try:
            result_path, _ = get_report_paths("page_auto")
            open_directory(result_path.parent)
        except (FileNotFoundError, NotADirectoryError, OSError) as error:
            self.notifications.warning(
                "Open Folder Failed",
                str(error),
                5000,
            )

    # ----- Run -----
    def start_run(self):
        app = QApplication.instance()

        if app is None or not bool(app.property("adspower_connected")):
            self.notifications.warning(
                "AdsPower",
                "Please connect AdsPower in Settings before running Page Auto.",
                5000,
            )
            return

        if not self.page_jobs or self.importing or self.running:
            return

        self._adspower_warning_shown = False
        self._stop_requested = False

        api_key = self.settings.value(
            "adspower/api_key",
            "",
            type=str,
        ).strip()

        if not api_key:
            cmd_log(
                "ERROR",
                "Page Auto cannot start: AdsPower API key is missing.",
            )

            self.notifications.warning(
                "API Key Required",
                "Please enter your AdsPower API key in Settings before running Page Auto.",
                5000,
            )
            return

        for row in self.page_rows:
            row["status"] = "Queued"
            row["error"] = ""

        self.refresh_page()

        profile_uids = [
            row.get("profile_uid")
            for job in self.page_jobs
            for row in job.get("rows", [])
        ]

        self.preflight_worker = PagePreflightWorker(
            api_key,
            profile_uids,
        )

        self.preflight_worker.result.connect(self.handle_preflight_result)
        self.preflight_worker.error.connect(self.handle_run_error)
        self.preflight_worker.finished.connect(self.handle_preflight_finished)

        self.running = True
        self.update_action_state()
        self.preflight_worker.start()

    def stop_run(self):
        if not self.running:
            return

        if getattr(self, "_stop_requested", False):
            return

        self._stop_requested = True

        workers = (
            getattr(self, "preflight_worker", None),
            getattr(self, "run_worker", None),
            getattr(self, "worker", None),
        )

        seen = set()

        for worker in workers:
            if worker is None or id(worker) in seen:
                continue

            seen.add(id(worker))

            request_stop = getattr(
                worker,
                "request_stop",
                None,
            )

            if callable(request_stop):
                request_stop()
            else:
                cmd_log(
                    "WARNING",
                    f"{type(worker).__name__} does not implement request_stop().",
                )

        self.stop_button.setEnabled(False)

    def handle_run_error(self, error: str):
        message = str(error).strip()

        if any(word in message.lower() for word in ("adspower", "browser")):
            self._notify_adspower_warning(message)
            return

        self.notifications.error(
            "New Notification",
            self._short_notification(message),
            5000,
        )

    def handle_run_progress(self, event: dict):
        task_id = event.get("task_id")
        status = event.get("ui_status", "")
        error = str(event.get("error") or "")

        row = next(
            (item for item in self.page_rows if item.get("task_id") == task_id),
            None,
        )

        if not row:
            return

        previous_status = row.get("status", "")
        previous_error = row.get("error", "")

        row["status"] = status
        row["error"] = error

        if status == previous_status and error == previous_error:
            return

        if not self._progress_refresh_timer.isActive():
            self._progress_refresh_timer.start()

    def handle_run_finished(self):
        worker = self.worker
        self.worker = None
        self.running = False

        self.update_action_state()

        if worker is not None:
            worker.deleteLater()

    def handle_preflight_finished(self):
        worker = self.preflight_worker
        self.preflight_worker = None

        if worker is not None:
            worker.deleteLater()

        if self.worker is None:
            self.running = False
            self.update_action_state()

    def handle_preflight_result(self, result: dict):
        if getattr(self, "_stop_requested", False):
            return

        if not result.get("ok"):
            return

        message = str(result.get("message") or "AdsPower API and profiles verified.")

        if not self.page_jobs:
            self.notifications.error(
                "Page Auto",
                "No Page Auto jobs found. Please import Excel first.",
                5000,
            )
            return

        if self.worker is not None and self.worker.isRunning():
            return

        self.notifications.success(
            "Preflight Successful",
            f"{message} Starting Facebook Page posting workflow.",
            5000,
        )

        app = QApplication.instance()

        if app is None or not bool(app.property("adspower_connected")):
            self.notifications.warning(
                "AdsPower",
                "AdsPower is not connected. Please connect again in Settings.",
                5000,
            )
            return

        self.worker = PageAutoWorker(self.page_jobs)
        self.worker.progress.connect(self.handle_run_progress)
        self.worker.error.connect(self.handle_run_error)
        self.worker.finished.connect(self.handle_run_finished)

        self.running = True
        self.update_action_state()

        self.worker.start()

    def clear_run_worker(self):
        if self.run_worker:
            self.run_worker.deleteLater()
            self.run_worker = None

        self.running = False
        self.update_action_state()
