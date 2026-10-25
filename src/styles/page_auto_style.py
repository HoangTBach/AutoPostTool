from src.themes.border import BORDERS
from src.themes.color import COLORS
from src.themes.font import FONTS
from src.themes.radius import RADIUS
from src.themes.spacing import SPACING as SPACE

# ----- Page Auto layout tokens -----
# Keep page_auto.py independent from direct theme imports.
PAGE_AUTO_MARGIN = (SPACE[32], SPACE[32], SPACE[32], SPACE[32])
PAGE_AUTO_LAYOUT_SPACING = SPACE[24]
PAGE_AUTO_ACTION_SPACING = SPACE[8]
PAGE_AUTO_STAT_SPACING = SPACE[12]
PAGE_AUTO_CONTENT_SPACING = SPACE["legacy"][20]
PAGE_AUTO_CONFIG_CARD_MARGINS = (SPACE[16], SPACE[16], SPACE[16], SPACE[16])
PAGE_AUTO_CONFIG_CARD_SPACING = SPACE[8]
PAGE_AUTO_CONFIG_BODY_SPACING = SPACE[32]
PAGE_AUTO_CONFIG_CONTROL_SPACING = SPACE[16]

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

QLabel#configLabel {{
    color: {TEXT_SUMMARY};
    background-color: {TRANSPARENT};
    font-size: {FONTS["size"][12]}px;
    font-weight: {FONTS["weight"]["semibold"]};
}}

QLabel#configUnitLabel {{
    color: {TEXT_SUMMARY};
    background-color: {TRANSPARENT};
    font-size: {FONTS["size"][12]}px;
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
