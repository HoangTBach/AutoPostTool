import requests  # type: ignore

from src.configs.adspower import ADSPOWER_TIMEOUT


class AdsPowerError(Exception):
    pass


class AdsPowerClient:

    def __init__(self, local_api: str):
        self.base_url = self.normalize_url(local_api)
        self.session = requests.Session()

    # ----- URL -----
    def normalize_url(self, local_api: str):
        local_api = local_api.strip()

        if not local_api:
            raise AdsPowerError("Local API is required.")

        if not local_api.startswith(("http://", "https://")):
            local_api = f"http://{local_api}"

        return local_api.rstrip("/")

    # ----- Request -----
    def request(self, method: str, path: str, **kwargs):
        try:
            response = self.session.request(
                method,
                f"{self.base_url}{path}",
                timeout=ADSPOWER_TIMEOUT,
                **kwargs,
            )

            response.raise_for_status()
            data = response.json()

        except requests.Timeout as error:
            raise AdsPowerError("AdsPower connection timed out.") from error

        except requests.ConnectionError as error:
            raise AdsPowerError("Cannot connect to AdsPower.") from error

        except requests.RequestException as error:
            raise AdsPowerError(str(error)) from error

        except ValueError as error:
            raise AdsPowerError("Invalid response from AdsPower.") from error

        if data.get("code") != 0:
            raise AdsPowerError(data.get("msg") or "AdsPower request failed.")

        return data

    # ----- Connection -----
    def check_connection(self):
        self.request("GET", "/status")
        return True

    # ----- Close -----
    def close(self):
        self.session.close()
