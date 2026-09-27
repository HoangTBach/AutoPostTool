from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ICON_DIR = BASE_DIR / "assets" / "icons"


MENU_ITEMS = {
    "top": [
        # {"icon": ICON_DIR / "dashboard.png", "name": "Dashboard", "page": "dashboard"},
        {"icon": ICON_DIR / "page-auto.png", "name": "Page Auto", "page": "page_auto"},
        # {"icon": ICON_DIR / "group-auto.png", "name": "Group Auto", "page": "group_auto"},
        # {"icon": ICON_DIR / "news-auto.png", "name": "News Auto", "page": "news_auto"},
    ],
    "bottom": [
        # {"icon": ICON_DIR / "update.png", "name": "Update", "page": "update"},
        # {"icon": ICON_DIR / "setting.png", "name": "Setting", "page": "setting"},
    ],
}
