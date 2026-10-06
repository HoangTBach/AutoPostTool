from src.themes.color import COLORS
from src.themes.font import FONTS
from src.themes.radius import RADIUS

# ----- Colors -----
CARD_BG = COLORS["neutral"]["white"]
CARD_BORDER = COLORS["slate"][200]
CARD_TITLE = COLORS["slate"][500]
CARD_DESCRIPTION = COLORS["slate"][400]
TEXT_COLOR = COLORS["slate"][900]

STAT_COLORS = {
    "blue": {
        "base": COLORS["blue"][600],
        "bg": COLORS["blue"][50],
    },
    "green": {
        "base": COLORS["emerald"][500],
        "bg": COLORS["emerald"][50],
    },
    "purple": {
        "base": COLORS["violet"][500],
        "bg": COLORS["violet"][50],
    },
    "red": {
        "base": COLORS["red"][500],
        "bg": COLORS["red"][50],
    },
}


CARD_STYLE = f"""
QWidget#card {{
    background-color: {CARD_BG};
    border: 1px solid {CARD_BORDER};
    border-radius: {RADIUS["card"]}px;
}}

QLabel#statTitle {{
    background-color: transparent;
    color: {CARD_TITLE};
    border: none;
    font-size: {FONTS["size"][11]}px;
    font-weight: {FONTS["weight"]["semibold"]};
}}

QLabel#statValue {{
    background-color: transparent;
    color: {TEXT_COLOR};
    border: none;
    font-size: {FONTS["size"][20]}px;
    font-weight: {FONTS["weight"]["bold"]};
}}

QLabel#statDescription {{
    background-color: transparent;
    color: {CARD_DESCRIPTION};
    border: none;
    font-size: {FONTS["size"][10]}px;
    font-weight: {FONTS["weight"]["regular"]};
}}

QWidget#tableCardHeader {{
    background-color: transparent;
    border: none;
}}

QLabel#tableCardTitle {{
    background-color: transparent;
    color: {CARD_TITLE};
    border: none;
    font-weight: {FONTS["weight"]["semibold"]};
}}

QWidget#tableCardBody {{
    background-color: transparent;
    border: none;
}}
"""
