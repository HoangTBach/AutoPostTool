from src.themes.color import COLORS
from src.themes.font import FONTS

# ----- Colors -----
SIDEBAR_LOGO_TEXT = COLORS["neutral"]["white"]
SIDEBAR_LOGO_TEXT_MUTED = COLORS["slate"][400]


SIDEBAR_HEADER_STYLE = f"""
QLabel#sidebarAppName {{
    color: {SIDEBAR_LOGO_TEXT};
    font-size: {FONTS["size"][16]}px;
    font-weight: {FONTS["weight"]["bold"]};
}}

QLabel#sidebarAppMeta {{
    color: {SIDEBAR_LOGO_TEXT_MUTED};
    font-size: {FONTS["size"][11]}px;
    font-weight: {FONTS["weight"]["regular"]};
}}
"""
