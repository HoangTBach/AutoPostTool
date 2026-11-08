from src.themes.border import BORDERS
from src.themes.color import COLORS
from src.themes.font import FONTS
from src.themes.radius import RADIUS

# ----- Colors -----
TRANSPARENT = COLORS["transparent"]
CARD_BG = COLORS["neutral"]["white"]
CARD_BORDER = COLORS["slate"][200]
CARD_TITLE = COLORS["slate"][500]
CARD_DESCRIPTION = COLORS["slate"][400]
TEXT_COLOR = COLORS["slate"][900]

STAT_COLORS = {
    "blue": {"base": COLORS["blue"][600], "bg": COLORS["blue"][50]},
    "green": {"base": COLORS["emerald"][500], "bg": COLORS["emerald"][50]},
    "purple": {"base": COLORS["violet"][500], "bg": COLORS["violet"][50]},
    "red": {"base": COLORS["red"][500], "bg": COLORS["red"][50]},
}

# ----- Border -----
BORDER_WIDTH = BORDERS["width"]["default"]


CARD_STYLE = f"""
QWidget#card {{
    background-color: {CARD_BG};
    border: {BORDER_WIDTH}px solid {CARD_BORDER};
    border-radius: {RADIUS["card"]}px;
}}

QLabel#statTitle {{
    color: {CARD_TITLE};
    background-color: {TRANSPARENT};
    border: none;
    font-size: {FONTS["size"][11]}px;
    font-weight: {FONTS["weight"]["semibold"]};
}}

QLabel#statValue {{
    color: {TEXT_COLOR};
    background-color: {TRANSPARENT};
    border: none;
    font-size: {FONTS["size"][20]}px;
    font-weight: {FONTS["weight"]["bold"]};
}}

QLabel#statDescription {{
    color: {CARD_DESCRIPTION};
    background-color: {TRANSPARENT};
    border: none;
    font-size: {FONTS["size"][10]}px;
    font-weight: {FONTS["weight"]["regular"]};
}}

QWidget#tableCardHeader {{
    background-color: {TRANSPARENT};
    border: none;
}}

QLabel#tableCardTitle {{
    color: {CARD_TITLE};
    background-color: {TRANSPARENT};
    border: none;
    font-weight: {FONTS["weight"]["semibold"]};
}}

QWidget#tableCardBody {{
    background-color: {TRANSPARENT};
    border: none;
}}
"""
<<<<<<< Updated upstream
=======


# ----- Section Card -----
SECTION_CARD_STYLE = f"""
QWidget#sectionCardHeader,
QWidget#sectionCardBody,
QScrollArea#sectionCardScrollArea,
QScrollArea#sectionCardScrollArea > QWidget,
QScrollArea#sectionCardScrollArea > QWidget > QWidget {{
    background: transparent;
    border: none;
}}
QLabel#sectionCardTitle {{
    color: {TEXT_COLOR};
    background: transparent;
    border: none;
    font-size: {FONTS["size"][14]}px;
    font-weight: {FONTS["weight"]["bold"]};
}}
QLabel#sectionCardDescription {{
    color: {CARD_DESCRIPTION};
    background: transparent;
    border: none;
    font-size: {FONTS["size"][12]}px;
    font-weight: {FONTS["weight"]["regular"]};
}}
QFrame#sectionCardHeaderDivider {{
    background-color: {CARD_BORDER};
    border: none;
    min-height: 1px;
    max-height: 1px;
}}
"""

# ----- Scrollable Card -----
SCROLLABLE_CARD_STYLE = f"""
QLabel#scrollableCardTitle {{
    background: transparent;
    border: none;
    color: {TEXT_COLOR};
    font-size: {FONTS["size"][18]}px;
    font-weight: {FONTS["weight"]["bold"]};
}}
QLabel#scrollableCardDescription {{
    background: transparent;
    border: none;
    color: {CARD_TITLE};
    font-size: {FONTS["size"][13]}px;
    font-weight: {FONTS["weight"]["regular"]};
}}
"""
>>>>>>> Stashed changes
