import json


from src.configs.adspower import (
    ADSPOWER_DEFAULT_URL,
    ADSPOWER_SETTINGS_FILE,
)

DEFAULT_SETTINGS = {
    "local_api": ADSPOWER_DEFAULT_URL,
    "auto_reconnect": True,
}


# ----- Load Settings -----
def load_adspower_settings():
    if not ADSPOWER_SETTINGS_FILE.exists():
        return DEFAULT_SETTINGS.copy()

    try:
        with ADSPOWER_SETTINGS_FILE.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

    except (
        OSError,
        json.JSONDecodeError,
    ):
        return DEFAULT_SETTINGS.copy()

    return {
        **DEFAULT_SETTINGS,
        **data,
    }


# ----- Save Settings -----
def save_adspower_settings(
    local_api: str,
    auto_reconnect: bool,
):
    ADSPOWER_SETTINGS_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    data = {
        "local_api": local_api.strip(),
        "auto_reconnect": auto_reconnect,
    }

    with ADSPOWER_SETTINGS_FILE.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            data,
            file,
            indent=4,
        )
