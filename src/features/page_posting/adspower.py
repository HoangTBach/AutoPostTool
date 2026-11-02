import json
import time
from pathlib import Path
from threading import Lock
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from src.configs.adspower import (
    ADSPOWER_DEFAULT_URL,
    ADSPOWER_TIMEOUT,
    ADSPOWER_REQUEST_INTERVAL_SECONDS,
    ADSPOWER_PROFILE_START_ATTEMPTS,
    ADSPOWER_PROFILE_START_RETRY_DELAY_SECONDS,
)

# ----- Settings -----
REQUEST_INTERVAL_SECONDS = ADSPOWER_REQUEST_INTERVAL_SECONDS
PROFILE_START_ATTEMPTS = ADSPOWER_PROFILE_START_ATTEMPTS
PROFILE_START_RETRY_DELAY = ADSPOWER_PROFILE_START_RETRY_DELAY_SECONDS

_TRANSIENT_ERRORS = (
    "updating",
    "waiting for download",
    "browser is starting",
    "please wait",
    "temporarily unavailable",
    "timed out",
    "timeout",
    "try again",
    "connection refused",
    "not ready",
    "missing ws.selenium",
    "missing webdriver",
    "no selenium address",
    "no webdriver path",
    "already open",
    "already running",
    "already started",
)

_api_key = ""
_api_url = ADSPOWER_DEFAULT_URL.rstrip("/")
_last_request_at = 0.0
_request_lock = Lock()


# ----- Exceptions -----
class AdsPowerError(Exception):
    pass


class AdsPowerConnectionError(AdsPowerError):
    pass


# ----- Credentials -----
def set_credentials(api_key: str, api_url: str = ADSPOWER_DEFAULT_URL) -> None:
    global _api_key, _api_url

    api_key = str(api_key or "").strip()
    api_url = str(api_url or ADSPOWER_DEFAULT_URL).strip().rstrip("/")

    if not api_key:
        raise AdsPowerConnectionError("AdsPower API key is empty.")

    if not api_url:
        raise AdsPowerConnectionError("AdsPower API URL is empty.")

    if "://" not in api_url:
        api_url = f"http://{api_url}"

    parsed_url = urlparse(api_url)

    if parsed_url.scheme not in ("http", "https") or not parsed_url.netloc:
        raise AdsPowerConnectionError(f"Invalid AdsPower API URL: {api_url}")

    _api_key = api_key
    _api_url = api_url


def clear_credentials() -> None:
    global _api_key, _api_url

    _api_key = None
    _api_url = ADSPOWER_DEFAULT_URL.rstrip("/")


# ----- Request -----
def _wait_for_request_interval() -> None:
    global _last_request_at

    with _request_lock:
        elapsed = time.monotonic() - _last_request_at
        remaining = REQUEST_INTERVAL_SECONDS - elapsed

        if remaining > 0:
            time.sleep(remaining)

        _last_request_at = time.monotonic()


def _request(
    method: str,
    endpoint: str,
    params: dict | None = None,
) -> dict:
    if not _api_key:
        raise AdsPowerConnectionError("AdsPower API key has not been configured.")

    url = f"{_api_url}/{endpoint.lstrip('/')}"

    if params:
        query = urlencode(
            {key: value for key, value in params.items() if value is not None}
        )
        if query:
            url = f"{url}?{query}"

    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {_api_key}",
        },
        method=method.upper(),
    )

    _wait_for_request_interval()

    try:
        with urlopen(request, timeout=ADSPOWER_TIMEOUT) as response:
            raw_response = response.read()

    except HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", errors="replace")
        except Exception:
            detail = str(exc.reason)

        raise AdsPowerError(
            f"AdsPower HTTP error {exc.code}: {detail or exc.reason}"
        ) from exc

    except (URLError, TimeoutError, OSError) as exc:
        raise AdsPowerConnectionError(f"Cannot connect to AdsPower API: {exc}") from exc

    try:
        payload = json.loads(raw_response.decode("utf-8"))

    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AdsPowerError("AdsPower returned an invalid JSON response.") from exc

    if not isinstance(payload, dict):
        raise AdsPowerError("AdsPower returned an unexpected response format.")

    code = payload.get("code")

    if code not in (0, "0"):
        message = (
            payload.get("msg") or payload.get("message") or "Unknown AdsPower API error"
        )
        raise AdsPowerError(str(message))

    data = payload.get("data", {})

    if not isinstance(data, dict):
        raise AdsPowerError("AdsPower response data has an invalid format.")

    return data


