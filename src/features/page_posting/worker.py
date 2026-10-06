from PySide6.QtCore import QThread, Signal

from src.features.page_posting.excel import get_data_file_stamp, load_page_rows
from src.features.page_posting.service import build_page_jobs, flatten_page_jobs

_SIGNATURE_FIELDS = (
    "task_id",
    "post_id",
    "post_order",
    "profile_id",
    "profile_uid",
    "profile_name",
    "profile_status",
    "via_id",
    "via_name",
    "page_id",
    "page",
    "page_link",
    "page_status",
    "caption",
    "image",
    "comment",
)


class PageImportWorker(QThread):

    result = Signal(object)
    error = Signal(str)

    def __init__(self, previous_stamp=None, previous_signature=None):
        super().__init__()

        self.previous_stamp = previous_stamp
        self.previous_signature = previous_signature

    def run(self):
        try:
            file_stamp = get_data_file_stamp()

            if file_stamp == self.previous_stamp:
                self.result.emit(
                    {
                        "changed": False,
                        "file_stamp": file_stamp,
                        "signature": self.previous_signature,
                    }
                )
                return

            rows = load_page_rows()
            jobs = build_page_jobs(rows)
            ordered_rows = flatten_page_jobs(jobs)

            signature = _build_signature(ordered_rows)

            if signature == self.previous_signature:
                self.result.emit(
                    {
                        "changed": False,
                        "file_stamp": file_stamp,
                        "signature": signature,
                    }
                )
                return

            self.result.emit(
                {
                    "changed": True,
                    "file_stamp": file_stamp,
                    "signature": signature,
                    "jobs": jobs,
                    "rows": ordered_rows,
                }
            )

        except Exception as error:
            self.error.emit(str(error))


class PageAutoWorker(QThread):

    error = Signal(str)

    def __init__(self, jobs: list[dict]):
        super().__init__()

        self.jobs = jobs
        self.stop_requested = False

    # ----- Stop -----
    def request_stop(self):
        self.stop_requested = True

    # ----- Run -----
    def run(self):
        try:
            for job in self.jobs:
                if self.stop_requested:
                    return

                for row in job["rows"]:
                    if self.stop_requested:
                        return

                    # AdsPower + Facebook Page
                    pass

        except Exception as error:
            self.error.emit(str(error))


# ----- Signature -----
def _build_signature(rows: list[dict]) -> tuple:
    return tuple(tuple(row.get(field) for field in _SIGNATURE_FIELDS) for row in rows)
