"""Group Auto-specific layout tokens and Qt styles."""

from src.themes.border import BORDERS
from src.themes.color import COLORS
from src.themes.font import FONTS
from src.themes.spacing import SPACING as SPACE

GROUP_AUTO_MARGIN = (SPACE[32], SPACE[32], SPACE[32], SPACE[32])
GROUP_AUTO_LAYOUT_SPACING = SPACE[24]
GROUP_AUTO_ACTION_SPACING = SPACE[8]
GROUP_AUTO_STAT_SPACING = SPACE[12]
GROUP_AUTO_CONTENT_SPACING = SPACE["legacy"][20]
GROUP_AUTO_CONFIG_MARGIN = (SPACE[16], SPACE[16], SPACE[16], SPACE[16])
GROUP_AUTO_CONFIG_CARD_SPACING = SPACE[8]
GROUP_AUTO_CONFIG_BODY_SPACING = SPACE[32]
GROUP_AUTO_CONFIG_CONTROL_SPACING = SPACE[16]

TRANSPARENT = COLORS["transparent"]
TEXT_MUTED = COLORS["slate"][500]
TEXT_STRONG = COLORS["slate"][900]
GROUP_AUTO_DIVIDER_COLOR = COLORS["slate"][200]
GROUP_AUTO_DIVIDER_WIDTH = BORDERS["width"]["default"]

GROUP_AUTO_STYLE = f"""
QWidget#groupAutoContent {{
    background-color: {TRANSPARENT};
}}
QLabel#groupSummaryLabel {{
    color: {TEXT_MUTED};
    background-color: {TRANSPARENT};
    font-size: {FONTS["size"][11]}px;
}}
QLabel#groupConfigLabel {{
    color: {TEXT_MUTED};
    background-color: {TRANSPARENT};
    font-size: {FONTS["size"][12]}px;
    font-weight: {FONTS["weight"]["semibold"]};
}}
QLabel#groupConfigUnit {{
    color: {TEXT_MUTED};
    background-color: {TRANSPARENT};
    font-size: {FONTS["size"][12]}px;
}}
QWidget#groupConfigDivider {{
    background-color: {GROUP_AUTO_DIVIDER_COLOR};
    border: none;
}}
QWidget#groupEmptyState {{
    background-color: {TRANSPARENT};
}}
QLabel#groupEmptyTitle {{
    color: {TEXT_STRONG};
    background-color: {TRANSPARENT};
    font-size: {FONTS["size"][14]}px;
    font-weight: {FONTS["weight"]["semibold"]};
}}
QLabel#groupEmptySubtitle {{
    color: {TEXT_MUTED};
    background-color: {TRANSPARENT};
    font-size: {FONTS["size"][12]}px;
}}
"""
