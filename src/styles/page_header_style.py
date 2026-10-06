from src.themes.border import BORDERS
from src.themes.color import COLORS
from src.themes.font import FONTS

# ----- Colors -----
PAGE_HEADER_TITLE = COLORS["slate"][900]
PAGE_HEADER_SUBTITLE = COLORS["slate"][500]
PAGE_HEADER_DIVIDER = COLORS["slate"][200]

# ----- Border -----
BORDER_WIDTH = BORDERS["width"]["default"]


PAGE_HEADER_STYLE = f"""
QLabel#pageHeaderTitle {{
    color: {PAGE_HEADER_TITLE};
    font-size: {FONTS["size"][24]}px;
    font-weight: {FONTS["weight"]["bold"]};
}}

QLabel#pageHeaderSubtitle {{
    color: {PAGE_HEADER_SUBTITLE};
    font-size: {FONTS["size"][14]}px;
    font-weight: {FONTS["weight"]["regular"]};
}}

QFrame#pageHeaderDivider {{
    border: none;
    border-top: {BORDER_WIDTH}px solid {PAGE_HEADER_DIVIDER};
}}
"""
