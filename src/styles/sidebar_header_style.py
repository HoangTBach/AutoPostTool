from src.themes.color import (
    SIDEBAR_LOGO_TEXT,
    SIDEBAR_LOGO_TEXT_MUTED,
)

from src.themes.font import (
    FONT_SIZE_11,
    FONT_SIZE_16,
    FONT_WEIGHT_REGULAR,
    FONT_WEIGHT_BOLD,
)

SIDEBAR_HEADER_STYLE = f"""
QLabel#sidebarAppName {{
    color: {SIDEBAR_LOGO_TEXT};
    font-size: {FONT_SIZE_16}px;
    font-weight: {FONT_WEIGHT_BOLD};
}}

QLabel#sidebarAppMeta {{
    color: {SIDEBAR_LOGO_TEXT_MUTED};
    font-size: {FONT_SIZE_11}px;
    font-weight: {FONT_WEIGHT_REGULAR};
}}
"""
