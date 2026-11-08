from src.themes.color import COLORS
from src.themes.radius import RADIUS
from src.themes.spacing import SPACING

# ----- Scrollbar -----
SCROLLBAR_COLOR = COLORS["slate"][300]
SCROLLBAR_TRANSPARENT = COLORS["transparent"]

SMOOTH_SCROLLBAR_STYLE = f"""
QScrollBar:vertical {{
    background: {SCROLLBAR_TRANSPARENT};
    width: {SPACING[4]}px;
    border: none;
    margin: 0px;
}}

QScrollBar::handle:vertical {{
    background: {SCROLLBAR_COLOR};
    border-radius: {RADIUS["small"]}px;
    min-height: {SPACING[32]}px;
}}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    width: 0px;
    height: 0px;
    border: none;
}}

QScrollBar::up-arrow:vertical,
QScrollBar::down-arrow:vertical {{
    width: 0px;
    height: 0px;
    border: none;
}}

QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {{
    background: {SCROLLBAR_TRANSPARENT};
}}

QScrollBar:horizontal {{
    background: {SCROLLBAR_TRANSPARENT};
    height: {SPACING[4]}px;
    border: none;
    margin: 0px;
}}

QScrollBar::handle:horizontal {{
    background: {SCROLLBAR_COLOR};
    border-radius: {RADIUS["small"]}px;
    min-width: {SPACING[32]}px;
}}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {{
    width: 0px;
    height: 0px;
    border: none;
}}

QScrollBar::left-arrow:horizontal,
QScrollBar::right-arrow:horizontal {{
    width: 0px;
    height: 0px;
    border: none;
}}

QScrollBar::add-page:horizontal,
QScrollBar::sub-page:horizontal {{
    background: {SCROLLBAR_TRANSPARENT};
}}
"""
