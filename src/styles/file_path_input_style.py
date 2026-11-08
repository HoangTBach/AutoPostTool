from src.themes.color import COLORS

FILE_PATH_INPUT_ICON_SIZE = 14
FILE_PATH_INPUT_ICON_COLOR = COLORS["slate"][400]


FILE_PATH_INPUT_STYLE = f"""
QToolButton#filePathInputBrowseButton {{
    background-color: transparent;
    border: none;
    border-left: 1px solid #E2E8F0;
    padding: 0;
}}

QToolButton#filePathInputBrowseButton:hover {{
    background-color: transparent;
    border: none;
    border-left: 1px solid #E2E8F0;
}}

QToolButton#filePathInputBrowseButton:pressed {{
    background-color: transparent;
    border: none;
    border-left: 1px solid #E2E8F0;
}}
"""
