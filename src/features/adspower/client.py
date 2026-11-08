import json
from json import JSONDecodeError
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from src.configs.adspower import ADSPOWER_TIMEOUT


class AdsPowerError(Exception):
    pass


class AdsPowerClient:

    def __init__(
        self,
        local_api: str,
        api_key: str = "",
    ):
        self.base_url = self.normalize_url(local_api)
        self.api_key = api_key.strip()

    # ----- URL -----
    def normalize_url(self, local_api: str) -> str:
        local_api = local_api.strip()

        if not local_api:
            raise AdsPowerError("Local API is required.")

        if not local_api.startswith(("http://", "https://")):
            local_api = f"http://{local_api}"

        local_api = local_api.rstrip("/")
        try:
            parts = urlsplit(local_api)
            port = parts.port  # Validate malformed ports before making a request.
        except ValueError as error:
            raise AdsPowerError("Invalid AdsPower Local API URL.") from error

        if (
            parts.scheme not in {"http", "https"}
            or not parts.hostname
            or parts.username is not None
            or parts.password is not None
            or parts.path not in {"", "/"}
            or parts.query
            or parts.fragment
        ):
            raise AdsPowerError("Invalid AdsPower Local API URL.")

        return local_api

    # ----- Connection -----
    def check_connection(self) -> bool:
        self.request(
            "POST",
            "/api/v2/browser-profile/list",
            {
                "page": 1,
                "limit": 1,
            },
        )

        return True

    # ----- Profiles -----
    def get_profiles(
        self,
        page: int = 1,
        limit: int = 100,
    ) -> list[dict]:
        result = self.request(
            "POST",
            "/api/v2/browser-profile/list",
            {
                "page": page,
                "limit": limit,
            },
        )

        data = result.get("data")
        if not isinstance(data, dict) or not isinstance(data.get("list"), list):
            raise AdsPowerError("AdsPower returned an invalid profile list.")
        return data["list"]

    # ----- Request -----
    def request(
        self,
        method: str,
        path: str,
        payload: dict | None = None,
    ) -> dict:
        url = f"{self.base_url}{path}"
        body = None

        if payload is not None:
            body = json.dumps(payload).encode("utf-8")

        request = Request(
            url,
            data=body,
            method=method,
        )

        request.add_header("Accept", "application/json")

        if payload is not None:
            request.add_header(
                "Content-Type",
                "application/json",
            )

        if self.api_key:
            request.add_header(
                "Authorization",
                f"Bearer {self.api_key}",
            )

        try:
            with urlopen(
                request,
                timeout=ADSPOWER_TIMEOUT,
            ) as response:
                content = response.read().decode("utf-8")

        except HTTPError as error:
            message = self._get_http_error(error)

            raise AdsPowerError(message) from error

        except URLError as error:
            reason = getattr(error, "reason", error)

            raise AdsPowerError(f"Cannot connect to AdsPower: {reason}") from error

        except TimeoutError as error:
            raise AdsPowerError("AdsPower connection timed out.") from error

        except OSError as error:
            raise AdsPowerError(f"Cannot connect to AdsPower: {error}") from error

        try:
            result = json.loads(content)

        except JSONDecodeError as error:
            raise AdsPowerError("AdsPower returned invalid response.") from error

        if not isinstance(result, dict):
            raise AdsPowerError("AdsPower returned an unexpected response format.")

        if result.get("code") not in (0, "0"):
            raise AdsPowerError(
                str(result.get("msg") or result.get("message") or "AdsPower request failed.")
            )

        return result

    # ----- Error -----
    def _get_http_error(self, error: HTTPError) -> str:
        try:
            content = error.read().decode("utf-8")
            result = json.loads(content)

            if not isinstance(result, dict):
                return f"AdsPower HTTP {error.code}"

            return (
                result.get("msg")
                or result.get("message")
                or f"AdsPower HTTP {error.code}"
            )

        except (JSONDecodeError, UnicodeDecodeError, TypeError, ValueError):
            return f"AdsPower HTTP {error.code}"
