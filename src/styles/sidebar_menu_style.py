from src.themes.color import COLORS
from src.themes.font import FONTS
from src.themes.radius import RADIUS

# ----- Colors -----
MENU_TEXT = COLORS["slate"][400]
MENU_TEXT_HOVER = COLORS["blue"][600]
MENU_BG_HOVER = COLORS["slate"][800]
MENU_TEXT_ACTIVE = COLORS["blue"][600]
MENU_BG_ACTIVE = COLORS["slate"][800]


SIDEBAR_MENU_STYLE = f"""
QPushButton#menuButton {{
    background-color: transparent;
    border: none;
    border-radius: {RADIUS["medium"]}px;
}}

QLabel#menuButtonText {{
    background-color: transparent;
    color: {MENU_TEXT};
    font-weight: {FONTS["weight"]["medium"]};
}}
"""
