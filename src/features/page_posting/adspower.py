import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from src.configs.adspower import ADSPOWER_DEFAULT_URL, ADSPOWER_TIMEOUT

DEFAULT_API_URL = ADSPOWER_DEFAULT_URL
_api_url = DEFAULT_API_URL
_api_key = ""
_last_request_at = 0.0


def set_credentials(local_api: str, api_key: str) -> None:
    global _api_url, _api_key
    _api_url = (local_api or DEFAULT_API_URL).strip().rstrip("/")
    _api_key = (api_key or "").strip()


def clear_credentials() -> None:
    global _api_url, _api_key
    _api_url = DEFAULT_API_URL
    _api_key = ""


def _request(endpoint: str, params: dict | None = None) -> dict:
    global _last_request_at

    if not _api_key:
        raise RuntimeError("AdsPower is not connected. Connect it in Settings first.")

    wait = 1.0 - (time.monotonic() - _last_request_at)
    if wait > 0:
        time.sleep(wait)

    url = f"{_api_url}{endpoint}"
    if params:
        url = f"{url}?{urlencode(params)}"

    request = Request(
        url,
        headers={
            "Authorization": f"Bearer {_api_key}",
            "Accept": "application/json",
        },
    )

    try:
        with urlopen(request, timeout=ADSPOWER_TIMEOUT) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"AdsPower API HTTP {error.code}: {detail}") from error
    except (URLError, TimeoutError, OSError) as error:
        raise RuntimeError(f"Cannot reach AdsPower Local API: {error}") from error
    finally:
        _last_request_at = time.monotonic()

    if str(payload.get("code", "0")) != "0":
        raise RuntimeError(f"AdsPower API error: {payload.get('msg') or payload}")

    return payload.get("data") or {}


def start_profile(profile_uid: str) -> dict:
    if not profile_uid:
        raise ValueError("AdsPower profile UID is missing.")

    data = _request("/api/v1/browser/start", {"user_id": profile_uid})

    if not data.get("ws", {}).get("selenium") or not data.get("webdriver"):
        raise RuntimeError(f"AdsPower returned incomplete browser data: {data}")

    return data


def stop_profile(profile_uid: str) -> None:
    if profile_uid:
        _request("/api/v1/browser/stop", {"user_id": profile_uid})


def connect_driver(profile_data: dict):
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
    except ImportError as error:
        raise RuntimeError(
            "Selenium is missing. Run: python -m pip install selenium"
        ) from error

    selenium_address = profile_data["ws"]["selenium"].strip()

    if "://" in selenium_address:
        debugger_address = urlsplit(selenium_address).netloc
    else:
        debugger_address = selenium_address.split("/", 1)[0]

    options = Options()
    options.add_experimental_option("debuggerAddress", debugger_address)

    return webdriver.Chrome(
        service=Service(executable_path=profile_data["webdriver"]),
        options=options,
    )
