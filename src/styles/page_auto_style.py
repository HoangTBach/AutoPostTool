from src.themes.border import BORDERS
from src.themes.color import COLORS
from src.themes.font import FONTS
from src.themes.radius import RADIUS

# ----- Colors -----
TRANSPARENT = COLORS["transparent"]
TEXT_COLOR = COLORS["slate"][900]
TEXT_SUMMARY = COLORS["slate"][500]
TABLE_BORDER = COLORS["slate"][200]

# ----- Border -----
BORDER_WIDTH = BORDERS["width"]["default"]


PAGE_AUTO_STYLE = f"""
QWidget#pageAutoContent {{
    background-color: {TRANSPARENT};
}}

QLabel#summary_label {{
    color: {TEXT_SUMMARY};
    background-color: {TRANSPARENT};
    font-size: {FONTS["size"][11]}px;
    font-weight: {FONTS["weight"]["regular"]};
}}

QTableWidget#pageTable {{
    background-color: {TRANSPARENT};
    color: {TEXT_COLOR};
    border: {BORDER_WIDTH}px solid {TABLE_BORDER};
    border-radius: {RADIUS["icon"]}px;
    outline: none;
}}
"""
