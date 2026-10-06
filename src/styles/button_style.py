from src.themes.border import BORDERS
from src.themes.color import COLORS
from src.themes.font import FONTS
from src.themes.radius import RADIUS

# ----- Colors -----
TRANSPARENT = COLORS["transparent"]
BUTTON_WHITE = COLORS["neutral"]["white"]
BUTTON_BORDER = COLORS["slate"]["input_border"]

BUTTON_COLORS = {
    "blue": {
        "base": COLORS["blue"][600],
        "hover": COLORS["blue"][600],
        "hover_bg": COLORS["blue"][50],
    },
    "green": {
        "base": COLORS["emerald"][500],
        "hover": COLORS["emerald"][500],
        "hover_bg": COLORS["emerald"][50],
    },
    "red": {
        "base": COLORS["red"][500],
        "hover": COLORS["red"][600],
        "hover_bg": COLORS["red"][50],
    },
    "gray": {
        "base": COLORS["slate"][400],
        "hover": COLORS["slate"][400],
        "hover_bg": COLORS["slate"][50],
    },
}

# ----- Border -----
BORDER_WIDTH = BORDERS["width"]["default"]


BUTTON_STYLE = f"""
QPushButton#button {{
    background-color: {TRANSPARENT};
    border: {BORDER_WIDTH}px solid {BUTTON_BORDER};
    border-radius: {RADIUS["medium"]}px;
}}

QLabel#buttonText {{
    background-color: {TRANSPARENT};
    font-size: {FONTS["size"][14]}px;
    font-weight: {FONTS["weight"]["semibold"]};
}}
"""

for name, color in BUTTON_COLORS.items():
    BUTTON_STYLE += f"""
    /* ----- Outline ----- */

    QPushButton#button[variant="outline"][color="{name}"] {{
        background-color: {BUTTON_WHITE};
        border-color: {BUTTON_BORDER};
    }}

    QPushButton#button[variant="outline"][color="{name}"]:hover {{
        background-color: {color["hover_bg"]};
        border-color: {color["base"]};
    }}

    /* ----- Primary ----- */

    QPushButton#button[variant="primary"][color="{name}"] {{
        background-color: {color["base"]};
        border-color: {color["base"]};
    }}

    QPushButton#button[variant="primary"][color="{name}"]:hover {{
        background-color: {color["hover"]};
        border-color: {color["hover"]};
    }}
    """
