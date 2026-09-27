from src.themes.color import (
    PAGE_HEADER_TITLE,
    PAGE_HEADER_SUBTITLE,
    PAGE_HEADER_DIVIDER,
)

from src.themes.font import (
    FONT_SIZE_14,
    FONT_SIZE_24,
    FONT_WEIGHT_REGULAR,
    FONT_WEIGHT_BOLD,
)

PAGE_HEADER_STYLE = f"""
QLabel#pageHeaderTitle {{
    color: {PAGE_HEADER_TITLE};
    font-size: {FONT_SIZE_24}px;
    font-weight: {FONT_WEIGHT_BOLD};
}}

QLabel#pageHeaderSubtitle {{
    color: {PAGE_HEADER_SUBTITLE};
    font-size: {FONT_SIZE_14}px;
    font-weight: {FONT_WEIGHT_REGULAR};
}}

QFrame#pageHeaderDivider {{
    border: none;
    border-top: 1px solid {PAGE_HEADER_DIVIDER};
}}
"""
