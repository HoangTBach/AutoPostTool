from src.themes.color import (
    TABLE_INPUT_BG,
    TABLE_INPUT_BORDER,
    TEXT_COLOR,
)
from src.themes.font import (
    FONT_SIZE_13,
    FONT_WEIGHT_REGULAR,
)

INPUT_STYLE = f"""
QLineEdit#input {{
    background-color: {TABLE_INPUT_BG};
    color: {TEXT_COLOR};

    border: 1px solid {TABLE_INPUT_BORDER};
    border-radius: 6px;

    padding: 0px 10px;

    min-height: 30px;
    max-height: 30px;

    font-size: {FONT_SIZE_13}px;
    font-weight: {FONT_WEIGHT_REGULAR};
}}

QLineEdit#input[editable="true"] {{
    background-color: #FFFFFF;
}}

QLineEdit#input:focus {{
    border-color: #2563EB;
}}
"""
