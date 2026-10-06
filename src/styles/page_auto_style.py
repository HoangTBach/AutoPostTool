from src.themes.color import COLORS
from src.themes.font import FONTS
from src.themes.radius import RADIUS

# ----- Colors -----
TEXT_COLOR = COLORS["slate"][900]
TEXT_SUMMARY = COLORS["slate"][500]
TABLE_BORDER = COLORS["slate"][200]


PAGE_AUTO_STYLE = f"""
QWidget#pageAutoContent {{
    background-color: transparent;
}}

QLabel#summary_label {{
    color: {TEXT_SUMMARY};

    font-size: {FONTS["size"][11]}px;
    font-weight: {FONTS["weight"]["regular"]};
}}

QTableWidget#pageTable {{
    background-color: transparent;
    color: {TEXT_COLOR};

    border: 1px solid {TABLE_BORDER};
    border-radius: {RADIUS["icon"]}px;

    outline: none;
}}
"""
