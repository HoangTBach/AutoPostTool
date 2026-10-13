from pathlib import Path

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from src.components.button import Button
from src.components.card import StatCard, TableCard
from src.components.page_header import PageHeader
from src.components.table import Table
from src.configs.path import DOWNLOAD_DIR
from src.configs.table import PAGE_TABLE_COLUMNS
from src.features.page_posting.worker import (
    PageAutoWorker,
    PageImportWorker,
)
from src.styles.page_auto_style import PAGE_AUTO_STYLE
from src.themes.spacing import SPACING as SPACE
from src.utils.file import open_directory

ICON_DIR = Path(__file__).resolve().parent.parent / "assets" / "icons"


class PageAutoPage(QWidget):

    # ----- Settings -----
    MARGIN = (SPACE[32], SPACE[32], SPACE[32], SPACE[32])
    SPACING = SPACE[24]
    ACTION_SPACING = SPACE[8]
    STAT_SPACING = SPACE[12]
    CONTENT_SPACING = SPACE["legacy"][20]

    def __init__(self):
        super().__init__()

        self.setObjectName("pageAutoContent")
        self.setStyleSheet(PAGE_AUTO_STYLE)

        # ----- State -----
        self.page_rows = []
        self.page_jobs = []

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
            text="Open Excel",
            icon=ICON_DIR / "folder-open.svg",
            variant="outline",
            color="blue",
        )

        self.summary_label = QLabel("0 rows • 0 page targets")
        self.summary_label.setObjectName("summary_label")

        self.run_button = Button(
            text="Run",
            icon=ICON_DIR / "play.svg",
            variant="primary",
            color="blue",
        )

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

        action_layout.addStretch()

        action_layout.addWidget(self.summary_label)

        action_layout.addWidget(self.run_button)

        action_layout.addWidget(self.stop_button)

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

        # ----- Content -----
        content = QWidget()

        content_layout = QVBoxLayout(content)

        content_layout.setContentsMargins(0, 0, 0, 0)

        content_layout.setSpacing(self.CONTENT_SPACING)

        content_layout.addLayout(action_layout)

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

        self.open_button.clicked.connect(self.open_excel)

        self.run_button.clicked.connect(self.start_run)

        self.stop_button.clicked.connect(self.stop_run)

        self.update_action_state()

    # ----- Import -----
    def import_excel(self):
        if self.importing or self.running:
            return

        self.importing = True
        self.update_action_state()

        self.import_worker = PageImportWorker(
            self.data_file_stamp,
            self.data_signature,
        )

        self.import_worker.result.connect(self.handle_import_result)

        self.import_worker.error.connect(self.handle_import_error)

        self.import_worker.finished.connect(self.clear_import_worker)

        self.import_worker.start()

    def handle_import_result(
        self,
        result: dict,
    ):
        self.data_file_stamp = result["file_stamp"]

        if not result["changed"]:
            return

        old_status = {
            row["task_id"]: row.get("status", "")
            for row in self.page_rows
            if row.get("task_id")
        }

        rows = result["rows"]

        for row in rows:
            task_id = row.get("task_id")

            if task_id in old_status:
                row["status"] = old_status[task_id]

        self.data_signature = result["signature"]

        self.page_jobs = result["jobs"]

        self.page_rows = rows

        self.refresh_page()

    def handle_import_error(
        self,
        error: str,
    ):
        QMessageBox.warning(
            self,
            "Page Auto",
            error,
        )

    def clear_import_worker(self):
        if self.import_worker:
            self.import_worker.deleteLater()
            self.import_worker = None

        self.importing = False
        self.update_action_state()

    # ----- Page Data -----
    def refresh_page(self):
        self.table.set_data(self.page_rows)

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
            f"{total_pages - active_pages} " "pages need review"
        )

        self.published_card.value_label.setText(str(published))

        self.failed_card.value_label.setText(str(failed))

    # ----- Action State -----
    def update_action_state(self):
        has_data = bool(self.page_rows)

        busy = self.importing or self.running

        self.import_button.setEnabled(not busy)

        self.open_button.setEnabled(not busy)

        self.run_button.setVisible(has_data and not busy)

        self.stop_button.setVisible(self.running)

        self.stop_button.setEnabled(self.running)

    # ----- Open Excel -----
    def open_excel(self):
        try:
            open_directory(DOWNLOAD_DIR)

        except (
            FileNotFoundError,
            NotADirectoryError,
            OSError,
        ) as error:
            QMessageBox.warning(self, "Open Excel", str(error))

    # ----- Run -----
    def start_run(self):
        if not self.page_jobs or self.importing or self.running:
            return

        self.run_worker = PageAutoWorker(self.page_jobs)

        self.run_worker.error.connect(self.handle_run_error)
        self.run_worker.progress.connect(self.handle_run_progress)
        self.run_worker.finished.connect(self.clear_run_worker)

        self.running = True
        self.update_action_state()

        self.run_worker.start()

    def stop_run(self):
        if not self.running or not self.run_worker:
            return

        self.run_worker.request_stop()

        self.stop_button.setEnabled(False)

    def handle_run_error(self, error: str):
        QMessageBox.warning(self, "Page Auto", error)

    def handle_run_progress(self, event: dict):
        task_id = event.get("task_id")

        for row in self.page_rows:
            if row.get("task_id") == task_id:
                row["status"] = event.get("ui_status", "")
                row["error"] = event.get("error", "")
                break

        self.refresh_page()

    def clear_run_worker(self):
        if self.run_worker:
            self.run_worker.deleteLater()
            self.run_worker = None

        self.running = False
        self.update_action_state()
