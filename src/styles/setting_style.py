from src.themes.color import (
    CARD_BORDER,
    CARD_DESCRIPTION,
    CARD_TITLE,
    CONNECTION_CONNECTED,
    CONNECTION_CONNECTED_BG,
    CONNECTION_DEFAULT,
    CONNECTION_DEFAULT_BG,
    CONNECTION_DISCONNECTED,
    CONNECTION_DISCONNECTED_BG,
    CONNECTION_TESTING,
    CONNECTION_TESTING_BG,
    TEXT_COLOR,
)

from src.themes.font import (
    FONT_SIZE_10,
    FONT_SIZE_11,
    FONT_SIZE_12,
    FONT_SIZE_13,
    FONT_SIZE_14,
    FONT_WEIGHT_REGULAR,
    FONT_WEIGHT_BOLD,
    FONT_WEIGHT_SEMIBOLD,
)

SETTING_STYLE = f"""
/* ----- Header ----- */

QLabel#settingCardTitle {{
    background-color: transparent;
    color: {TEXT_COLOR};
    border: none;

    font-size: {FONT_SIZE_14}px;
    font-weight: {FONT_WEIGHT_BOLD};
}}

QLabel#settingCardSubtitle {{
    background-color: transparent;
    color: {CARD_DESCRIPTION};
    border: none;

    font-size: {FONT_SIZE_12}px;
    font-weight: {FONT_WEIGHT_REGULAR};
}}


/* ----- Connection Status ----- */

QLabel#connectionStatus {{
    background-color: {CONNECTION_DEFAULT_BG};
    color: {CONNECTION_DEFAULT};

    border: none;
    border-radius: 10px;

    padding: 4px 8px;

    font-size: {FONT_SIZE_10}px;
    font-weight: {FONT_WEIGHT_SEMIBOLD};
}}

QLabel#connectionStatus[state="connected"] {{
    background-color: {CONNECTION_CONNECTED_BG};
    color: {CONNECTION_CONNECTED};
}}

QLabel#connectionStatus[state="disconnected"] {{
    background-color: {CONNECTION_DISCONNECTED_BG};
    color: {CONNECTION_DISCONNECTED};
}}

QLabel#connectionStatus[state="testing"] {{
    background-color: {CONNECTION_TESTING_BG};
    color: {CONNECTION_TESTING};
}}


/* ----- Divider ----- */

QWidget#settingDivider {{
    background-color: {CARD_BORDER};
    border: none;

    min-height: 1px;
    max-height: 1px;
}}


/* ----- Label ----- */

QLabel#settingLabel {{
    background-color: transparent;
    color: {CARD_TITLE};
    border: none;

    font-size: {FONT_SIZE_11}px;
    font-weight: {FONT_WEIGHT_SEMIBOLD};
}}

QLabel#apiKeyLabel {{
    background-color: transparent;
    color: {CARD_TITLE};
    border: none;

    font-size: {FONT_SIZE_13}px;
    font-weight: {FONT_WEIGHT_REGULAR};
}}


/* ----- Reconnect ----- */

QLabel#reconnectLabel {{
    background-color: transparent;
    color: {CARD_DESCRIPTION};
    border: none;

    font-size: {FONT_SIZE_11}px;
    font-weight: {FONT_WEIGHT_SEMIBOLD};
}}
"""
