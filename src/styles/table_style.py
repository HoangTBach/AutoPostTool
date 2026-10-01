from src.themes.color import (
    CARD_BORDER,
    CARD_TITLE,
    STATUS_DONE,
    STATUS_ERROR,
    STATUS_QUEUED,
    STATUS_RUNNING,
    TABLE_HEADER_BG,
    TABLE_INPUT_BG,
    TABLE_INPUT_BORDER,
    TEXT_COLOR,
)

from src.themes.font import (
    FONT_SIZE_10,
    FONT_SIZE_12,
    FONT_SIZE_13,
    FONT_WEIGHT_MEDIUM,
    FONT_WEIGHT_REGULAR,
    FONT_WEIGHT_SEMIBOLD,
)

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
    color: {TEXT_COLOR};
    border: none;

    font-size: {FONT_SIZE_10}px;
    font-weight: {FONT_WEIGHT_SEMIBOLD};
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
    font-size: {FONT_SIZE_13}px;
}}

QLabel#tableText[column="no"] {{
    color: {CARD_TITLE};
    font-weight: {FONT_WEIGHT_MEDIUM};
}}

QLabel#tableText[column="page"] {{
    color: {TEXT_COLOR};
    font-weight: {FONT_WEIGHT_MEDIUM};
}}


/* ----- Box ----- */

QLabel#tableBox {{
    background-color: {TABLE_INPUT_BG};
    color: {TEXT_COLOR};

    border: 1px solid {TABLE_INPUT_BORDER};
    border-radius: 6px;

    min-height: 30px;
    max-height: 30px;

    padding: 0px 10px;

    font-size: {FONT_SIZE_13}px;
    font-weight: {FONT_WEIGHT_REGULAR};
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

    font-size: {FONT_SIZE_12}px;
    font-weight: {FONT_WEIGHT_MEDIUM};
}}


/* ----- Status ----- */

QLabel#tableStatus {{
    background-color: transparent;
    border: none;

    font-size: {FONT_SIZE_12}px;
    font-weight: {FONT_WEIGHT_MEDIUM};
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
    width: 4px;
    margin: 0px;
}}

QScrollBar::handle:vertical {{
    background-color: #CBD5E1;
    border-radius: 4px;
    min-height: 32px;
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
