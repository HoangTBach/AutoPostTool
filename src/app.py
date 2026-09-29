from PySide6.QtWidgets import QMainWindow

from src.configs.setting import (
    WINDOW_TITLE,
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    WINDOW_MIN_WIDTH,
    WINDOW_MIN_HEIGHT,
)

from src.layouts.main_layout import MainLayout
from src.styles.app_style import APP_STYLE


class App(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle(WINDOW_TITLE)

        self.resize(
            WINDOW_WIDTH,
            WINDOW_HEIGHT,
        )

        self.setMinimumSize(
            WINDOW_MIN_WIDTH,
            WINDOW_MIN_HEIGHT,
        )
        self.setStyleSheet(APP_STYLE)

        # Set Layout
        self.setCentralWidget(MainLayout())
