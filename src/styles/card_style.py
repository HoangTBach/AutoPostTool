from src.themes.color import (
    CARD_BG,
    CARD_BORDER,
    CARD_DESCRIPTION,
    CARD_TITLE,
    TEXT_COLOR,
)
from src.themes.font import (
    FONT_SIZE_10,
    FONT_SIZE_11,
    FONT_SIZE_20,
    FONT_WEIGHT_BOLD,
    FONT_WEIGHT_REGULAR,
    FONT_WEIGHT_SEMIBOLD,
)

CARD_STYLE = f"""
/* ----- Card ----- */

QWidget#card {{
    background-color: {CARD_BG};
    border: 1px solid {CARD_BORDER};
    border-radius: 12px;
}}


/* ----- Stat Card ----- */

QLabel#statTitle {{
    color: {CARD_TITLE};
    font-size: {FONT_SIZE_11}px;
    font-weight: {FONT_WEIGHT_SEMIBOLD};
    background-color: transparent;
    border: none;
}}

QLabel#statValue {{
    color: {TEXT_COLOR};
    font-size: {FONT_SIZE_20}px;
    font-weight: {FONT_WEIGHT_BOLD};
    background-color: transparent;
    border: none;
}}

QLabel#statDescription {{
    color: {CARD_DESCRIPTION};
    font-size: {FONT_SIZE_10}px;
    font-weight: {FONT_WEIGHT_REGULAR};
    background-color: transparent;
    border: none;
}}


/* ----- Table Card ----- */

QWidget#tableCardHeader {{
    background-color: transparent;
    border: none;
}}

QLabel#tableCardTitle {{
    color: {CARD_TITLE};
    font-weight: {FONT_WEIGHT_SEMIBOLD};
    background-color: transparent;
    border: none;
}}

QWidget#tableCardBody {{
    background-color: transparent;
    border: none;
}}
"""
