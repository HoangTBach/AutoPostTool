from src.themes.color import COLORS

# ----- Colors -----
SIDEBAR_BG = COLORS["slate"][900]


SIDEBAR_STYLE = f"""
QWidget#sidebar {{
    background-color: {SIDEBAR_BG};
}}
"""
