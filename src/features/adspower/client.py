import requests

from src.configs.adspower import (
    ADSPOWER_API_KEY,
    ADSPOWER_TIMEOUT,
)


class AdsPowerError(Exception):
    pass


class AdsPowerClient:

    def __init__(
        self,
        local_api: str,
    ):
        self.local_api = self.normalize_url(local_api)

    # ----- Normalize URL -----
    @staticmethod
    def normalize_url(
        local_api: str,
    ):
        local_api = local_api.strip()

        if not local_api:
            raise AdsPowerError("Local API is required.")

        if not local_api.startswith(("http://", "https://")):
            local_api = f"http://{local_api}"

        return local_api.rstrip("/")

    # ----- Headers -----
    def get_headers(self):
        if not ADSPOWER_API_KEY:
            return {}

        return {"Authorization": (f"Bearer {ADSPOWER_API_KEY}")}

    # ----- Check Connection -----
    def check_connection(self):
        try:
            response = requests.get(
                f"{self.local_api}/status",
                headers=self.get_headers(),
                timeout=ADSPOWER_TIMEOUT,
            )

            response.raise_for_status()

        except requests.RequestException as error:
            raise AdsPowerError("Cannot connect to AdsPower.") from error

        try:
            data = response.json()

        except ValueError as error:
            raise AdsPowerError("Invalid response from AdsPower.") from error

        if data.get("code") != 0:
            raise AdsPowerError(
                data.get(
                    "msg",
                    "AdsPower connection failed.",
                )
            )

        return True
