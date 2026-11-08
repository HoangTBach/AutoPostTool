from pathlib import Path

from PySide6.QtCore import QSettings, QSize, Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QSizePolicy,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from src.components.button import Button
from src.components.card import Card, SectionCard
from src.components.input import Input
from src.components.file_path_input import FilePathInput
from src.components.notification import NotificationManager
from src.components.page_header import PageHeader
from src.components.setting_choice import (
    SettingChoiceTile,
    SettingRadioChoice,
    SettingWorkspacePreview,
)
from src.components.smooth_scroll_area import SmoothScrollArea
from src.components.toggle_switch import ToggleSwitch
from src.configs.adspower import ADSPOWER_DEFAULT_URL
from src.configs.path import DATA_FILE, RESULT_DIR
from src.features.adspower.worker import AdsPowerCheckWorker
from src.features.page_posting.adspower import clear_credentials, set_credentials
from src.styles.setting_style import (
    SETTING_NOTIFICATION_ITEM_STYLE,
    SETTING_PAGE_STYLE,
    SETTING_SECTIONS_STYLE,
    SETTING_STYLE,
    CARD_BORDER,
    CONNECTION_STATUS_STYLES,
)
from src.themes.spacing import SPACING as SPACE
from src.utils.cmd_log import cmd_log

ICON_DIR = Path(__file__).resolve().parent.parent / "assets" / "icons"


