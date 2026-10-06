import sys
from pathlib import Path

from PySide6.QtGui import (
    QFont,
    QFontDatabase,
    QIcon,
)
from PySide6.QtWidgets import QApplication

from src.app import App
from src.configs.setting import APP_NAME
from src.themes.font import FONTS


def main():
    app = QApplication(sys.argv)

    # ----- Font -----
    font_dir = Path(__file__).resolve().parent / "assets" / "fonts"

    for font_file in font_dir.glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(font_file))

    font = QFont(FONTS["family"]["primary"])
    font.setPixelSize(FONTS["size"][14])
    app.setFont(font)

    # ----- Logo -----
    logo_path = Path(__file__).resolve().parent / "assets" / "images" / "logo.png"

    if logo_path.exists():
        app.setWindowIcon(QIcon(str(logo_path)))

    # ----- App -----
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_NAME)

    window = App()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
