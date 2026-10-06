from src.themes.color import COLORS
from src.themes.font import FONTS
from src.themes.radius import RADIUS
from src.themes.spacing import SPACING

# ----- Colors -----
CARD_BORDER = COLORS["slate"][200]
CARD_TITLE = COLORS["slate"][500]

TABLE_HEADER_BG = COLORS["slate"]["input_surface"]
TABLE_HEADER_TEXT = COLORS["slate"][900]

INPUT_BG = COLORS["slate"]["input_surface"]
INPUT_BORDER = COLORS["slate"]["input_border"]

TEXT_COLOR = COLORS["slate"][900]

STATUS_DONE = COLORS["emerald"][500]
STATUS_ERROR = COLORS["red"][500]
STATUS_RUNNING = COLORS["blue"][600]
STATUS_QUEUED = COLORS["slate"][400]

SCROLLBAR_COLOR = COLORS["slate"][300]


TABLE_STYLE = f"""
/* ----- Table ----- */

QWidget#table {{
    background-color: transparent;
    border: none;
}}


/* ----- Header ----- */

QWidget#tableHeader {{
    background-color: {TABLE_HEADER_BG};

    border: 1px solid {CARD_BORDER};
    border-bottom: none;
}}

QLabel#tableHeaderCell {{
    background-color: transparent;
    color: {TABLE_HEADER_TEXT};

    border: none;

    font-size: {FONTS["size"][10]}px;
    font-weight: {FONTS["weight"]["semibold"]};
}}


/* ----- Scroll Area ----- */

QScrollArea#tableScrollArea {{
    background-color: transparent;
    border: none;
}}

QScrollArea#tableScrollArea > QWidget {{
    background-color: transparent;
}}

QScrollArea#tableScrollArea > QWidget > QWidget {{
    background-color: transparent;
}}


/* ----- Body ----- */

QWidget#tableBody {{
    background-color: transparent;
    border: none;
}}


/* ----- Row ----- */

QWidget#tableRow {{
    background-color: transparent;

    border: none;
    border-top: 1px solid {CARD_BORDER};
}}


/* ----- Text ----- */

QLabel#tableText {{
    background-color: transparent;

    border: none;

    font-size: {FONTS["size"][13]}px;
}}

QLabel#tableText[column="no"] {{
    color: {CARD_TITLE};

    font-weight: {FONTS["weight"]["medium"]};
}}

QLabel#tableText[column="page"] {{
    color: {TEXT_COLOR};

    font-weight: {FONTS["weight"]["medium"]};
}}


/* ----- Box ----- */

QLabel#tableBox {{
    background-color: {INPUT_BG};
    color: {TEXT_COLOR};

    border: 1px solid {INPUT_BORDER};
    border-radius: {RADIUS["input"]}px;

    min-height: 30px;
    max-height: 30px;

    padding: 0px {SPACING["legacy"][10]}px;

    font-size: {FONTS["size"][13]}px;
    font-weight: {FONTS["weight"]["regular"]};
}}


/* ----- List ----- */

QWidget#tableList {{
    background-color: transparent;
    border: none;
}}

QLabel#tableListItem {{
    background-color: transparent;
    color: {TEXT_COLOR};

    border: none;

    font-size: {FONTS["size"][12]}px;
    font-weight: {FONTS["weight"]["medium"]};
}}


/* ----- Status ----- */

QLabel#tableStatus {{
    background-color: transparent;

    border: none;

    font-size: {FONTS["size"][12]}px;
    font-weight: {FONTS["weight"]["medium"]};
}}

QLabel#tableStatus[status="done"] {{
    color: {STATUS_DONE};
}}

QLabel#tableStatus[status="error"] {{
    color: {STATUS_ERROR};
}}

QLabel#tableStatus[status="running"] {{
    color: {STATUS_RUNNING};
}}

QLabel#tableStatus[status="queued"] {{
    color: {STATUS_QUEUED};
}}


/* ----- ScrollBar ----- */

QScrollBar:vertical {{
    background-color: transparent;

    width: {SPACING[4]}px;
    margin: 0px;
}}

QScrollBar::handle:vertical {{
    background-color: {SCROLLBAR_COLOR};

    border-radius: {RADIUS["small"]}px;

    min-height: {SPACING[32]}px;
}}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    width: 0px;
    height: 0px;
}}

QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {{
    background-color: transparent;
}}
"""
