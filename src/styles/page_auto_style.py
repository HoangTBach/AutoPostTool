from src.themes.color import (
    BG_COLOR,
    TEXT_COLOR,
)

PAGE_AUTO_STYLE = f"""
QWidget#pageAutoContent {{
    background-color: {BG_COLOR};
}}

QTableWidget#pageTable {{
    background-color: {BG_COLOR};
    color: {TEXT_COLOR};

    border: 1px solid #E2E8F0;
    border-radius: 10px;

    outline: none;
}}
"""
