from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ICON_DIR = BASE_DIR / "assets" / "icons"


MENU_ITEMS = {
    "top": [
        # {"icon": ICON_DIR / "dashboard.svg", "name": "Dashboard", "page": "dashboard"},
        {"icon": ICON_DIR / "file-text.svg", "name": "Page Auto", "page": "page_auto"},
        # {
        #     "icon": ICON_DIR / "users-2.svg",
        #     "name": "Group Auto",
        #     "page": "group_auto",
        # },
        # {"icon": ICON_DIR / "newspaper.svg", "name": "News Auto", "page": "news_auto"},
    ],
    "bottom": [
        # {"icon": ICON_DIR / "refresh-cw.svg", "name": "Update", "page": "update"},
        {"icon": ICON_DIR / "settings.svg", "name": "Setting", "page": "setting"},
    ],
}
