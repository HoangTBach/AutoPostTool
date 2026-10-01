from pathlib import Path

from PySide6.QtCore import (
    Qt,
    QTimer,
)
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from src.components.page_header import PageHeader
from src.components.input import Input
from src.components.button import Button
from src.components.toggle_switch import ToggleSwitch

from src.features.adspower.client import (
    AdsPowerClient,
    AdsPowerError,
)
from src.features.adspower.settings import (
    load_adspower_settings,
    save_adspower_settings,
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

    def __init__(self):
        super().__init__()

        self.setStyleSheet(SETTING_STYLE)

        # ----- Data -----
        settings = load_adspower_settings()

        # ----- Header -----
        header = PageHeader(
            title="Settings",
            subtitle=(
                "Manage connections, automation, " "and alerts for your workspace."
            ),
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
            self.status_label, alignment=Qt.AlignmentFlag.AlignVCenter
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
            text=settings["local_api"],
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

        self.reconnect_switch.setChecked(settings["auto_reconnect"])

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

        self.reconnect_switch.toggled.connect(self.save_settings)

        # ----- Auto Reconnect -----
        if settings["auto_reconnect"]:
            QTimer.singleShot(200, self.connect_adspower)

    # ----- Test Connection -----
    def test_connection(self):
        self.set_connection_state("testing")

        try:
            client = AdsPowerClient(self.api_input.text())

            client.check_connection()

        except AdsPowerError as error:
            self.set_connection_state("disconnected")

            QMessageBox.warning(self, "AdsPower", str(error))

            return

        self.set_connection_state("connected")

    # ----- Connect -----
    def connect_adspower(self):
        self.set_connection_state("testing")

        try:
            client = AdsPowerClient(self.api_input.text())

            client.check_connection()

        except AdsPowerError:
            self.set_connection_state("disconnected")

            return

        self.set_connection_state("connected")

        self.save_settings()

    # ----- Save Settings -----
    def save_settings(self, *_):
        save_adspower_settings(
            local_api=self.api_input.text(),
            auto_reconnect=(self.reconnect_switch.isChecked()),
        )

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
