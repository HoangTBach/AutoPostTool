from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from src.components.button import Button
from src.components.card import (
    StatCard,
    TableCard,
)
from src.components.page_header import PageHeader
from src.components.table import Table

from src.themes.color import CARD_DESCRIPTION
from src.themes.font import (
    FONT_SIZE_10,
    FONT_WEIGHT_REGULAR,
)

from src.configs.table import PAGE_TABLE_COLUMNS
from src.configs.path import DOWNLOAD_DIR
from src.features.page_posting.excel import load_page_rows
from src.utils.file import open_directory

# ----- Paths -----
ICON_DIR = Path(__file__).resolve().parent.parent / "assets" / "icons"


class PageAutoPage(QWidget):

    # ----- Settings -----
    MARGIN = (32, 32, 32, 32)
    SPACING = 24

    ACTION_SPACING = 8
    STAT_SPACING = 12
    CONTENT_SPACING = 20

    def __init__(self):
        super().__init__()

        # ----- Data -----
        self.page_rows = []

        page_stats = self.get_page_stats(self.page_rows)

        # ----- Header -----
        header = PageHeader(
            title="Page Auto",
            subtitle="Manage and publish posts across your Pages.",
        )

        # ----- Action Buttons -----
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

        # ----- Table Summary -----
        self.summary_label = QLabel()

        self.summary_label.setObjectName("tableSummary")

        self.summary_label.setStyleSheet(f"""
            QLabel#tableSummary {{
                color: {CARD_DESCRIPTION};
                font-size: {FONT_SIZE_10}px;
                font-weight: {FONT_WEIGHT_REGULAR};
                background-color: transparent;
            }}
            """)

        self.update_summary(self.page_rows)

        # ----- Default State -----
        self.run_button.hide()
        self.stop_button.hide()

        # ----- Button Events -----
        self.import_button.clicked.connect(self.import_excel)

        self.open_button.clicked.connect(self.open_excel)

        self.run_button.clicked.connect(self.start_run)

        self.stop_button.clicked.connect(self.stop_run)

        # ----- Action Layout -----
        action_layout = QHBoxLayout()

        action_layout.setContentsMargins(0, 0, 0, 0)

        action_layout.setSpacing(self.ACTION_SPACING)

        action_layout.addWidget(self.import_button)

        action_layout.addWidget(self.open_button)

        action_layout.addStretch()

        action_layout.addWidget(self.summary_label)

        action_layout.addWidget(self.run_button)

        action_layout.addWidget(self.stop_button)

        # ----- Stat Cards -----
        self.active_pages_card = StatCard(
            title="Active pages",
            value=(f"{page_stats['active_pages']} / " f"{page_stats['page_targets']}"),
            description=self.get_review_description(page_stats["review_pages"]),
            icon=ICON_DIR / "file-text.svg",
            color="blue",
        )

        self.published_card = StatCard(
            title="Posts published",
            value=str(page_stats["published"]),
            description="Published posts",
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
            value=str(page_stats["failed"]),
            description="Needs attention",
            icon=ICON_DIR / "triangle-alert.svg",
            color="red",
        )

        # ----- Stat Layout -----
        stat_layout = QHBoxLayout()

        stat_layout.setContentsMargins(0, 0, 0, 0)

        stat_layout.setSpacing(self.STAT_SPACING)

        stat_layout.addWidget(self.active_pages_card, 1)

        stat_layout.addWidget(self.published_card, 1)

        stat_layout.addWidget(self.automation_card, 1)

        stat_layout.addWidget(self.failed_card, 1)

        # ----- Page List Card -----
        self.table_card = TableCard(title="Page List")

        # ----- Table -----
        self.table = Table(columns=PAGE_TABLE_COLUMNS)

        self.table_card.set_table(self.table)

        self.table.set_data(self.page_rows)

        # ----- Content -----
        content = QWidget()

        content_layout = QVBoxLayout(content)

        content_layout.setContentsMargins(0, 0, 0, 0)

        content_layout.setSpacing(self.CONTENT_SPACING)

        content_layout.addLayout(action_layout)

        content_layout.addLayout(stat_layout)

        content_layout.addWidget(self.table_card, 1)

        # ----- Page Layout -----
        layout = QVBoxLayout(self)

        layout.setContentsMargins(*self.MARGIN)

        layout.setSpacing(self.SPACING)

        layout.addWidget(header)

        layout.addWidget(content, 1)

    # ----- Set Page Data -----
    def set_page_data(self, rows: list[dict]):
        self.page_rows = rows

        self.table.set_data(self.page_rows)

        self.update_summary(self.page_rows)

        self.update_stats(self.page_rows)

    # ----- Page Stats -----
    def get_page_stats(self, rows: list[dict]):
        page_targets = {
            row.get("page_id") or row.get("page")
            for row in rows
            if (row.get("page_id") or row.get("page"))
        }

        active_pages = {
            row.get("page_id") or row.get("page")
            for row in rows
            if (
                (row.get("page_id") or row.get("page"))
                and str(row.get("page_status", "")).upper() == "ACTIVE"
            )
        }

        review_pages = page_targets - active_pages

        published = sum(
            1 for row in rows if str(row.get("status", "")).lower() == "done"
        )

        failed = sum(1 for row in rows if str(row.get("status", "")).lower() == "error")

        return {
            "page_targets": len(page_targets),
            "active_pages": len(active_pages),
            "review_pages": len(review_pages),
            "published": published,
            "failed": failed,
        }

    # ----- Update Stats -----
    def update_stats(self, rows: list[dict]):
        stats = self.get_page_stats(rows)

        self.active_pages_card.value_label.setText(
            (f"{stats['active_pages']} / " f"{stats['page_targets']}")
        )

        self.active_pages_card.description_label.setText(
            self.get_review_description(stats["review_pages"])
        )

        self.published_card.value_label.setText(str(stats["published"]))

        self.failed_card.value_label.setText(str(stats["failed"]))

    # ----- Update Summary -----
    def update_summary(self, rows: list[dict]):
        page_targets = {
            row.get("page_id") or row.get("page")
            for row in rows
            if (row.get("page_id") or row.get("page"))
        }

        self.summary_label.setText(
            (f"{len(rows)} rows • " f"{len(page_targets)} page targets")
        )

    # ----- Review Description -----
    def get_review_description(self, count: int):
        if count == 1:
            return "1 page needs review"

        return f"{count} pages need review"

    # ----- Next Automation -----
    def set_next_automation(self, time_text: str, description: str):
        self.automation_card.value_label.setText(time_text)

        self.automation_card.description_label.setText(description)

    # ----- Import Excel -----
    def import_excel(self):

        if not self.import_button.isEnabled():
            return

        try:
            new_rows = load_page_rows()

        except FileNotFoundError as error:
            QMessageBox.warning(
                self,
                "File Not Found",
                str(error),
            )
            return

        except KeyError as error:
            QMessageBox.warning(
                self,
                "Sheet Not Found",
                f"Missing sheet: {error}",
            )
            return

        except Exception as error:
            QMessageBox.critical(
                self,
                "Import Error",
                str(error),
            )
            return

        # ----- No Data -----
        if not new_rows:
            QMessageBox.information(
                self,
                "Import Excel",
                "No Page Post data found.",
            )
            return

        # ----- Current Status -----
        current_status = {
            row.get("task_id"): row.get(
                "status",
                "",
            )
            for row in self.page_rows
            if row.get("task_id")
        }

        # ----- Restore Status -----
        for row in new_rows:
            task_id = row.get("task_id")

            if task_id in current_status:
                row["status"] = current_status[task_id]

        # ----- Set Data -----
        self.set_page_data(new_rows)

        # ----- Show Right Actions -----
        self.summary_label.show()
        self.run_button.show()
        self.stop_button.hide()

    # ----- Open Excel Directory -----
    def open_excel(self):
        try:
            open_directory(DOWNLOAD_DIR)

        except FileNotFoundError as error:
            QMessageBox.warning(
                self,
                "Folder Not Found",
                str(error),
            )

    # ----- Start Run -----
    def start_run(self):
        if not self.page_rows:
            return

        # ----- Lock Import -----
        self.import_button.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )

        # ----- Queued -----
        for row in self.page_rows:

            if row.get("status") == "Done":
                continue

            if not row.get("status"):
                row["status"] = "Queued"

        # ----- Refresh Table -----
        self.table.set_data(self.page_rows)

        self.update_stats(self.page_rows)

        # ----- Button State -----
        self.run_button.hide()
        self.stop_button.show()

    # ----- Stop Run -----
    def stop_run(self):

        # ----- Unlock Import -----
        self.import_button.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            False,
        )

        # ----- Button State -----
        self.stop_button.hide()

        if self.page_rows:
            self.run_button.show()
