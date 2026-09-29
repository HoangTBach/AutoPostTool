from src.themes.color import (
    BUTTON_BORDER,
    BUTTON_COLORS,
    BUTTON_WHITE,
)

from src.themes.font import FONT_WEIGHT_SEMIBOLD

BUTTON_STYLE = f"""
QPushButton#button {{
    background-color: transparent;
    border: 1px solid {BUTTON_BORDER};
    border-radius: 8px;
}}

QLabel#buttonText {{
    background-color: transparent;
    font-weight: {FONT_WEIGHT_SEMIBOLD};
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
        color: {BUTTON_WHITE};
    }}

    QPushButton#button[variant="primary"][color="{name}"]:hover {{
        background-color: {color["hover"]};
        border-color: {color["hover"]};
    }}
    """
