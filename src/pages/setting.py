from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from src.components.button import Button
from src.components.card import Card
from src.components.input import Input
from src.components.page_header import PageHeader
from src.components.toggle_switch import ToggleSwitch
from src.configs.adspower import ADSPOWER_DEFAULT_URL
from src.features.adspower.worker import AdsPowerCheckWorker
from src.styles.setting_style import SETTING_STYLE
from src.themes.spacing import SPACING as SPACE

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

    def __init__(self):
        super().__init__()

        self.setStyleSheet(SETTING_STYLE)

        # ----- State -----
        self.is_connected = False
        self.check_worker = None
        self.check_action = None

        self.connected_local_api = ""
        self.connected_api_key = ""

        self.reconnect_timer = QTimer(self)
        self.reconnect_timer.setInterval(self.AUTO_RECONNECT_INTERVAL)
        self.reconnect_timer.timeout.connect(self.auto_reconnect)

        # ----- Header -----
        header = PageHeader(
            title="Settings",
            subtitle="Manage connections, automation, and alerts for your workspace.",
        )

        # ----- Card -----
        card = Card()

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(*self.CARD_MARGIN)
        card_layout.setSpacing(self.CARD_SPACING)

        # ----- Card Header -----
        title_label = QLabel("AdsPower Connection")
        title_label.setObjectName("settingCardTitle")

        subtitle_label = QLabel("Connect your AdsPower workspace and local API")
        subtitle_label.setObjectName("settingCardSubtitle")

        title_layout = QVBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(SPACE[2])
        title_layout.addWidget(title_label)
        title_layout.addWidget(subtitle_label)

        # ----- Connection Status -----
        self.status_label = QLabel("● Disconnected")
        self.status_label.setObjectName("connectionStatus")
        self.status_label.setProperty(
            "state",
            "disconnected",
        )
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.addLayout(title_layout)
        header_layout.addStretch()
        header_layout.addWidget(
            self.status_label,
            alignment=Qt.AlignmentFlag.AlignVCenter,
        )

        card_layout.addLayout(header_layout)

        # ----- Divider -----
        divider = QWidget()
        divider.setObjectName("settingDivider")

        card_layout.addWidget(divider)

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

        form_layout = QVBoxLayout()
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(self.FORM_SPACING)

        form_layout.addWidget(api_label)
        form_layout.addWidget(self.api_input)

        form_layout.addWidget(api_key_label)
        form_layout.addWidget(self.api_key_input)

        card_layout.addLayout(form_layout)

        # ----- Test Button -----
        self.test_button = Button(
            text="Test",
            variant="outline",
            color="blue",
        )

        # ----- Connect Button -----
        self.connect_button = Button(
            text="Connect",
            icon=ICON_DIR / "play.svg",
            variant="primary",
            color="blue",
        )

        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(self.BUTTON_SPACING)

        button_layout.addWidget(
            self.test_button,
            1,
        )

        button_layout.addWidget(
            self.connect_button,
            1,
        )

        card_layout.addLayout(button_layout)

        # ----- Divider -----
        reconnect_divider = QWidget()
        reconnect_divider.setObjectName("settingDivider")

        card_layout.addWidget(reconnect_divider)

        # ----- Auto Reconnect -----
        reconnect_label = QLabel("Auto reconnect")
        reconnect_label.setObjectName("reconnectLabel")

        self.reconnect_switch = ToggleSwitch()
        self.reconnect_switch.setChecked(self.AUTO_RECONNECT_DEFAULT)

        reconnect_layout = QHBoxLayout()
        reconnect_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        reconnect_layout.setSpacing(0)

        reconnect_layout.addWidget(reconnect_label)
        reconnect_layout.addStretch()
        reconnect_layout.addWidget(self.reconnect_switch)

        card_layout.addLayout(reconnect_layout)

        # ----- Content -----
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        content_layout.setSpacing(SPACE[12])

        content_layout.addWidget(card, 1)
        content_layout.addStretch(1)

        # ----- Page Layout -----
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*self.MARGIN)
        layout.setSpacing(self.SPACING)

        layout.addWidget(header)
        layout.addLayout(content_layout)
        layout.addStretch()

        # ----- Events -----
        self.test_button.clicked.connect(self.test_connection)

        self.connect_button.clicked.connect(self.connect_adspower)

        self.reconnect_switch.toggled.connect(self.toggle_auto_reconnect)

        self.api_key_input.textChanged.connect(self.handle_credentials_changed)

        self.update_actions()

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
        if self.check_worker and self.check_worker.isRunning():
            return

        local_api = self.api_input.text().strip()
        api_key = self.api_key_input.text().strip()

        if not local_api:
            if action != "auto":
                QMessageBox.warning(
                    self,
                    "AdsPower",
                    "Local API is required.",
                )
            return

        if not api_key:
            if action != "auto":
                QMessageBox.warning(
                    self,
                    "AdsPower",
                    "API key is required.",
                )
            return

        self.check_action = action
        self.set_connection_state("testing")

        self.check_worker = AdsPowerCheckWorker(
            local_api,
            api_key,
        )

        self.check_worker.result.connect(self.handle_check_result)
        self.check_worker.finished.connect(self.clear_check_worker)

        self.update_actions()
        self.check_worker.start()

    def handle_check_result(
        self,
        success: bool,
        error: str,
    ):
        action = self.check_action

        if success:
            if action in (
                "connect",
                "auto",
            ):
                self.set_connected()

            elif self.is_connected:
                self.set_connection_state("connected")

            else:
                self.set_connection_state("disconnected")

            if action == "test":
                QMessageBox.information(
                    self,
                    "AdsPower Test",
                    "AdsPower Local API is working.",
                )

            return

        if action == "auto":
            self.set_disconnected()
            return

        if action == "connect":
            self.set_disconnected()

        elif self.is_connected:
            self.set_disconnected()

        else:
            self.set_connection_state("disconnected")

        QMessageBox.warning(
            self,
            "AdsPower",
            error,
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

        self.connected_local_api = self.api_input.text().strip()

        self.connected_api_key = self.api_key_input.text().strip()

        self.set_connection_state("connected")

    def set_disconnected(self):
        self.is_connected = False

        self.connected_local_api = ""
        self.connected_api_key = ""

        self.set_connection_state("disconnected")

    # ----- Credentials -----
    def handle_credentials_changed(self):
        current_api_key = self.api_key_input.text().strip()

        if self.is_connected and current_api_key != self.connected_api_key:
            self.set_disconnected()

        self.update_actions()

    # ----- Auto Reconnect -----
    def toggle_auto_reconnect(
        self,
        checked: bool,
    ):
        if checked:
            self.reconnect_timer.start()

            QTimer.singleShot(
                0,
                self.auto_reconnect,
            )

        else:
            self.reconnect_timer.stop()

    def auto_reconnect(self):
        if self.check_worker and self.check_worker.isRunning():
            return

        self.start_check("auto")

    # ----- Actions -----
    def update_actions(self):
        busy = self.check_worker is not None and self.check_worker.isRunning()
        has_api_key = bool(self.api_key_input.text().strip())

        self.test_button.setEnabled(not busy and has_api_key)

        self.connect_button.setEnabled(
            not busy and has_api_key and not self.is_connected
        )

    # ----- Status -----
    def set_connection_state(
        self,
        state: str,
    ):
        states = {
            "connected": "● Connected",
            "disconnected": "● Disconnected",
            "testing": "● Testing...",
        }

        self.status_label.setText(states[state])

        self.status_label.setProperty(
            "state",
            state,
        )

        self.status_label.style().unpolish(self.status_label)

        self.status_label.style().polish(self.status_label)

    # ----- Close -----
    def closeEvent(self, event):
        self.reconnect_timer.stop()

        if self.check_worker and self.check_worker.isRunning():
            self.check_worker.quit()
            self.check_worker.wait()

        super().closeEvent(event)
