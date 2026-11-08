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


# ----- Settings Page -----
SETTING_PAGE_STYLE = """
QWidget#settingsPage {
    background-color: transparent;
    border: none;
}

QWidget#settingsPathField {
    background-color: transparent;
    border: none;
}

QToolButton#settingsPathBrowseButton {
    background-color: transparent;
    border: none;
    padding: 0;
}

QLabel#settingFooterTitle {
    color: #0F172A;
    background-color: transparent;
    border: none;
    font-size: 12px;
    font-weight: 600;
}

QLabel#settingFooterSubtitle {
    color: #94A3B8;
    background-color: transparent;
    border: none;
    font-size: 10px;
    font-weight: 400;
}
"""

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
QWidget#settingsPathField {{
    background-color: transparent;
    border: none;
    font-size: {FONTS["size"][13]}px;
    font-weight: {FONTS["weight"]["semibold"]};
}}

QToolButton#settingsPathBrowseButton {{
    background-color: transparent;
    border: none;
    padding: 0;
    font-size: {FONTS["size"][12]}px;
    font-weight: {FONTS["weight"]["regular"]};
}}

QWidget#unsavedStatus {{
    background-color: {TRANSPARENT};
    border: none;
}}

QLabel#unsavedStatusTitle {{
    background-color: {TRANSPARENT};
    color: {COLORS["slate"][900]};
    border: none;
    font-size: {FONTS["size"][13]}px;
    font-weight: {FONTS["weight"]["semibold"]};
}}

QLabel#unsavedStatusDescription {{
    background-color: {TRANSPARENT};
    color: {COLORS["slate"][400]};
    border: none;
    font-size: {FONTS["size"][12]}px;
    font-weight: {FONTS["weight"]["regular"]};
}}
"""




# ----- AdsPower Connection Status Badge -----
# Local widget styles ensure a colored pill remains visible inside SectionCard.
CONNECTION_STATUS_STYLES = {
    "connected": f"""
        QLabel#connectionStatus {{
            background-color: {CONNECTION_CONNECTED_BG};
            color: {CONNECTION_CONNECTED};
            border: none;
            border-radius: 11px;
            padding: 4px 10px;
            font-size: {FONTS['size'][10]}px;
            font-weight: {FONTS['weight']['semibold']};
        }}
    """,
    "disconnected": f"""
        QLabel#connectionStatus {{
            background-color: {CONNECTION_DISCONNECTED_BG};
            color: {CONNECTION_DISCONNECTED};
            border: none;
            border-radius: 11px;
            padding: 4px 10px;
            font-size: {FONTS['size'][10]}px;
            font-weight: {FONTS['weight']['semibold']};
        }}
    """,
    "testing": f"""
        QLabel#connectionStatus {{
            background-color: {CONNECTION_TESTING_BG};
            color: {CONNECTION_TESTING};
            border: none;
            border-radius: 11px;
            padding: 4px 10px;
            font-size: {FONTS['size'][10]}px;
            font-weight: {FONTS['weight']['semibold']};
        }}
    """,
}

# ----- Settings Screen: Theme and Below -----
SETTING_SECTIONS_STYLE = f"""
QWidget#settingsScrollableContent,
QWidget#settingsMainContent,
QWidget#settingsSectionBody,
QWidget#settingsSectionHeader,
QWidget#settingsThemeColumn,
QWidget#settingsLanguageColumn,
QWidget#settingsSidebarColumn,
QWidget#settingsSplitColumn {{
    background: transparent;
    border: none;
}}
QScrollArea#settingsSmoothScroll {{
    background: transparent;
    border: none;
}}
QLabel#settingsFieldTitle {{
    color: #17243C;
    background: transparent;
    border: none;
    font-size: {FONTS['size'][12]}px;
    font-weight: {FONTS['weight']['semibold']};
}}
QFrame#settingsVerticalDivider {{
    background: #DCE6F2;
    border: none;
    max-width: 1px;
    min-width: 1px;
}}
QLabel#settingsRowTitle,
QLabel#settingsRowSubtitle {{
    background: transparent;
    border: none;
}}
QLabel#settingsRowTitle {{
    color: #17243C;
    font-size: 11px;
    font-weight: 600;
}}
QLabel#settingsRowSubtitle {{
    color: #7E90A9;
    font-size: 9px;
    font-weight: 400;
}}
QLabel#settingsPreferenceSubtitle {{
    color: #7E90A9;
    background: transparent;
    border: none;
    font-size: 9px;
    font-weight: 400;
}}

