from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QLabel,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

from src.configs.setting import SIDEBAR_NAME, SIDEBAR_META
from src.styles.sidebar_header_style import SIDEBAR_HEADER_STYLE


class SidebarHeader(QWidget):

    # ----- Settings -----
    LOGO_SIZE = 36
    SPACING = 12

    def __init__(self):
        super().__init__()

        # ----- Logo Icon -----
        logo = QLabel()
        logo.setFixedSize(
            self.LOGO_SIZE,
            self.LOGO_SIZE,
        )

        logo_path = (
            Path(__file__).resolve().parent.parent / "assets" / "images" / "logo.png"
        )

        if logo_path.exists():
            pixmap = QPixmap(str(logo_path))

            logo.setPixmap(
                pixmap.scaled(
                    self.LOGO_SIZE,
                    self.LOGO_SIZE,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )

        # ----- Icon Text -----
        app_name = QLabel(SIDEBAR_NAME)
        app_name.setObjectName("sidebarAppName")

        app_meta = QLabel(SIDEBAR_META)
        app_meta.setObjectName("sidebarAppMeta")

        # ----- Text Layout -----
        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)

        text_layout.addWidget(app_name)
        text_layout.addWidget(app_meta)

        # ----- Header Layout -----
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self.SPACING)

        layout.addWidget(logo)
        layout.addLayout(text_layout)
        layout.addStretch()

        # ----- Style -----
        self.setStyleSheet(SIDEBAR_HEADER_STYLE)