# ----- Connection Check -----
def check_connection(
    api_key: str,
    api_url: str = ADSPOWER_DEFAULT_URL,
) -> bool:
    set_credentials(api_key, api_url=api_url)

    data = _request(
        "GET",
        "/api/v1/user/list",
        {
            "page": 1,
            "page_size": 1,
        },
    )

    profiles = data.get("list")

    if not isinstance(profiles, list):
        raise AdsPowerError("AdsPower returned an invalid profile list.")

    return True


# ----- Profile Validation -----
def check_profiles(profile_uids: list[str]) -> list[str]:
    requested = sorted(
        {
            str(profile_uid or "").strip()
            for profile_uid in profile_uids
            if str(profile_uid or "").strip()
        }
    )

    if not requested:
        raise AdsPowerError("No AdsPower profile UIDs were provided for preflight.")

    page = 1
    page_size = 100
    available_uids = set()

    while True:
        data = _request(
            "GET",
            "/api/v1/user/list",
            {
                "page": page,
                "page_size": page_size,
            },
        )

        profiles = data.get("list")

        if not isinstance(profiles, list):
            raise AdsPowerError("AdsPower returned an invalid profile list.")

        for profile in profiles:
            if not isinstance(profile, dict):
                continue

            profile_uid = str(profile.get("user_id") or "").strip()

            if profile_uid:
                available_uids.add(profile_uid)

        page_count = data.get("page_count")
        total = data.get("total")

        try:
            if page_count is not None and page >= int(page_count):
                break
        except (TypeError, ValueError):
            pass

        try:
            if total is not None and len(available_uids) >= int(total):
                break
        except (TypeError, ValueError):
            pass

        if len(profiles) < page_size:
            break

        page += 1

        if page > 1000:
            raise AdsPowerError("AdsPower profile listing exceeded 1000 pages.")

    missing_uids = [
        profile_uid for profile_uid in requested if profile_uid not in available_uids
    ]

    if missing_uids:
        raise AdsPowerError(
            "AdsPower profile UID(s) not found: " + ", ".join(missing_uids)
        )

    return requested


# ----- Active Profile -----
def get_active_profile(profile_uid: str) -> dict | None:
    """Return connection data for an already-open local AdsPower profile.

    If AdsPower reports the profile as active before its Selenium endpoint is
    ready, poll briefly rather than failing immediately. This helps on slower
    machines and after the profile has just been opened.
    """
    profile_uid = str(profile_uid or "").strip()
    if not profile_uid:
        raise AdsPowerError("AdsPower profile UID is empty.")

    attempts = 8
    delay_seconds = 0.75
    missing_fields: list[str] = []

    for attempt in range(1, attempts + 1):
        data = _request("GET", "/api/v1/browser/local-active")
        profiles = data.get("list")
        if not isinstance(profiles, list):
            raise AdsPowerError(
                "AdsPower returned an invalid active-browser list from "
                "/api/v1/browser/local-active."
            )

        active_profile = next(
            (
                profile
                for profile in profiles
                if isinstance(profile, dict)
                and str(profile.get("user_id") or "").strip() == profile_uid
            ),
            None,
        )
        if active_profile is None:
            return None

        ws = active_profile.get("ws")
        missing_fields = []
        if not isinstance(ws, dict) or not str(ws.get("selenium") or "").strip():
            missing_fields.append("ws.selenium")
        if not str(active_profile.get("webdriver") or "").strip():
            missing_fields.append("webdriver")

        if not missing_fields:
            return active_profile

        if attempt < attempts:
            time.sleep(delay_seconds)

    raise AdsPowerConnectionError(
        f"AdsPower profile {profile_uid} is active but its Selenium connection "
        f"is not ready after {attempts} checks; missing: {', '.join(missing_fields)}. "
        "Wait for the profile browser to finish starting, then retry."
    )


# ----- Profile -----
def start_profile(profile_uid: str) -> dict:
    profile_uid = str(profile_uid or "").strip()

    if not profile_uid:
        raise AdsPowerError("AdsPower profile UID is empty.")

    for attempt in range(1, PROFILE_START_ATTEMPTS + 1):
        try:
            profile_data = _request(
                "GET",
                "/api/v1/browser/start",
                {"user_id": profile_uid},
            )

            ws = profile_data.get("ws")
            has_selenium = isinstance(ws, dict) and bool(
                str(ws.get("selenium") or "").strip()
            )
            has_webdriver = bool(str(profile_data.get("webdriver") or "").strip())

            if has_selenium and has_webdriver:
                return profile_data

            active_profile = get_active_profile(profile_uid)
            if active_profile:
                return active_profile

            missing = []
            if not has_selenium:
                missing.append("ws.selenium")
            if not has_webdriver:
                missing.append("webdriver")
            raise AdsPowerConnectionError(
                f"AdsPower profile {profile_uid} is not ready; missing "
                f"{', '.join(missing)}."
            )

        except AdsPowerError as exc:
            message = str(exc).lower()
            is_transient = any(keyword in message for keyword in _TRANSIENT_ERRORS)

            if any(
                keyword in message
                for keyword in ("already open", "already running", "already started")
            ):
                try:
                    active_profile = get_active_profile(profile_uid)
                except AdsPowerError:
                    active_profile = None
                if active_profile:
                    return active_profile
                is_transient = True

            if not is_transient or attempt >= PROFILE_START_ATTEMPTS:
                raise

            time.sleep(PROFILE_START_RETRY_DELAY)

    raise AdsPowerError(f"Could not start AdsPower profile: {profile_uid}")


