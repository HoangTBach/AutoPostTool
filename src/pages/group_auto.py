from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.components.button import Button
from src.components.card import Card, StatCard, TableCard
from src.components.file_path_input import FilePathInput
from src.components.input import Input, InputMode
from src.components.page_header import PageHeader
from src.components.table import Table
from src.configs import automation as automation_config
from src.configs.path import MEDIA_DIR
from src.configs.table import GROUP_TABLE_COLUMNS
from src.styles.group_auto_style import (
    GROUP_AUTO_ACTION_SPACING,
    GROUP_AUTO_CONFIG_MARGIN,
    GROUP_AUTO_CONFIG_CARD_SPACING,
    GROUP_AUTO_CONFIG_BODY_SPACING,
    GROUP_AUTO_CONFIG_CONTROL_SPACING,
    GROUP_AUTO_CONTENT_SPACING,
    GROUP_AUTO_LAYOUT_SPACING,
    GROUP_AUTO_MARGIN,
    GROUP_AUTO_STAT_SPACING,
    GROUP_AUTO_STYLE,
)

ICON_DIR = Path(__file__).resolve().parent.parent / "assets" / "icons"


class GroupAutoPage(QWidget):
    MARGIN = GROUP_AUTO_MARGIN
    SPACING = GROUP_AUTO_LAYOUT_SPACING

    def __init__(self, notifications=None):
        super().__init__()
        self._config_expanded = False
        self.setObjectName("groupAutoContent")
        self.setStyleSheet(GROUP_AUTO_STYLE)

        header = PageHeader(
            title="Group Auto",
            subtitle="Publish one post to multiple groups and track every destination.",
        )

        # ----- Actions -----
        self.import_button = Button(
            text="Import Excel", icon=ICON_DIR / "upload.svg",
            variant="outline", color="green", disabled=True,
        )
        self.open_button = Button(
            text="Open Folder", icon=ICON_DIR / "folder-open.svg",
            variant="outline", color="blue", disabled=True,
        )
        self.config_button = Button(
            text="Config", icon=ICON_DIR / "settings.svg",
            variant="outline", color="gray",
        )
        self.summary_label = QLabel("0 rows • 0 group targets")
        self.summary_label.setObjectName("groupSummaryLabel")
        self.run_button = Button(
            text="Run", icon=ICON_DIR / "play.svg",
            variant="primary", color="blue", disabled=True,
        )
        self.stop_button = Button(
            text="Stop", icon=ICON_DIR / "square.svg",
            variant="primary", color="red", disabled=True,
        )
        self.run_button.setVisible(False)
        self.stop_button.setVisible(False)
        action_layout = QHBoxLayout()
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(GROUP_AUTO_ACTION_SPACING)
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
        self.config_card_layout.setContentsMargins(*GROUP_AUTO_CONFIG_MARGIN)
        self.config_card_layout.setSpacing(GROUP_AUTO_CONFIG_CARD_SPACING)
        self._build_config_card()
        self.config_card.setMaximumHeight(0)
        self.config_card.setVisible(False)

        # ----- Config Animation -----
        self._config_animation = QPropertyAnimation(
            self.config_card, b"maximumHeight", self
        )
        self._config_animation.setDuration(220)
        self._config_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._config_animation.finished.connect(self._finish_config_animation)

        # ----- Stats -----
        self.active_groups_card = StatCard(
            title="Active groups",
            value="0 / 0",
            description="0 groups need review",
            icon=ICON_DIR / "users-2.svg",
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
        stat_layout.setSpacing(GROUP_AUTO_STAT_SPACING)
        for card in (
            self.active_groups_card,
            self.published_card,
            self.automation_card,
            self.failed_card,
        ):
            stat_layout.addWidget(card, 1)

        # ----- Table -----
        self.table_card = TableCard(title="Group List")
        self.table = Table(columns=GROUP_TABLE_COLUMNS)
        self.table_card.set_table(self.table)

        self.empty_state = QWidget(self.table.body)
        self.empty_state.setObjectName("groupEmptyState")
        empty_layout = QVBoxLayout(self.empty_state)
        empty_layout.setContentsMargins(16, 40, 16, 40)
        empty_layout.setSpacing(8)
        self.empty_title = QLabel("No groups added yet")
        self.empty_title.setObjectName("groupEmptyTitle")
        self.empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_subtitle = QLabel(
            "Group details will appear here when data is available."
        )
        self.empty_subtitle.setObjectName("groupEmptySubtitle")
        self.empty_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_subtitle.setWordWrap(True)
        empty_layout.addWidget(self.empty_title)
        empty_layout.addWidget(self.empty_subtitle)
        self.table.body_layout.addWidget(self.empty_state)

        # ----- Content -----
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(GROUP_AUTO_CONTENT_SPACING)
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
        self.config_button.clicked.connect(self.toggle_config_card)

    # ----- Config Card -----
    def _build_config_card(self):
        body = QWidget(self.config_card)
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(GROUP_AUTO_CONFIG_BODY_SPACING)

        # ----- Left: Timing Settings -----
        timing_panel = QWidget(body)
        timing_layout = QGridLayout(timing_panel)
        timing_layout.setContentsMargins(0, 0, 0, 0)
        timing_layout.setHorizontalSpacing(GROUP_AUTO_CONFIG_CONTROL_SPACING)
        timing_layout.setVerticalSpacing(GROUP_AUTO_CONFIG_CONTROL_SPACING)
        timing_layout.setColumnStretch(0, 1)
        timing_layout.setColumnMinimumWidth(1, 70)
        timing_layout.setColumnMinimumWidth(2, 48)

        self.group_delay_input = self._create_locked_input(
            str(getattr(automation_config, "GROUP_AUTO_POST_DELAY", 1))
        )
        self.order_delay_input = self._create_locked_input(
            str(getattr(automation_config, "GROUP_AUTO_ORDER_DELAY", 150))
        )

        timing_layout.addWidget(
            self._config_label("Delay between groups"), 0, 0
        )
        timing_layout.addWidget(self.group_delay_input, 0, 1)
        timing_layout.addWidget(self._unit_label(), 0, 2)
        timing_layout.addWidget(
            self._config_label("Delay between post orders"), 1, 0
        )
        timing_layout.addWidget(self.order_delay_input, 1, 1)
        timing_layout.addWidget(self._unit_label(), 1, 2)

        # ----- Right: Media Folder -----
        media_panel = QWidget(body)
        media_layout = QGridLayout(media_panel)
        media_layout.setContentsMargins(0, 0, 0, 0)
        media_layout.setHorizontalSpacing(GROUP_AUTO_CONFIG_CONTROL_SPACING)
        media_layout.setVerticalSpacing(GROUP_AUTO_CONFIG_CONTROL_SPACING)
        media_layout.setColumnStretch(1, 1)

        self.media_folder_label = self._config_label("Media folder")
        self.media_folder_input = FilePathInput(
            text=str(MEDIA_DIR), variant="file_path", parent=media_panel
        )
        self.media_folder_input.path_input.setToolTip(str(MEDIA_DIR))
        self.media_folder_input.browse_button.setEnabled(False)
        media_layout.addWidget(
            self.media_folder_label, 0, 0, Qt.AlignmentFlag.AlignVCenter
        )
        media_layout.addWidget(self.media_folder_input, 0, 1)

        # ----- Divider -----
        self.config_divider = QFrame(body)
        self.config_divider.setObjectName("groupConfigDivider")
        self.config_divider.setFixedWidth(1)
        self.config_divider.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding
        )

        body_layout.addWidget(timing_panel, 1, Qt.AlignmentFlag.AlignTop)
        body_layout.addWidget(self.config_divider)
        body_layout.addWidget(media_panel, 1, Qt.AlignmentFlag.AlignTop)

        # ----- Save Action -----
        save_layout = QHBoxLayout()
        save_layout.setContentsMargins(0, 0, 0, 0)
        save_layout.addStretch()
        self.save_button = Button(
            text="Save", variant="primary", color="blue", disabled=True
        )
        self.save_button.setMinimumWidth(72)
        save_layout.addWidget(self.save_button)

        self.config_card_layout.addWidget(body)
        self.config_card_layout.addLayout(save_layout)

    # ----- Config Helpers -----
    @staticmethod
    def _config_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("groupConfigLabel")
        return label

    @staticmethod
    def _unit_label() -> QLabel:
        label = QLabel("minutes")
        label.setObjectName("groupConfigUnit")
        return label

    @staticmethod
    def _create_locked_input(text: str) -> Input:
        field = Input(text=text, mode=InputMode.LOCKED)
        field.setAlignment(Qt.AlignmentFlag.AlignRight)
        field.setMinimumWidth(70)
        field.setMaximumWidth(70)
        return field

    # ----- Config Animation -----
    def toggle_config_card(self):
        self._config_animation.stop()
        current_height = self.config_card.height()
        self._config_expanded = not self._config_expanded

        if self._config_expanded:
            self.config_card.setVisible(True)
            self.config_card.setMaximumHeight(max(0, current_height))
            target_height = max(self.config_card.sizeHint().height(), current_height)
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
