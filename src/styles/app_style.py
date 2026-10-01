from src.themes.color import (
    BG_COLOR,
    BUTTON_COLORS,
    BUTTON_WHITE,
    TEXT_COLOR,
)

APP_STYLE = f"""
QMainWindow {{
    background-color: {BG_COLOR};
}}

QWidget {{
    color: {TEXT_COLOR};
}}

QMessageBox {{
    background-color: {BUTTON_WHITE};
}}

QMessageBox QLabel {{
    color: {TEXT_COLOR};
    background-color: transparent;
}}

QMessageBox QPushButton {{
    min-width: 70px;
    padding: 6px 16px;
    color: {BUTTON_WHITE};
    background-color: {BUTTON_COLORS["blue"]["base"]};
    border: none;
    border-radius: 6px;
}}

QMessageBox QPushButton:hover {{
    background-color: {BUTTON_COLORS["blue"]["hover"]};
}}
"""
