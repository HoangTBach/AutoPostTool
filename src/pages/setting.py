from pathlib import Path

from PySide6.QtCore import QSettings, QSize, Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from src.components.button import Button
from src.components.card import Card
from src.components.input import Input
from src.components.file_path_input import FilePathInput
from src.components.notification import NotificationManager
from src.components.page_header import PageHeader
from src.components.toggle_switch import ToggleSwitch
from src.configs.adspower import ADSPOWER_DEFAULT_URL
from src.features.adspower.worker import AdsPowerCheckWorker
from src.features.page_posting.adspower import clear_credentials, set_credentials
from src.styles.setting_style import SETTING_STYLE
from src.themes.spacing import SPACING as SPACE
from src.utils.cmd_log import cmd_log

ICON_DIR = Path(__file__).resolve().parent.parent / "assets" / "icons"


SETTING_PAGE_STYLE = """
QWidget#settingsPage {
    background-color: transparent;
    border: none;
}

QWidget#settingsPathField {
    background-color: transparent;
    border: none;
}

QToolButton#settingsPathBrowseButton {
    background-color: transparent;
    border: none;
    padding: 0;
}

QLabel#settingFooterTitle {
    color: #0F172A;
    background-color: transparent;
    border: none;
    font-size: 12px;
    font-weight: 600;
}

QLabel#settingFooterSubtitle {
    color: #94A3B8;
    background-color: transparent;
    border: none;
    font-size: 10px;
    font-weight: 400;
}
"""


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

        self.setStyleSheet(SETTING_STYLE + SETTING_PAGE_STYLE)

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
        adspower_card = Card()
        adspower_card.setMinimumHeight(240)

        adspower_layout = QVBoxLayout(adspower_card)
        adspower_layout.setContentsMargins(*self.CARD_MARGIN)
        adspower_layout.setSpacing(self.CARD_SPACING)

        # ----- AdsPower Header -----
        adspower_title = QLabel("AdsPower Connection")
        adspower_title.setObjectName("settingCardTitle")

        adspower_subtitle = QLabel("Connect your AdsPower workspace and local API")
        adspower_subtitle.setObjectName("settingCardSubtitle")

        title_layout = QVBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(SPACE[2])
        title_layout.addWidget(adspower_title)
        title_layout.addWidget(adspower_subtitle)

        # ----- Connection Status -----
        self.status_label = QLabel("● Disconnected")
        self.status_label.setObjectName("connectionStatus")
        self.status_label.setProperty("state", "disconnected")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        adspower_header_layout = QHBoxLayout()
        adspower_header_layout.setContentsMargins(0, 0, 0, 0)
        adspower_header_layout.addLayout(title_layout)
        adspower_header_layout.addStretch()
        adspower_header_layout.addWidget(
            self.status_label,
            alignment=Qt.AlignmentFlag.AlignVCenter,
        )

        adspower_layout.addLayout(adspower_header_layout)

        # ----- Divider -----
        adspower_divider = QWidget()
        adspower_divider.setObjectName("settingDivider")
        adspower_layout.addWidget(adspower_divider)

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
        storage_card = Card()
        storage_card.setMinimumHeight(240)

        storage_layout = QVBoxLayout(storage_card)
        storage_layout.setContentsMargins(*self.CARD_MARGIN)
        storage_layout.setSpacing(self.CARD_SPACING)

        storage_title = QLabel("Data File & Storage")
        storage_title.setObjectName("settingCardTitle")

        storage_subtitle = QLabel("Manage the workbook and export location")
        storage_subtitle.setObjectName("settingCardSubtitle")

        storage_title_layout = QVBoxLayout()
        storage_title_layout.setContentsMargins(0, 0, 0, 0)
        storage_title_layout.setSpacing(SPACE[2])
        storage_title_layout.addWidget(storage_title)
        storage_title_layout.addWidget(storage_subtitle)

        storage_layout.addLayout(storage_title_layout)

        storage_divider = QWidget()
        storage_divider.setObjectName("settingDivider")
        storage_layout.addWidget(storage_divider)

        # ----- Default Workbook -----
        workbook_label = QLabel("Default workbook")
        workbook_label.setObjectName("settingLabel")

        self.workbook_input = FilePathInput(
            text="data/databook.xlsx",
        )

        # ----- Export Folder -----
        export_label = QLabel("Export Folder")
        export_label.setObjectName("settingLabel")

        self.export_folder_input = FilePathInput(
            text="Download/",
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

        # ----- Content -----
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(SPACE[12])

        content_layout.addWidget(adspower_card, 1)
        content_layout.addWidget(storage_card, 1)

        # ----- Footer -----
        footer = Card()
        footer.setMinimumHeight(52)

        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(
            SPACE[16],
            SPACE[12],
            SPACE[16],
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

        self.set_default_button.set_disabled(True)

        self.save_button = Button(
            text="Save Changes",
            icon=ICON_DIR / "file-save.svg",
            variant="primary",
            color="blue",
        )

        footer_layout.addWidget(self.set_default_button)
        footer_layout.addWidget(self.save_button)

        # ----- Page Layout -----
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*self.MARGIN)
        layout.setSpacing(self.SPACING)

        layout.addWidget(header)
        layout.addLayout(content_layout)
        layout.addStretch(1)
        layout.addWidget(footer)

        # ----- Events -----
        self.test_button.clicked.connect(self.test_connection)
        self.connect_button.clicked.connect(self.connect_adspower)

        self.api_key_input.textChanged.connect(self.handle_credentials_changed)
        self.reconnect_switch.toggled.connect(self.toggle_auto_reconnect)
        self.save_button.clicked.connect(self.save_changes)

        self.update_actions()
        self._apply_auto_reconnect_setting(run_immediately=True)

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

        if action in ("connect", "auto") and not api_key:
            if action != "auto":
                self.notifications.warning(
                    "AdsPower",
                    "Please enter your API key before connecting.",
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
            self.connected_local_api,
            self.connected_api_key,
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
        self.settings.sync()

        self._saved_api_key = api_key
        self._saved_auto_reconnect = bool(auto_reconnect)

        self._apply_auto_reconnect_setting(run_immediately=True)
        self.update_actions()

    # ----- Unsaved Changes -----
    def _has_unsaved_changes(self) -> bool:
        current_api_key = self.api_key_input.text().strip()
        current_auto_reconnect = self.reconnect_switch.isChecked()

        return (
            current_api_key != self._saved_api_key
            or current_auto_reconnect != self._saved_auto_reconnect
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

        self.test_button.set_disabled(is_running)

        self.connect_button.set_disabled(is_running or not has_api_key)

        self.set_default_button.set_disabled(True)

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
