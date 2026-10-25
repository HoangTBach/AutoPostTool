from src.themes.color import COLORS
from src.themes.spacing import SPACING as SPACE

# ----- Colors -----
TOGGLE_COLORS = {
    "off": COLORS["slate"][300],
    "on": COLORS["blue"][600],
    "knob": COLORS["neutral"]["white"],
    "disabled": "#989B9F",
    "disabled_knob": "#A7A9AC",
}

# ----- Size -----
TOGGLE_WIDTH = 32
TOGGLE_HEIGHT = 18
TOGGLE_MARGIN = SPACE[2]

# ----- Animation -----
TOGGLE_DURATION = 160
