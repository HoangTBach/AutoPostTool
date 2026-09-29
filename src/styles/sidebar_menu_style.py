from src.themes.color import MENU_TEXT

from src.themes.font import (
    FONT_WEIGHT_MEDIUM,
)

SIDEBAR_MENU_STYLE = f"""
QPushButton#menuButton {{
    background-color: transparent;
    border: none;
    border-radius: 8px;

}}

QLabel#menuButtonText {{
    background-color: transparent;
    color: {MENU_TEXT};
    font-weight: {FONT_WEIGHT_MEDIUM};
}}
"""
