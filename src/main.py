import sys
from pathlib import Path

from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication

from src.app import App
from src.configs.setting import APP_NAME
from src.themes.font import (
    FONT_FAMILY,
    FONT_SIZE_14,
)


def main():
    app = QApplication(sys.argv)

    # Font
    font = QFont(FONT_FAMILY)
    font.setPixelSize(FONT_SIZE_14)
    app.setFont(font)

    # App Name
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_NAME)

    # Logo
    logo_path = Path(__file__).resolve().parent / "assets" / "images" / "logo.png"

    if logo_path.exists():
        app.setWindowIcon(QIcon(str(logo_path)))

    window = App()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
