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
from src.components.input import Input
from src.components.page_header import PageHeader
from src.components.toggle_switch import ToggleSwitch

from src.configs.adspower import ADSPOWER_DEFAULT_URL

from src.features.adspower.client import (
    AdsPowerClient,
    AdsPowerError,
)

from src.styles.setting_style import SETTING_STYLE

ICON_DIR = Path(__file__).resolve().parent.parent / "assets" / "icons"


class SettingPage(QWidget):

    # ----- Settings -----
    MARGIN = (32, 32, 32, 32)
    SPACING = 20

    CARD_MARGIN = (16, 14, 16, 14)
    CARD_SPACING = 16

    FORM_SPACING = 8
    BUTTON_SPACING = 8

    AUTO_RECONNECT_DEFAULT = False
    AUTO_RECONNECT_INTERVAL = 30000

    def __init__(self):
        super().__init__()

        self.setStyleSheet(SETTING_STYLE)

        # ----- State -----
        self.adspower_client = None
        self.is_connected = False

        self.reconnect_timer = QTimer(self)
        self.reconnect_timer.setInterval(self.AUTO_RECONNECT_INTERVAL)
        self.reconnect_timer.timeout.connect(self.auto_reconnect)

        # ----- Header -----
        header = PageHeader(
            title="Settings",
            subtitle="Manage connections, automation, and alerts for your workspace.",
        )

        # ----- Card -----
        card = QWidget()
        card.setObjectName("adsPowerCard")

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
        title_layout.setSpacing(2)
        title_layout.addWidget(title_label)
        title_layout.addWidget(subtitle_label)

        # ----- Connection Status -----
        self.status_label = QLabel("● Disconnected")
        self.status_label.setObjectName("connectionStatus")
        self.status_label.setProperty("state", "disconnected")
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

        form_layout = QVBoxLayout()
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(self.FORM_SPACING)
        form_layout.addWidget(api_label)
        form_layout.addWidget(self.api_input)

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
        button_layout.addWidget(self.test_button, 1)
        button_layout.addWidget(self.connect_button, 1)

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
        reconnect_layout.setContentsMargins(0, 0, 0, 0)
        reconnect_layout.setSpacing(0)
        reconnect_layout.addWidget(reconnect_label)
        reconnect_layout.addStretch()
        reconnect_layout.addWidget(self.reconnect_switch)

        card_layout.addLayout(reconnect_layout)

        # ----- Content -----
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)
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

        self.update_actions()

    # ----- Actions -----
    def update_actions(self):
        self.connect_button.setEnabled(not self.is_connected)

    # ----- Test Connection -----
    def test_connection(self):
        was_connected = self.is_connected

        self.set_connection_state("testing")
        self.test_button.setEnabled(False)
        self.connect_button.setEnabled(False)

        try:
            if was_connected and self.adspower_client:
                self.adspower_client.check_connection()

            else:
                client = AdsPowerClient(self.api_input.text())

                try:
                    client.check_connection()
                finally:
                    client.close()

        except AdsPowerError as error:
            print(f"AdsPower Test: Failed - {error}")

            if was_connected:
                self.disconnect_adspower()
            else:
                self.set_connection_state("disconnected")

            QMessageBox.warning(self, "AdsPower Test", str(error))
            return

        finally:
            self.test_button.setEnabled(True)
            self.update_actions()

        print("AdsPower Test: Success")

        if was_connected:
            self.set_connection_state("connected")
        else:
            self.set_connection_state("disconnected")

        QMessageBox.information(
            self,
            "AdsPower Test",
            "Local API is working.",
        )

    # ----- Connect -----
    def connect_adspower(self, silent=False):
        if self.is_connected:
            return True

        self.set_connection_state("testing")
        self.test_button.setEnabled(False)
        self.connect_button.setEnabled(False)

        client = AdsPowerClient(self.api_input.text())

        try:
            client.check_connection()

        except AdsPowerError as error:
            client.close()

            self.is_connected = False
            self.set_connection_state("disconnected")

            print(f"AdsPower: Disconnected - {error}")

            if not silent:
                QMessageBox.warning(self, "AdsPower", str(error))

            self.test_button.setEnabled(True)
            self.update_actions()

            return False

        if self.adspower_client:
            self.adspower_client.close()

        self.adspower_client = client
        self.is_connected = True

        self.set_connection_state("connected")

        self.test_button.setEnabled(True)
        self.update_actions()

        print(f"AdsPower: Connected - {self.api_input.text()}")

        return True

        # ----- Disconnect -----

    def disconnect_adspower(self):
        if self.adspower_client:
            self.adspower_client.close()
            self.adspower_client = None

        self.is_connected = False

        self.set_connection_state("disconnected")
        self.update_actions()

        print("AdsPower: Disconnected")

    # ----- Auto Reconnect -----
    def toggle_auto_reconnect(self, checked: bool):
        if checked:
            self.reconnect_timer.start()

            if not self.is_connected:
                self.connect_adspower(silent=True)

        else:
            self.reconnect_timer.stop()

    def auto_reconnect(self):
        if self.is_connected and self.adspower_client:
            try:
                self.adspower_client.check_connection()
                return

            except AdsPowerError:
                self.disconnect_adspower()

        self.connect_adspower(silent=True)

    # ----- Connection State -----
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

    # ----- Close -----
    def closeEvent(self, event):
        self.reconnect_timer.stop()

        if self.adspower_client:
            self.adspower_client.close()

        super().closeEvent(event)
