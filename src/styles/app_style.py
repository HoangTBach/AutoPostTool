from src.themes.color import COLORS
from src.themes.font import FONTS
from src.themes.radius import RADIUS
from src.themes.spacing import SPACING

# ----- Colors -----
BG_COLOR = COLORS["slate"][50]
TEXT_COLOR = COLORS["slate"][900]

MESSAGE_BG = COLORS["neutral"]["white"]
MESSAGE_BUTTON_BG = COLORS["blue"][600]
MESSAGE_BUTTON_TEXT = COLORS["neutral"]["white"]


APP_STYLE = f"""
QMainWindow {{
    background-color: {BG_COLOR};
}}

QWidget {{
    color: {TEXT_COLOR};
    font-family: "{FONTS["family"]["primary"]}";
}}

QMessageBox {{
    background-color: {MESSAGE_BG};
}}

QMessageBox QLabel {{
    color: {TEXT_COLOR};
    background-color: transparent;
}}

QMessageBox QPushButton {{
    min-width: 70px;

    padding: {SPACING["legacy"][6]}px {SPACING[16]}px;

    color: {MESSAGE_BUTTON_TEXT};
    background-color: {MESSAGE_BUTTON_BG};

    border: none;
    border-radius: {RADIUS["input"]}px;
}}

QMessageBox QPushButton:hover {{
    background-color: {MESSAGE_BUTTON_BG};
}}
"""
