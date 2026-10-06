from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QVBoxLayout,
    QWidget,
)

from src.components.sidebar_header import SidebarHeader
from src.components.sidebar_nav_list import NavList
from src.styles.sidebar_style import SIDEBAR_STYLE
from src.themes.spacing import SPACING as SPACE


class Sidebar(QWidget):

    # ----- Settings -----
    WIDTH = 260
    MARGIN = (SPACE[16], SPACE[24], SPACE[16], SPACE[24])
    SPACING = SPACE[32]

    def __init__(self):
        super().__init__()

        # ----- Sidebar Setup -----
        self.setObjectName("sidebar")
        self.setFixedWidth(self.WIDTH)

        self.setAttribute(
            Qt.WidgetAttribute.WA_StyledBackground,
            True,
        )

        self.setStyleSheet(SIDEBAR_STYLE)

        # ----- Sidebar Components -----
        self.header = SidebarHeader()
        self.nav_list = NavList()

        # ----- Sidebar Layout -----
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*self.MARGIN)
        layout.setSpacing(self.SPACING)

        layout.addWidget(self.header)
        layout.addWidget(self.nav_list, 1)
