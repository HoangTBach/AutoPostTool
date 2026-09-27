from src.themes.color import (
    BG_COLOR,
    TEXT_COLOR,
)

APP_STYLE = f"""
QMainWindow {{
    background-color: {BG_COLOR};
}}

QWidget {{
    color: {TEXT_COLOR};
}}
"""
