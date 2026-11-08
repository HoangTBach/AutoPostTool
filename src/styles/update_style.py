"""Update screen styling, matched to Figma node 128:299 (AutoPostTool VKU).

Uses the application's existing theme tokens. Only UpdatePage uses these rules.
"""

from src.themes.color import COLORS
from src.themes.font import FONTS
from src.themes.radius import RADIUS
from src.themes.spacing import SPACING as SPACE

UPDATE_MARGIN = (SPACE[32], SPACE[32], SPACE[32], SPACE[32])
UPDATE_LAYOUT_SPACING = SPACE[24]
UPDATE_CONTENT_GAP = SPACE[16]
UPDATE_COLUMN_GAP = SPACE[16]
UPDATE_CARD_RADIUS = RADIUS["card"]

WHITE = COLORS["neutral"]["white"]
DARK = COLORS["slate"][900]
TEXT = COLORS["slate"][900]
MUTED = COLORS["slate"][500]
FAINT = COLORS["slate"][400]
BORDER = COLORS["slate"][200]
PALE = COLORS["slate"][50]
BLUE = COLORS["blue"][600]
BLUE_PALE = COLORS["blue"][50]
GREEN = COLORS["emerald"][500]
GREEN_PALE = COLORS["emerald"][50]
RED = COLORS["red"][500]
RED_PALE = COLORS["red"][50]

UPDATE_STYLE = f"""
QWidget#updatePage {{
    background: transparent;
}}
QLabel#updateHeaderTitle {{
    color: {TEXT};
    font-size: {FONTS['size'][28]}px;
    font-weight: {FONTS['weight']['bold']};
}}
QWidget#updateHero {{
    background: {WHITE};
    border: 1px solid {BORDER};
    border-radius: {UPDATE_CARD_RADIUS}px;
}}
QFrame#updateHeroFeature {{
    background-color: {DARK};
    border: none;
    border-top-left-radius: {UPDATE_CARD_RADIUS}px;
    border-bottom-left-radius: {UPDATE_CARD_RADIUS}px;
}}
QFrame#updateHeroVersion {{
    background-color: {WHITE};
    border: none;
    border-top-right-radius: {UPDATE_CARD_RADIUS}px;
    border-bottom-right-radius: {UPDATE_CARD_RADIUS}px;
}}
QLabel#updateHeroTitle {{
    color: {WHITE};
    font-size: {FONTS['size'][30]}px;
    font-weight: {FONTS['weight']['regular']};
}}
QLabel#updateHeroDescription {{
    color: {COLORS['slate'][300]};
    font-size: {FONTS['size'][13]}px;
}}
QLabel#updateChannel {{
    color: {FAINT};
    font-size: {FONTS['size'][10]}px;
}}
QLabel#updateAvailable {{
    color: #00A66B;
    background-color: #E8FFF3;
    border: none;
    border-radius: 11px;
    padding: 4px 9px;
    font-size: {FONTS['size'][10]}px;
    font-weight: {FONTS['weight']['medium']};
}}
QLabel#updateCurrentLabel {{
    color: {MUTED};
    font-size: {FONTS['size'][11]}px;
    font-weight: {FONTS['weight']['semibold']};
}}
QLabel#updateCurrentValue {{
    color: {TEXT};
    font-size: {FONTS['size'][24]}px;
    font-weight: {FONTS['weight']['bold']};
}}
QLabel#updateInstalledDate {{
    color: {FAINT};
    font-size: {FONTS['size'][10]}px;
}}
QLabel#updateCurrentIcon {{
    background-color: {BLUE_PALE};
    border: none;
    border-radius: {RADIUS['icon']}px;
}}
QLabel#updateSectionTitle {{
    color: {TEXT};
    background: transparent;
    border: none;
    font-size: {FONTS['size'][18]}px;
    font-weight: {FONTS['weight']['bold']};
}}
QLabel#updateSectionDescription {{
    color: {MUTED};
    background: transparent;
    border: none;
    font-size: {FONTS['size'][13]}px;
    font-weight: {FONTS['weight']['regular']};
}}
QLabel#updateChangeDescription {{
    color: {MUTED};
    background: transparent;
    border: none;
    font-size: {FONTS['size'][13]}px;
}}
QFrame#updateChangeRow {{
    background: transparent;
    border: none;
    border-bottom: 1px solid {BORDER};
}}
QFrame#updateChangeRowLast {{
    background: transparent;
    border: none;
}}
QLabel#updateChangeIconGreen {{
    background-color: {GREEN_PALE};
    border-radius: {RADIUS['icon']}px;
}}
QLabel#updateChangeIconRed {{
    background-color: {RED_PALE};
    border-radius: {RADIUS['icon']}px;
}}
QLabel#updateChangeIconBlue {{
    background-color: {BLUE_PALE};
    border-radius: {RADIUS['icon']}px;
}}
QLabel#updateTagGreen {{
    color: #00A66B;
    background: {GREEN_PALE};
    border-radius: 8px;
    font-size: {FONTS['size'][10]}px;
    font-weight: {FONTS['weight']['bold']};
    padding: 2px 8px;
}}
QLabel#updateTagRed {{
    color: {RED};
    background: {RED_PALE};
    border-radius: 8px;
    font-size: {FONTS['size'][10]}px;
    font-weight: {FONTS['weight']['bold']};
    padding: 2px 8px;
}}
QLabel#updateTagBlue {{
    color: {BLUE};
    background: {BLUE_PALE};
    border-radius: 8px;
    font-size: {FONTS['size'][10]}px;
    font-weight: {FONTS['weight']['bold']};
    padding: 2px 8px;
}}
QLabel#updateHistoryCount {{
    background-color: {PALE};
    border-radius: 11px;
    color: {MUTED};
    font-size: {FONTS['size'][10]}px;
    padding: 5px 9px;
}}
QFrame#updateHistoryItem {{
    background-color: {PALE};
    border: 1px solid {BORDER};
    border-radius: {RADIUS['card']}px;
}}
QLabel#updateHistoryAvatarBlue {{
    color: {BLUE};
    background-color: {BLUE_PALE};
    border-radius: {RADIUS['icon']}px;
    font-size: {FONTS['size'][11]}px;
    font-weight: {FONTS['weight']['bold']};
}}
QLabel#updateHistoryAvatarGreen {{
    color: {GREEN};
    background-color: {GREEN_PALE};
    border-radius: {RADIUS['icon']}px;
    font-size: {FONTS['size'][11]}px;
    font-weight: {FONTS['weight']['bold']};
}}
QLabel#updateHistoryVersion {{
    color: {TEXT};
    background: transparent;
    font-size: {FONTS['size'][14]}px;
    font-weight: {FONTS['weight']['bold']};
}}
QLabel#updateHistoryDate,
QLabel#updateHistoryBullet {{
    color: {MUTED};
    background: transparent;
    font-size: {FONTS['size'][11]}px;
}}
QLabel#updateHistoryBulletDot {{
    color: {FAINT};
    background: transparent;
    font-size: {FONTS['size'][12]}px;
}}
QLabel#updateHistoryBadgeFix {{
    color: #00A66B;
    background: {GREEN_PALE};
    border-radius: 11px;
    font-size: {FONTS['size'][10]}px;
    padding: 5px 9px;
}}
QLabel#updateHistoryBadgeStable {{
    color: {BLUE};
    background: {BLUE_PALE};
    border-radius: 11px;
    font-size: {FONTS['size'][10]}px;
    padding: 5px 9px;
}}
"""
