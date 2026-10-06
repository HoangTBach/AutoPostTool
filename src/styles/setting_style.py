from src.themes.border import BORDERS
from src.themes.color import COLORS
from src.themes.font import FONTS
from src.themes.radius import RADIUS
from src.themes.spacing import SPACING

# ----- Colors -----
TRANSPARENT = COLORS["transparent"]
TEXT_COLOR = COLORS["slate"][900]
CARD_BORDER = COLORS["slate"][200]
CARD_TITLE = COLORS["slate"][500]
CARD_DESCRIPTION = COLORS["slate"][400]

CONNECTION_DEFAULT = COLORS["slate"][500]
CONNECTION_DEFAULT_BG = COLORS["slate"][50]
CONNECTION_CONNECTED = COLORS["emerald"][500]
CONNECTION_CONNECTED_BG = COLORS["emerald"][50]
CONNECTION_DISCONNECTED = COLORS["red"][500]
CONNECTION_DISCONNECTED_BG = COLORS["red"][50]
CONNECTION_TESTING = COLORS["blue"][600]
CONNECTION_TESTING_BG = COLORS["blue"][50]

# ----- Border -----
BORDER_WIDTH = BORDERS["width"]["default"]


SETTING_STYLE = f"""
QLabel#settingCardTitle {{
    background-color: {TRANSPARENT};
    color: {TEXT_COLOR};
    border: none;
    font-size: {FONTS["size"][14]}px;
    font-weight: {FONTS["weight"]["bold"]};
}}

QLabel#settingCardSubtitle {{
    background-color: {TRANSPARENT};
    color: {CARD_DESCRIPTION};
    border: none;
    font-size: {FONTS["size"][12]}px;
    font-weight: {FONTS["weight"]["regular"]};
}}

QLabel#connectionStatus {{
    background-color: {CONNECTION_DEFAULT_BG};
    color: {CONNECTION_DEFAULT};
    border: none;
    border-radius: {RADIUS["icon"]}px;
    padding: {SPACING[4]}px {SPACING[8]}px;
    font-size: {FONTS["size"][10]}px;
    font-weight: {FONTS["weight"]["semibold"]};
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

QWidget#settingDivider {{
    background-color: {CARD_BORDER};
    border: none;
    min-height: {BORDER_WIDTH}px;
    max-height: {BORDER_WIDTH}px;
}}

QLabel#settingLabel {{
    background-color: {TRANSPARENT};
    color: {CARD_TITLE};
    border: none;
    font-size: {FONTS["size"][11]}px;
    font-weight: {FONTS["weight"]["semibold"]};
}}

QLabel#apiKeyLabel {{
    background-color: {TRANSPARENT};
    color: {CARD_TITLE};
    border: none;
    font-size: {FONTS["size"][13]}px;
    font-weight: {FONTS["weight"]["regular"]};
}}

QLabel#reconnectLabel {{
    background-color: {TRANSPARENT};
    color: {CARD_DESCRIPTION};
    border: none;
    font-size: {FONTS["size"][11]}px;
    font-weight: {FONTS["weight"]["semibold"]};
}}
"""