class SettingPage(QWidget):
    # ----- Settings -----
    MARGIN = (SPACE[32], SPACE[32], SPACE[32], SPACE[32])
    SPACING = SPACE["legacy"][20]

    CARD_MARGIN = (
        SPACE[16],
        SPACE["legacy"][14],
        SPACE[16],
        SPACE["legacy"][14],
    )
    CARD_SPACING = SPACE[16]

    FORM_SPACING = SPACE[8]
    BUTTON_SPACING = SPACE[8]

    AUTO_RECONNECT_DEFAULT = False
    AUTO_RECONNECT_INTERVAL = 15000

    # ----- UI Preferences -----
    UI_DEFAULTS = {
        "theme": "Light",
        "language": "English",
        "task_completed": True,
        "notification_sound": False,
        "task_failed": True,
        "desktop_notifications": False,
        "start_with_windows": False,
        "minimize_to_tray": False,
        "confirm_before_close": False,
        "sidebar_mode": "Expanded",
        "split_page": "off",
    }
    UI_CHOICE_VALUES = {
        "theme": ("Light", "Dark", "System"),
        "language": ("English", "Vietnamese"),
        "sidebar_mode": ("Expanded", "Compact"),
        "split_page": ("off", "vertical", "horizontal"),
    }

    # ----- Initialize -----
    def __init__(self):
        super().__init__()

        self.setObjectName("settingsPage")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        # ----- Settings -----
        self.settings = QSettings(
            QSettings.Format.IniFormat,
            QSettings.Scope.UserScope,
            "AutoPostTool",
            "AutoPostTool",
        )

        self.notifications = NotificationManager(self)

        self._saved_api_key = self.settings.value(
            "adspower/api_key",
            "",
            type=str,
        ).strip()

        self._saved_auto_reconnect = self.settings.value(
            "adspower/auto_reconnect",
            self.AUTO_RECONNECT_DEFAULT,
            type=bool,
        )

        self._saved_ui_preferences = self._load_ui_preferences()
        self._ui_choice_buttons = {}
        self._ui_toggles = {}
        self.setStyleSheet(SETTING_STYLE + SETTING_PAGE_STYLE + SETTING_SECTIONS_STYLE)

        # ----- Connection State -----
        self.is_connected = False
        self.check_worker = None
        self.check_action = None

        self.connected_local_api = ""
        self.connected_api_key = ""

        self._check_local_api = ""
        self._check_api_key = ""

        self.reconnect_timer = QTimer(self)
        self.reconnect_timer.setInterval(self.AUTO_RECONNECT_INTERVAL)
        self.reconnect_timer.timeout.connect(self.auto_reconnect)

        # ----- Page Header -----
        header = PageHeader(
            title="Settings",
            subtitle="Manage connections, automation, and alerts for your workspace.",
        )

        # ----- AdsPower Card -----
        adspower_card = SectionCard(
            "AdsPower Connection",
            "Connect your AdsPower workspace and local API",
            header_border=True,
            header_height=63,
            header_margin=(20, 16, 20, 14),
            body_margin=self.CARD_MARGIN,
            body_spacing=self.CARD_SPACING,
            title_object_name="settingCardTitle",
            description_object_name="settingCardSubtitle",
        )
        self._style_section_card(adspower_card)
        adspower_card.setMinimumHeight(240)
        adspower_layout = adspower_card.body_layout

        # ----- Connection Status -----
        self.status_label = QLabel("● Disconnected")
        self.status_label.setObjectName("connectionStatus")
        self.status_label.setProperty("state", "disconnected")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self.status_label.setMinimumHeight(23)
        self.status_label.setStyleSheet(CONNECTION_STATUS_STYLES["disconnected"])
        adspower_card.header_layout.addWidget(
            self.status_label, 0, Qt.AlignmentFlag.AlignVCenter
        )

        # ----- Local API -----
        api_label = QLabel("Local API")
        api_label.setObjectName("settingLabel")

        self.api_input = Input(
            text=ADSPOWER_DEFAULT_URL,
            editable=False,
        )

        # ----- API Key -----
        api_key_label = QLabel("API key")
        api_key_label.setObjectName("apiKeyLabel")

        self.api_key_input = Input(
            editable=True,
            password=True,
        )
        self.api_key_input.setPlaceholderText("Enter API key")
        self.api_key_input.setText(self._saved_api_key)

        api_form_layout = QVBoxLayout()
        api_form_layout.setContentsMargins(0, 0, 0, 0)
        api_form_layout.setSpacing(self.FORM_SPACING)

        api_form_layout.addWidget(api_label)
        api_form_layout.addWidget(self.api_input)
        api_form_layout.addWidget(api_key_label)
        api_form_layout.addWidget(self.api_key_input)

        adspower_layout.addLayout(api_form_layout)

        # ----- Connection Buttons -----
        self.test_button = Button(
            text="Test",
            variant="outline",
            color="blue",
        )

        self.connect_button = Button(
            text="Connect",
            icon=ICON_DIR / "play.svg",
            variant="primary",
            color="blue",
            disabled=True,
        )

        connection_button_layout = QHBoxLayout()
        connection_button_layout.setContentsMargins(0, 0, 0, 0)
        connection_button_layout.setSpacing(self.BUTTON_SPACING)
        connection_button_layout.addWidget(self.test_button, 1)
        connection_button_layout.addWidget(self.connect_button, 1)

        adspower_layout.addLayout(connection_button_layout)

        # ----- Auto Reconnect Divider -----
        reconnect_divider = QWidget()
        reconnect_divider.setObjectName("settingDivider")
        adspower_layout.addWidget(reconnect_divider)

        # ----- Auto Reconnect -----
        reconnect_label = QLabel("Auto reconnect")
        reconnect_label.setObjectName("reconnectLabel")

        self.reconnect_switch = ToggleSwitch()
        self.reconnect_switch.setChecked(self._saved_auto_reconnect)

        reconnect_layout = QHBoxLayout()
        reconnect_layout.setContentsMargins(0, 0, 0, 0)
        reconnect_layout.setSpacing(0)
        reconnect_layout.addWidget(reconnect_label)
        reconnect_layout.addStretch()
        reconnect_layout.addWidget(self.reconnect_switch)

        adspower_layout.addLayout(reconnect_layout)

        # ----- Data File & Storage Card -----
        storage_card = SectionCard(
            "Data File & Storage",
            "Manage the workbook and export location",
            header_border=True,
            header_height=63,
            header_margin=(20, 16, 20, 14),
            body_margin=self.CARD_MARGIN,
            body_spacing=self.CARD_SPACING,
            title_object_name="settingCardTitle",
            description_object_name="settingCardSubtitle",
        )
        self._style_section_card(storage_card)
        storage_card.setMinimumHeight(240)
        storage_layout = storage_card.body_layout

        # ----- Default Workbook -----
        workbook_label = QLabel("Default workbook")
        workbook_label.setObjectName("settingLabel")

        self.workbook_input = FilePathInput(
            text=str(DATA_FILE),
        )
        self.workbook_input.browse_button.setEnabled(False)
        self.workbook_input.browse_button.setToolTip(
            "Default workbook location is fixed in src/configs/path.py"
        )

        # ----- Export Folder -----
        export_label = QLabel("Results folder")
        export_label.setObjectName("settingLabel")

        self.export_folder_input = FilePathInput(
            text=str(RESULT_DIR),
        )
        self.export_folder_input.browse_button.setEnabled(False)
        self.export_folder_input.browse_button.setToolTip(
            "Reports are saved in data/results; see src/configs/path.py"
        )

        # ----- Storage Form -----
        storage_form_layout = QVBoxLayout()
        storage_form_layout.setContentsMargins(0, 0, 0, 0)
        storage_form_layout.setSpacing(self.FORM_SPACING)
        storage_form_layout.addWidget(workbook_label)
        storage_form_layout.addWidget(self.workbook_input)
        storage_form_layout.addWidget(export_label)
        storage_form_layout.addWidget(self.export_folder_input)
        storage_layout.addLayout(storage_form_layout)
        storage_layout.addStretch()

        # ----- AdsPower & Storage Row -----
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(SPACE[12])

        content_layout.addWidget(adspower_card, 1)
        content_layout.addWidget(storage_card, 1)

        # ----- Theme & Language -----
        theme_card = self._build_theme_language()
        theme_card.set_disabled(True)

        # ----- Notifications & Application Preferences -----
        settings_row = QHBoxLayout()
        settings_row.setContentsMargins(0, 0, 0, 0)
        settings_row.setSpacing(SPACE[16])

        notifications_card = self._build_notifications()
        notifications_card.set_disabled(True)

        preferences_card = self._build_application_preferences()
        preferences_card.set_disabled(True)

        settings_row.addWidget(notifications_card, 6)
        settings_row.addWidget(preferences_card, 5)

        # ----- Custom Sidebar -----
        sidebar_card = self._build_custom_sidebar()
        sidebar_card.set_disabled(True)

        # ----- Footer -----
        footer = Card()
        footer.setProperty("settingFooter", True)
        footer.setFixedHeight(61)

        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(
            SPACE[12],
            SPACE[12],
            SPACE[12],
            SPACE[12],
        )
        footer_layout.setSpacing(SPACE[12])

        # ----- Unsaved Changes -----
        self.unsaved_status = QWidget()
        self.unsaved_status.setObjectName("unsavedStatus")

        unsaved_layout = QVBoxLayout(self.unsaved_status)
        unsaved_layout.setContentsMargins(0, 0, 0, 0)
        unsaved_layout.setSpacing(2)

        self.unsaved_title = QLabel("Unsaved changes")
        self.unsaved_title.setObjectName("unsavedStatusTitle")

        self.unsaved_description = QLabel(
            "You have pending changes that have not been saved yet"
        )
        self.unsaved_description.setObjectName("unsavedStatusDescription")

        unsaved_layout.addWidget(self.unsaved_title)
        unsaved_layout.addWidget(self.unsaved_description)

        self.unsaved_status.setVisible(False)
        footer_layout.addWidget(self.unsaved_status)

        footer_layout.addStretch()

        # ----- Footer Buttons -----
        self.set_default_button = Button(
            text="Set Default",
            variant="outline",
            color="blue",
        )

        self.set_default_button.setToolTip(
            "Reset the Theme & Language and other UI choices."
        )

        self.save_button = Button(
            text="Save Changes",
            icon=ICON_DIR / "file-save.svg",
            variant="primary",
            color="blue",
        )

        footer_layout.addWidget(self.set_default_button)
        footer_layout.addWidget(self.save_button)

        # ----- Scrollable Settings -----
        # AdsPower Connection through Custom Sidebar scrolls as a single page.
        # The save footer remains outside the scroll area.
        scroll_content = QWidget()
        scroll_content.setObjectName("settingsScrollableContent")
        scroll_content.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(SPACE[16])
        scroll_layout.addLayout(content_layout)
        scroll_layout.addWidget(theme_card)
        scroll_layout.addLayout(settings_row)
        scroll_layout.addWidget(sidebar_card)
        scroll_layout.addStretch(1)

        self.settings_scroll = SmoothScrollArea()
        self.settings_scroll.setObjectName("settingsSmoothScroll")
        self.settings_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.settings_scroll.viewport().setStyleSheet(
            "background: transparent; border: none;"
        )
        self.settings_scroll.setWidgetResizable(True)
        self.settings_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.settings_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.settings_scroll.setWidget(scroll_content)

        # ----- Page Layout -----
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*self.MARGIN)
        layout.setSpacing(self.SPACING)
        layout.addWidget(header)
        layout.addWidget(self.settings_scroll, 1)
        layout.addWidget(footer, 0)

        # ----- Events -----
        self.test_button.clicked.connect(self.test_connection)
        self.connect_button.clicked.connect(self.connect_adspower)

        self.api_key_input.textChanged.connect(self.handle_credentials_changed)
        self.reconnect_switch.toggled.connect(self.toggle_auto_reconnect)
        self.save_button.clicked.connect(self.save_changes)
        self.set_default_button.clicked.connect(self.reset_ui_preferences)

        self.update_actions()
        self._apply_auto_reconnect_setting(run_immediately=True)

    # ----- UI Preferences -----
    def _load_ui_preferences(self) -> dict:
        values = {}
        for name, default in self.UI_DEFAULTS.items():
            key = f"settings_ui/{name}"
            value = self.settings.value(key, default, type=type(default))
            if (
                name in self.UI_CHOICE_VALUES
                and value not in self.UI_CHOICE_VALUES[name]
            ):
                value = default
            values[name] = value
        return values

    def _current_ui_preferences(self) -> dict:
        values = {}
        for name, options in self._ui_choice_buttons.items():
            values[name] = next(
                (value for value, button in options.items() if button.isChecked()),
                self.UI_DEFAULTS[name],
            )
        for name, toggle in self._ui_toggles.items():
            values[name] = toggle.isChecked()
        return values

    def _track_ui_choice(self, key: str, value: str, button, group: QButtonGroup):
        group.addButton(button)
        self._ui_choice_buttons.setdefault(key, {})[value] = button
        button.setChecked(self._saved_ui_preferences[key] == value)
        button.toggled.connect(lambda _checked: self.update_actions())

    def _track_ui_toggle(self, key: str, toggle: ToggleSwitch):
        toggle.setChecked(self._saved_ui_preferences[key])
        self._ui_toggles[key] = toggle
        toggle.toggled.connect(lambda _checked: self.update_actions())

    def reset_ui_preferences(self):
        # This resets the draft UI choices, not AdsPower credentials or OS settings.
        for key, options in self._ui_choice_buttons.items():
            options[self.UI_DEFAULTS[key]].setChecked(True)
        for key, toggle in self._ui_toggles.items():
            toggle.setChecked(self.UI_DEFAULTS[key])
        self.update_actions()

    # ----- Settings Section Card -----
    @staticmethod
    def _style_section_card(card: SectionCard) -> None:
        card.setProperty("settingSection", True)

    @staticmethod
    def _section_card(title: str, subtitle: str, height: int):
        card = SectionCard(
            title,
            subtitle,
            header_border=True,
            header_height=63,
            header_margin=(20, 16, 20, 14),
            body_margin=(20, 20, 20, 20),
            header_spacing=2,
            title_object_name="settingCardTitle",
            description_object_name="settingCardSubtitle",
        )
        card.setProperty("settingSection", True)
        card.setFixedHeight(height)
        return card, card.body_layout

    @staticmethod
    def _field_title(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("settingsFieldTitle")
        return label

    @staticmethod
    def _vertical_divider(parent=None) -> QFrame:
        # Same 1px slate divider used by the Page Auto Config card.
        divider = QFrame(parent)
        divider.setObjectName("settingsVerticalDivider")
        divider.setFrameShape(QFrame.Shape.NoFrame)
        divider.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        divider.setFixedWidth(1)
        divider.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        divider.setStyleSheet(f"background-color: {CARD_BORDER}; border: none;")
        return divider

    # ----- Theme & Language -----
    def _build_theme_language(self) -> SectionCard:
        card, body_layout = self._section_card(
            "Theme & Language",
            "Customize the appearance and display language of the application.",
            225,
        )
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(16)
        body_layout.addLayout(row, 1)

        theme_column = QWidget(card.body)
        theme_column.setObjectName("settingsThemeColumn")
        theme_layout = QVBoxLayout(theme_column)
        theme_layout.setContentsMargins(0, 0, 0, 0)
        theme_layout.setSpacing(8)
        theme_layout.addWidget(self._field_title("Theme"))

        theme_tiles = QHBoxLayout()
        theme_tiles.setContentsMargins(0, 0, 0, 0)
        theme_tiles.setSpacing(16)
        theme_group = QButtonGroup(self)
        theme_group.setExclusive(True)
        for name in ("Light", "Dark", "System"):
            tile = SettingChoiceTile(name, ICON_DIR / f"theme-{name.lower()}.svg")
            theme_tiles.addWidget(tile, 1)
            self._track_ui_choice("theme", name, tile, theme_group)
        theme_layout.addLayout(theme_tiles)
        theme_layout.addStretch(1)
        row.addWidget(theme_column, 1)
        row.addWidget(self._vertical_divider(card.body))

        language_column = QWidget(card.body)
        language_column.setObjectName("settingsLanguageColumn")
        language_layout = QVBoxLayout(language_column)
        language_layout.setContentsMargins(0, 0, 0, 0)
        language_layout.setSpacing(12)
        language_layout.addWidget(self._field_title("Language"))
        # Three equal columns, matching the Theme selector layout.
        # Only two languages are supported; the third column is reserved.
        language_grid = QGridLayout()
        language_grid.setContentsMargins(0, 0, 0, 0)
        language_grid.setHorizontalSpacing(16)
        language_grid.setVerticalSpacing(0)
        for column in range(3):
            language_grid.setColumnStretch(column, 1)
        language_group = QButtonGroup(self)
        language_group.setExclusive(True)
        for column, name in enumerate(("English", "Vietnamese")):
            option = SettingRadioChoice(name, boxed=True)
            language_grid.addWidget(option, 0, column)
            self._track_ui_choice("language", name, option, language_group)
        # Empty third cell is intentional; do not duplicate a language.
        language_grid.addWidget(QWidget(language_column), 0, 2)
        language_layout.addLayout(language_grid)
        language_layout.addStretch(1)
        row.addWidget(language_column, 1)
        return card

    # ----- Notifications -----
    def _build_notifications(self) -> SectionCard:
        card, body_layout = self._section_card(
            "Notifications", "Manage task and system notifications.", 205
        )
        content = QVBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(8)
        body_layout.addLayout(content, 1)
        rows = (
            (
                (
                    "task_completed",
                    "Task completed notification",
                    "Notify when a task is finished successfully.",
                ),
                (
                    "notification_sound",
                    "Play notification sound",
                    "Play a sound when there is a notification.",
                ),
            ),
            (
                (
                    "task_failed",
                    "Task failed notification",
                    "Notify when a task fails.",
                ),
                (
                    "desktop_notifications",
                    "Desktop notifications",
                    "Show desktop notifications.",
                ),
            ),
        )
        for pair in rows:
            line = QHBoxLayout()
            line.setContentsMargins(0, 0, 0, 0)
            line.setSpacing(8)
            for name, title, description in pair:
                line.addWidget(self._notification_item(name, title, description), 1)
            content.addLayout(line)
        return card

    def _notification_item(self, key: str, title: str, description: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName("settingsNotificationItem")
        frame.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        frame.setStyleSheet(SETTING_NOTIFICATION_ITEM_STYLE)
        frame.setFixedHeight(46)
        row = QHBoxLayout(frame)
        row.setContentsMargins(8, 6, 8, 6)
        row.setSpacing(5)
        copy = QVBoxLayout()
        copy.setContentsMargins(0, 0, 0, 0)
        copy.setSpacing(3)
        label = QLabel(title)
        label.setObjectName("settingsRowTitle")
        label.setMinimumWidth(0)
        description_label = QLabel(description)
        description_label.setObjectName("settingsRowSubtitle")
        description_label.setMinimumWidth(0)
        copy.addWidget(label)
        copy.addWidget(description_label)
        row.addLayout(copy, 1)
        toggle = ToggleSwitch()
        self._track_ui_toggle(key, toggle)
        row.addWidget(toggle)
        return frame

    # ----- Application Preferences -----
    def _build_application_preferences(self) -> SectionCard:
        card, body_layout = self._section_card(
            "Application Preferences",
            "Configure how the application works on your computer.",
            205,
        )
        content = QVBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(8)
        body_layout.addLayout(content, 1)
        preferences = (
            (
                "start_with_windows",
                "Start with Windows",
                "Launch the application when Windows starts.",
            ),
            (
                "minimize_to_tray",
                "Minimize to system tray",
                "Minimize to system tray instead of taskbar.",
            ),
            (
                "confirm_before_close",
                "Confirm before closing",
                "Show confirmation dialog when closing the app.",
            ),
        )
        for name, title, description in preferences:
            line = QHBoxLayout()
            line.setContentsMargins(0, 0, 0, 0)
            line.setSpacing(8)
            copy = QVBoxLayout()
            copy.setContentsMargins(0, 0, 0, 0)
            copy.setSpacing(2)
            title_label = QLabel(title)
            title_label.setObjectName("settingsRowTitle")
            description_label = QLabel(description)
            description_label.setObjectName("settingsPreferenceSubtitle")
            copy.addWidget(title_label)
            copy.addWidget(description_label)
            line.addLayout(copy, 1)
            toggle = ToggleSwitch()
            self._track_ui_toggle(name, toggle)
            line.addWidget(toggle)
            content.addLayout(line)
        return card

    # ----- Custom Sidebar -----
    def _build_custom_sidebar(self) -> SectionCard:
        card, body_layout = self._section_card(
            "Custom Sidebar",
            "Customize sidebar layout and workspace navigation.",
            279,
        )
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(16)
        body_layout.addLayout(row, 1)

        sidebar_column = QWidget(card.body)
        sidebar_column.setObjectName("settingsSidebarColumn")
        sidebar_column.setMaximumWidth(388)
        left = QVBoxLayout(sidebar_column)
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(12)
        left.addWidget(self._field_title("Sidebar Mode"))
        choices = QHBoxLayout()
        choices.setContentsMargins(0, 0, 0, 0)
        choices.setSpacing(16)
        sidebar_group = QButtonGroup(self)
        sidebar_group.setExclusive(True)
        for name, description in (
            ("Expanded", "Show icons and labels"),
            ("Compact", "Show icons only"),
        ):
            tile = SettingChoiceTile(
                name,
                ICON_DIR / f"sidebar-{name.lower()}.svg",
                description=description,
                tile_height=141,
                preview_height=86,
            )
            choices.addWidget(tile, 1)
            self._track_ui_choice("sidebar_mode", name, tile, sidebar_group)
        left.addLayout(choices)
        left.addStretch(1)
        row.addWidget(sidebar_column, 4)
        row.addWidget(self._vertical_divider(card.body))

        split_column = QWidget(card.body)
        split_column.setObjectName("settingsSplitColumn")
        right = QVBoxLayout(split_column)
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(12)
        right.addWidget(self._field_title("Split Page (Workspace)"))
        split_row = QHBoxLayout()
        split_row.setContentsMargins(0, 0, 0, 0)
        split_row.setSpacing(16)

        split_options = QVBoxLayout()
        split_options.setContentsMargins(0, 0, 0, 0)
        split_options.setSpacing(13)
        split_options.addStretch(1)
        split_group = QButtonGroup(self)
        split_group.setExclusive(True)
        for key, title in (
            ("off", "Off – Single page"),
            ("vertical", "Vertical split – Left / Right"),
            ("horizontal", "Horizontal split – Top / Bottom"),
        ):
            option = SettingRadioChoice(title)
            split_options.addWidget(option)
            self._track_ui_choice("split_page", key, option, split_group)
        split_options.addStretch(1)
        split_row.addLayout(split_options, 1)
        split_row.addWidget(
            SettingWorkspacePreview(ICON_DIR / "home-module-selector.svg")
        )
        right.addLayout(split_row)
        right.addStretch(1)
        row.addWidget(split_column, 7)
        return card

    # ----- Path Field -----
    def _create_path_field(self, text: str) -> QWidget:
        field = QWidget()
        field.setObjectName("settingsPathField")
        field.setAttribute(
            Qt.WidgetAttribute.WA_StyledBackground,
            True,
        )

        layout = QGridLayout(field)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.setColumnStretch(0, 1)

        path_input = Input(
            text=text,
            editable=False,
        )
        path_input.setMinimumWidth(120)

        button_size = max(28, path_input.sizeHint().height())
        path_input.setMinimumHeight(button_size)
        path_input.setTextMargins(0, 0, button_size + 4, 0)

        layout.setColumnMinimumWidth(1, button_size)
        layout.addWidget(path_input, 0, 0, 1, 2)

        browse_button = QToolButton(field)
        browse_button.setObjectName("settingsPathBrowseButton")
        browse_button.setIcon(QIcon(str(ICON_DIR / "folder-open.svg")))
        browse_button.setIconSize(QSize(14, 14))
        browse_button.setFixedSize(button_size, button_size)
        browse_button.setCursor(Qt.CursorShape.PointingHandCursor)

        layout.addWidget(
            browse_button,
            0,
            1,
            alignment=(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
        )

        return field

    # ----- Test -----
    def test_connection(self):
        self.start_check("test")

    # ----- Connect -----
    def connect_adspower(self):
        if self.is_connected:
            return

        self.start_check("connect")

    # ----- Check -----
    def start_check(self, action: str):
        if self.check_worker is not None:
            return

        local_api = ADSPOWER_DEFAULT_URL.strip()

        if action == "auto":
            api_key = self._saved_api_key
        else:
            api_key = self.api_key_input.text().strip()

        if not local_api:
            self.notifications.warning(
                "AdsPower",
                "Local API URL is required.",
                5000,
            )
            return

        if not api_key:
            if action != "auto":
                self.notifications.warning(
                    "AdsPower",
                    "Please enter your API key before testing or connecting.",
                    5000,
                )
            return

        self.check_action = action
        self._check_local_api = local_api
        self._check_api_key = api_key

        self.set_connection_state("testing")

        self.check_worker = AdsPowerCheckWorker(
            local_api,
            api_key,
        )
        self.check_worker.result.connect(self.handle_check_result)
        self.check_worker.finished.connect(self.clear_check_worker)

        self.update_actions()

        if action != "auto":
            cmd_log("INFO", f"AdsPower {action} started.")

        self.check_worker.start()

    # ----- Check Result -----
    def handle_check_result(self, success: bool, error: str):
        action = self.check_action or "unknown"
        was_connected = self.is_connected

        if success:
            if action in ("connect", "auto"):
                self.set_connected()
            elif self.is_connected:
                self.set_connection_state("connected")
            else:
                self.set_connection_state("disconnected")

            if action == "test":
                self.notifications.success(
                    "AdsPower Test",
                    "Connection successful.",
                    5000,
                )
                cmd_log(
                    "INFO",
                    "AdsPower Local API test succeeded.",
                )

            elif action == "connect":
                self.notifications.success(
                    "AdsPower Connected",
                    "AdsPower connected successfully.",
                    5000,
                )
                cmd_log(
                    "INFO",
                    "AdsPower connection successful.",
                )

            elif action == "auto" and not was_connected:
                self.notifications.success(
                    "AdsPower Reconnected",
                    "Connection restored successfully.",
                    5000,
                )
                cmd_log(
                    "INFO",
                    "AdsPower auto reconnect successful.",
                )

            return

        if action == "auto":
            self.set_disconnected()
            return

        if action == "connect" or self.is_connected:
            self.set_disconnected()
        else:
            self.set_connection_state("disconnected")

        message = self._get_notification_error(error or "")
        self.notifications.error("AdsPower", message, 5000)

        cmd_log(
            "ERROR",
            f"AdsPower {action} failed: {error or 'Unknown error.'}",
        )

    def clear_check_worker(self):
        if self.check_worker:
            self.check_worker.deleteLater()
            self.check_worker = None

        self.check_action = None
        self.update_actions()

    # ----- Connected -----
    def set_connected(self):
        self.is_connected = True

        self.connected_local_api = (
            self._check_local_api or self.api_input.text().strip()
        )
        self.connected_api_key = (
            self._check_api_key or self.api_key_input.text().strip()
        )

        set_credentials(
            self.connected_api_key,
            api_url=self.connected_local_api,
        )

        self._set_app_connection_state(True)
        self.set_connection_state("connected")

    def set_disconnected(self):
        self.is_connected = False

        self.connected_local_api = ""
        self.connected_api_key = ""

        self._set_app_connection_state(False)
        self.set_connection_state("disconnected")
        clear_credentials()

    # ----- Credentials -----
    def handle_credentials_changed(self, _text: str = ""):
        # Editing the API key only marks the form as dirty.
        # Persistence happens exclusively in save_changes().
        self.update_actions()

    def _save_api_key(self, api_key: str):
        api_key = api_key.strip()

        if api_key:
            self.settings.setValue("adspower/api_key", api_key)
        else:
            self.settings.remove("adspower/api_key")

    # ----- Save Changes -----
    def save_changes(self):
        if self.check_worker is not None:
            return

        api_key = self.api_key_input.text().strip()
        auto_reconnect = self.reconnect_switch.isChecked()

        # If the saved API key changes, reset a connection using
        # different credentials before applying the new settings.
        if self.is_connected and api_key != self.connected_api_key:
            self.set_disconnected()

        self._save_api_key(api_key)

        self.settings.setValue(
            "adspower/auto_reconnect",
            bool(auto_reconnect),
        )
        current_ui = self._current_ui_preferences()
        for name, value in current_ui.items():
            self.settings.setValue(f"settings_ui/{name}", value)
        self.settings.sync()

        if self.settings.status() != QSettings.Status.NoError:
            self.notifications.error("Settings", "Unable to save changes.", 5000)
            return

        self._saved_api_key = api_key
        self._saved_auto_reconnect = bool(auto_reconnect)
        self._saved_ui_preferences = current_ui

        self._apply_auto_reconnect_setting(run_immediately=True)
        self.update_actions()

    # ----- Unsaved Changes -----
    def _has_unsaved_changes(self) -> bool:
        current_api_key = self.api_key_input.text().strip()
        current_auto_reconnect = self.reconnect_switch.isChecked()

        return (
            current_api_key != self._saved_api_key
            or current_auto_reconnect != self._saved_auto_reconnect
            or self._current_ui_preferences() != self._saved_ui_preferences
        )

    def _update_unsaved_state(self):
        has_changes = self._has_unsaved_changes()
        is_running = self.check_worker is not None

        self.unsaved_status.setVisible(has_changes)

        self.save_button.set_disabled(is_running or not has_changes)

    # ----- Auto Reconnect -----
    def toggle_auto_reconnect(self, _checked: bool):
        self.update_actions()

    def _apply_auto_reconnect_setting(
        self,
        run_immediately: bool = False,
    ):
        should_reconnect = self._saved_auto_reconnect and bool(self._saved_api_key)

        if not should_reconnect:
            self.reconnect_timer.stop()
            return

        self.reconnect_timer.start()

        if run_immediately and not self.is_connected:
            QTimer.singleShot(0, self.auto_reconnect)

    def auto_reconnect(self):
        if not self._saved_auto_reconnect or not self._saved_api_key:
            return

        if self.is_connected or self.check_worker is not None:
            return

        self.start_check("auto")

    # ----- Actions -----
    def update_actions(self):
        is_running = self.check_worker is not None
        has_api_key = bool(self.api_key_input.text().strip())

        self.api_key_input.setEnabled(not is_running)

        self.test_button.set_disabled(is_running or not has_api_key)

        self.connect_button.set_disabled(is_running or not has_api_key)

        self.set_default_button.set_disabled(is_running)

        self._update_unsaved_state()

    # ----- Status -----
    def set_connection_state(self, state: str):
        states = {
            "connected": "● Connected",
            "disconnected": "● Disconnected",
            "testing": "● Testing...",
        }

        self.status_label.setText(states[state])
        self.status_label.setProperty("state", state)
        self.status_label.setStyleSheet(CONNECTION_STATUS_STYLES[state])

        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def _set_app_connection_state(self, connected: bool) -> None:
        app = QApplication.instance()

        if app is not None:
            app.setProperty("adspower_connected", bool(connected))

    # ----- Close -----
    def closeEvent(self, event):
        self.reconnect_timer.stop()

        workers = []

        for name in ("worker", "preflight_worker", "check_worker"):
            worker = getattr(self, name, None)

            if worker is not None and all(
                worker is not existing for existing in workers
            ):
                workers.append(worker)

        for worker in workers:
            if not worker.isRunning():
                continue

            request_stop = getattr(worker, "request_stop", None)

            if callable(request_stop):
                request_stop()

            worker.quit()

        for worker in workers:
            if worker.isRunning():
                worker.wait()

        super().closeEvent(event)

    # ----- Notification Error -----
    def _get_notification_error(self, error: str) -> str:
        error_text = str(error or "").strip()
        error_lower = error_text.lower()

        if "10061" in error_lower or "actively refused" in error_lower:
            return "Could not connect to AdsPower. " "Make sure AdsPower is running."

        if (
            "401" in error_lower
            or "unauthorized" in error_lower
            or "invalid api key" in error_lower
        ):
            return "AdsPower rejected the API key. " "Check your API key and try again."

        return error_text or (
            "Could not connect to AdsPower. "
            "Check that AdsPower is running and the API key is correct."
        )
