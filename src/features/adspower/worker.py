from PySide6.QtCore import QThread, Signal

from src.features.adspower.client import AdsPowerClient, AdsPowerError


class AdsPowerCheckWorker(QThread):

    result = Signal(bool, str)

    def __init__(
        self,
        local_api: str,
        api_key: str,
    ):
        super().__init__()

        self.local_api = local_api
        self.api_key = api_key

    def run(self):
        try:
            client = AdsPowerClient(
                self.local_api,
                self.api_key,
            )

            client.check_connection()

            self.result.emit(True, "")

        except AdsPowerError as error:
            self.result.emit(False, str(error))

        except Exception as error:
            self.result.emit(False, str(error))
