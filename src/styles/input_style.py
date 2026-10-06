from src.themes.color import COLORS
from src.themes.font import FONTS
from src.themes.radius import RADIUS
from src.themes.spacing import SPACING

# ----- Colors -----
INPUT_BG = COLORS["slate"]["input_surface"]
INPUT_BG_EDITABLE = COLORS["neutral"]["white"]

INPUT_BORDER = COLORS["slate"]["input_border"]
INPUT_BORDER_FOCUS = COLORS["blue"][600]

INPUT_TEXT = COLORS["slate"][900]


INPUT_STYLE = f"""
QLineEdit#input {{
    background-color: {INPUT_BG};
    color: {INPUT_TEXT};

    border: 1px solid {INPUT_BORDER};
    border-radius: {RADIUS["input"]}px;

    padding: 0px {SPACING["legacy"][10]}px;

    min-height: 30px;
    max-height: 30px;

    font-size: {FONTS["size"][13]}px;
    font-weight: {FONTS["weight"]["regular"]};
}}

QLineEdit#input[editable="true"] {{
    background-color: {INPUT_BG_EDITABLE};
}}

QLineEdit#input:focus {{
    border-color: {INPUT_BORDER_FOCUS};
}}
"""
