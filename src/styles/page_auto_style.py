from src.themes.color import TEXT_COLOR, TEXT_SUMMARY
from src.themes.font import FONT_SIZE_11, FONT_WEIGHT_REGULAR

PAGE_AUTO_STYLE = f"""
QWidget#pageAutoContent {{
    background-color: transparent;
}}

QLabel#summary_label {{
    color: {TEXT_SUMMARY};
    font-size: {FONT_SIZE_11};
    font-weight: {FONT_WEIGHT_REGULAR};
}}

QTableWidget#pageTable {{
    background-color: transparent;
    color: {TEXT_COLOR};

    border: 1px solid #E2E8F0;
    border-radius: 10px;

    outline: none;
}}
"""
