from PySide6.QtWidgets import (
    QHBoxLayout,
    QStackedWidget,
    QWidget,
)

from src.components.sidebar import Sidebar
from src.pages.page_auto import PageAutoPage


class MainLayout(QWidget):

    # ----- Settings -----
    MARGINS = (0, 0, 0, 0)
    SPACING = 0

    DEFAULT_PAGE = "page_auto"

    def __init__(self):
        super().__init__()

        # ----- Sidebar -----
        self.sidebar = Sidebar()

        # ----- Pages -----
        self.content = QStackedWidget()
        self.pages = {
            "page_auto": PageAutoPage(),
        }

        for page in self.pages.values():
            self.content.addWidget(page)

        self.sidebar.nav_list.page_selected.connect(self.change_page)
        self.change_page(self.DEFAULT_PAGE)
        self.sidebar.nav_list.set_active_page(self.DEFAULT_PAGE)

        # ----- Main Layout -----
        layout = QHBoxLayout(self)
        layout.setContentsMargins(*self.MARGINS)
        layout.setSpacing(self.SPACING)

        layout.addWidget(self.sidebar)
        layout.addWidget(self.content)

    # ----- Change Page -----
    def change_page(self, page_name):
        page = self.pages.get(page_name)

        if page is not None:
            self.content.setCurrentWidget(page)