/* Card shells and section separators used on Settings. */
QWidget#card[settingSection="true"],
QWidget#card[settingFooter="true"] {{
    background-color: {COLORS["neutral"]["white"]};
    border: {BORDER_WIDTH}px solid {CARD_BORDER};
    border-radius: {RADIUS["card"]}px;
}}
QFrame#sectionCardHeaderDivider {{
    background-color: {CARD_BORDER};
    border: none;
    min-height: {BORDER_WIDTH}px;
    max-height: {BORDER_WIDTH}px;
}}
"""


# ----- Notification Tile Border -----
SETTING_NOTIFICATION_ITEM_STYLE = """
QFrame#settingsNotificationItem {
    background-color: white;
    border: 1px solid #DCE6F2;
    border-radius: 6px;
}
"""


# ----- Setting Choice: Selectable Tile -----
SETTING_CHOICE_TILE_STYLE = f"""
QPushButton#settingChoiceTile {{
    background-color: {COLORS["neutral"]["white"]};
    border: 1px solid #DCE6F2;
    border-radius: 9px;
    padding: 0px;
}}
QPushButton#settingChoiceTile:hover {{
    background-color: {COLORS["blue"]["surface"]};
    border: 1px solid {COLORS["blue"][300]};
}}
QPushButton#settingChoiceTile:checked {{
    background-color: {COLORS["blue"]["surface"]};
    border: 1px solid {COLORS["blue"][600]};
}}
QPushButton#settingChoiceTile:checked:hover {{
    background-color: {COLORS["blue"][50]};
    border: 1px solid {COLORS["blue"][600]};
}}
QPushButton#settingChoiceTile:pressed {{
    background-color: #DBEAFE;
    border: 1px solid {COLORS["blue"][600]};
}}
QLabel#settingChoicePreview,
QLabel#settingChoiceTitle,
QLabel#settingChoiceSubtitle {{
    background: transparent;
    border: none;
}}
QLabel#settingChoiceTitle {{
    color: #17243C;
    font-size: 11px;
    font-weight: 500;
}}
QLabel#settingChoiceSubtitle {{
    color: #7E90A9;
    font-size: 10px;
    font-weight: 400;
}}
"""


# ----- Setting Choice: Language and Split Radios -----
SETTING_RADIO_CHOICE_STYLE = f"""
QPushButton#settingRadioChoice {{
    background: transparent;
    border: none;
    border-radius: 5px;
    padding: 0px;
    text-align: left;
}}
QPushButton#settingRadioChoice[boxed="true"] {{
    background-color: {COLORS["neutral"]["white"]};
    border: 1px solid #DCE6F2;
    border-radius: 6px;
}}
QPushButton#settingRadioChoice[boxed="true"]:hover {{
    background-color: {COLORS["blue"]["surface"]};
    border: 1px solid {COLORS["blue"][300]};
}}
QPushButton#settingRadioChoice[boxed="true"]:checked {{
    background-color: {COLORS["blue"]["surface"]};
    border: 1px solid {COLORS["blue"][600]};
}}
QPushButton#settingRadioChoice[boxed="true"]:checked:hover {{
    background-color: {COLORS["blue"][50]};
    border: 1px solid {COLORS["blue"][600]};
}}
QPushButton#settingRadioChoice[boxed="true"]:pressed {{
    background-color: #DBEAFE;
    border: 1px solid {COLORS["blue"][600]};
}}
QPushButton#settingRadioChoice[boxed="false"]:hover {{
    background-color: {COLORS["blue"]["surface"]};
}}
QLabel#settingRadioText {{
    background: transparent;
    border: none;
    color: #17243C;
    font-size: 11px;
    font-weight: 400;
}}
QLabel#settingRadioText[selected="true"] {{
    color: {COLORS["blue"][600]};
    font-weight: 600;
}}
"""
