from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QVBoxLayout,
    QWidget,
)

from src.components.menu_button import MenuButton
from src.configs.menu import MENU_ITEMS


class NavList(QWidget):

    # ----- Settings -----
    SPACING = 12

    # ----- Navigation Signal -----
    page_selected = Signal(str)

    def __init__(self):
        super().__init__()

        self.buttons = []

        # ----- Navigation Layout -----
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self.SPACING)

        # ----- Top Menu -----
        for item in MENU_ITEMS["top"]:
            layout.addWidget(self.create_button(item))

        layout.addStretch()

        # ----- Bottom Menu -----
        for item in MENU_ITEMS["bottom"]:
            layout.addWidget(self.create_button(item))

    # ----- Create Menu Button -----
    def create_button(self, item):
        button = MenuButton(
            icon=item["icon"],
            name=item["name"],
            page=item["page"],
        )

        button.clicked.connect(
            lambda checked=False, button=button: self.select_button(button)
        )

        self.buttons.append(button)

        return button

    # ----- Select Menu Button -----
    def select_button(self, selected_button):
        for button in self.buttons:
            button.set_active(button is selected_button)

        self.page_selected.emit(selected_button.page)

    # ----- Set Active Page -----
    def set_active_page(self, page_name):
        for button in self.buttons:
            button.set_active(button.page == page_name)
