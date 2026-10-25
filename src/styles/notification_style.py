from src.themes.border import BORDERS
from src.themes.color import COLORS
from src.themes.font import FONTS
from src.themes.radius import RADIUS
from src.themes.spacing import SPACING

# ----- Colors -----
NOTIFICATION_BG = COLORS["neutral"]["white"]
NOTIFICATION_TEXT = COLORS["slate"][900]
NOTIFICATION_MESSAGE = COLORS["slate"][500]

NOTIFICATION_STYLES = {
    "info": {
        "accent": COLORS["blue"][600],
        "border": COLORS["blue"][300],
        "surface": COLORS["blue"][50],
    },
    "success": {
        "accent": COLORS["green"][600],
        "border": COLORS["green"][300],
        "surface": COLORS["emerald"][50],
    },
    "error": {
        "accent": COLORS["red"][600],
        "border": COLORS["red"][200],
        "surface": COLORS["red"][50],
    },
    "warning": {
        "accent": COLORS["amber"][600],
        "border": COLORS["amber"][300],
        "surface": COLORS["amber"][50],
    },
}


# ----- Border -----
BORDER_WIDTH = BORDERS["width"]["default"]


# ----- Radius -----
NOTIFICATION_RADIUS = RADIUS.get(
    "notification",
    RADIUS.get("card", 12),
)


# ----- Spacing -----
LEGACY_SPACING = SPACING["legacy"]

NOTIFICATION_PADDING_X = LEGACY_SPACING.get(14, 14)
NOTIFICATION_PADDING_Y = LEGACY_SPACING.get(12, 12)
NOTIFICATION_GAP = LEGACY_SPACING.get(12, 12)


# ----- Font -----
NOTIFICATION_TITLE_SIZE = FONTS["size"][14]
NOTIFICATION_MESSAGE_SIZE = FONTS["size"][12]

NOTIFICATION_TITLE_WEIGHT = FONTS["weight"]["semibold"]
NOTIFICATION_MESSAGE_WEIGHT = FONTS["weight"]["regular"]


# ----- Style -----
def get_notification_card_style(kind: str) -> str:
    style = NOTIFICATION_STYLES.get(
        kind,
        NOTIFICATION_STYLES["info"],
    )

    return f"""
        QFrame#notificationCard {{
            background-color: {NOTIFICATION_BG};
            border: {BORDER_WIDTH}px solid {style["border"]};
            border-radius: {NOTIFICATION_RADIUS}px;
        }}

        QFrame#notificationCard QLabel {{
            background-color: transparent;
            border: none;
        }}

        QLabel#notificationTitle {{
            color: {style["accent"]};
            font-size: {NOTIFICATION_TITLE_SIZE}px;
            font-weight: {NOTIFICATION_TITLE_WEIGHT};
        }}

        QLabel#notificationMessage {{
            color: {NOTIFICATION_MESSAGE};
            font-size: {NOTIFICATION_MESSAGE_SIZE}px;
            font-weight: {NOTIFICATION_MESSAGE_WEIGHT};
        }}
    """