def stop_profile(profile_uid: str) -> dict:
    profile_uid = str(profile_uid or "").strip()

    if not profile_uid:
        raise AdsPowerError("AdsPower profile UID is empty.")

    return _request(
        "GET",
        "/api/v1/browser/stop",
        {"user_id": profile_uid},
    )


# ----- Selenium -----
def _get_debugger_address(profile_data: dict) -> str:
    ws = profile_data.get("ws", {})

    if not isinstance(ws, dict):
        ws = {}

    selenium_address = str(ws.get("selenium") or "").strip()

    if selenium_address:
        parsed = urlparse(
            selenium_address if "://" in selenium_address else f"//{selenium_address}"
        )

        if parsed.hostname and parsed.port:
            return f"{parsed.hostname}:{parsed.port}"

        address = selenium_address.split("/", 1)[0]
        if ":" in address:
            host, port = address.rsplit(":", 1)

            if host and port.isdigit():
                return f"{host}:{port}"

    debug_port = profile_data.get("debug_port")

    if debug_port and str(debug_port).isdigit():
        return f"127.0.0.1:{debug_port}"

    raise AdsPowerConnectionError(
        "Cannot determine the AdsPower browser debugger address."
    )


def get_profile_debugger_address(profile_data: dict) -> str:
    """Return the debugger host:port for a profile returned by AdsPower."""
    return _get_debugger_address(profile_data)


def _normalize_debugger_address(address: str) -> tuple[str, int] | None:
    value = str(address or "").strip()
    if not value:
        return None

    parsed = urlparse(value if "://" in value else f"//{value}")
    host = str(parsed.hostname or "").strip().lower()
    port = parsed.port
    if not host or port is None:
        return None

    if host in {"localhost", "::1"}:
        host = "127.0.0.1"

    return host, port


def connect_driver(profile_data: dict):
    if not isinstance(profile_data, dict):
        raise AdsPowerConnectionError("Invalid AdsPower profile data.")

    webdriver_path = str(profile_data.get("webdriver") or "").strip()

    if not webdriver_path:
        raise AdsPowerConnectionError("AdsPower did not provide a WebDriver path.")

    driver_path = Path(webdriver_path)

    if not driver_path.is_file():
        raise AdsPowerConnectionError(f"WebDriver file does not exist: {driver_path}")

    debugger_address = _get_debugger_address(profile_data)

    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service

    except ImportError as exc:
        raise AdsPowerConnectionError(
            "Selenium is not installed in the current Python environment."
        ) from exc

    options = Options()
    options.debugger_address = debugger_address

    driver = None

    try:
        driver = webdriver.Chrome(
            service=Service(executable_path=str(driver_path)),
            options=options,
        )

        if not driver.window_handles:
            raise AdsPowerConnectionError("Connected browser has no available window.")

        driver.execute_script("return 1")
        capabilities = getattr(driver, "capabilities", {}) or {}
        chrome_options = capabilities.get("goog:chromeOptions") or {}
        attached_address = str(chrome_options.get("debuggerAddress") or "").strip()
        expected_address = _get_debugger_address(profile_data)

        if attached_address:
            expected = _normalize_debugger_address(expected_address)
            attached = _normalize_debugger_address(attached_address)
            if expected and attached and expected != attached:
                raise AdsPowerConnectionError(
                    "Selenium attached to a different browser debugger than the "
                    f"AdsPower profile requested. Expected {expected_address}; "
                    f"connected to {attached_address}."
                )

        return driver

    except Exception as exc:
        if driver is not None:
            try:
                # This function may be attaching to a browser opened manually.
                # Stop the ChromeDriver service without closing that browser.
                driver.service.stop()
            except Exception:
                pass

        if isinstance(exc, AdsPowerConnectionError):
            raise

        raise AdsPowerConnectionError(
            f"Could not connect Selenium to AdsPower: {exc}"
        ) from exc


def close_driver(driver) -> bool:
    if driver is None:
        return True

    try:
        driver.quit()
        return True

    except Exception:
        return False
