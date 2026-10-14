from datetime import datetime, timedelta
import time
import uuid

from PySide6.QtCore import QThread, Signal

from src.configs.automation import (
    PAGE_AUTO_POST_DELAY,
    PAGE_AUTO_ORDER_DELAY,
)
from src.features.page_posting.adspower import (
    connect_driver,
    start_profile,
    stop_profile,
)
from src.features.page_posting.excel import (
    get_data_file_stamp,
    load_page_rows,
)
from src.features.page_posting.facebook import (
    PublishUnknownError,
    get_published_post_url,
    post_comment,
    publish_photo,
)
from src.features.page_posting.report import PageAutoReport
from src.features.page_posting.service import (
    build_page_jobs,
    flatten_page_jobs,
)
from src.features.page_posting.validation import validate_row

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

_TERMINAL_STATUSES = {"Published", "Failed", "Unknown"}


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


class _FatalAutomationError(RuntimeError):
    def __init__(self, message: str, user_message: str):
        super().__init__(message)
        self.user_message = user_message


class PageAutoWorker(QThread):
    error = Signal(str)
    progress = Signal(object)

    def __init__(self, jobs: list[dict]):
        super().__init__()
        self.jobs = jobs
        self._last_post_finished_at = None
        self.stop_requested = False
        self.run_id = str(uuid.uuid4())

    def request_stop(self):
        self.stop_requested = True

    def run(self):
        try:
            report = PageAutoReport()
            self._recover_interrupted_rows(report)

            state = report.get_state()
            last_completed_order = self._parse_order(state.get("last_completed_order"))
            next_order_at = self._parse_datetime(state.get("next_order_at"))

            grouped_jobs = {}
            for job in self.jobs:
                grouped_jobs.setdefault(job["post_order"], []).append(job)

            for order in sorted(grouped_jobs):
                if self.stop_requested:
                    return

                if last_completed_order is not None and order > last_completed_order:
                    if not self._wait_until(next_order_at):
                        return

                if self.stop_requested:
                    return

                for job in grouped_jobs[order]:
                    if self.stop_requested:
                        return

                    self._run_job(job, report)

                if self.stop_requested or not self._order_is_complete(
                    grouped_jobs[order], report
                ):
                    return

                if last_completed_order is None or order > last_completed_order:
                    order_delay = max(0.0, float(PAGE_AUTO_ORDER_DELAY))
                    next_order_at = datetime.now().astimezone() + timedelta(
                        minutes=order_delay
                    )

                    report.set_state(
                        {
                            "last_completed_order": str(order),
                            "next_order_at": next_order_at.isoformat(
                                timespec="seconds"
                            ),
                        }
                    )

                    last_completed_order = order

        except _FatalAutomationError as error:
            self.error.emit(error.user_message)
        except Exception:
            self.error.emit(
                "Page Auto stopped unexpectedly. Check report file access "
                "and PageAuto_DevLog.xlsx."
            )

    def _recover_interrupted_rows(self, report: PageAutoReport) -> None:
        for job in self.jobs:
            for row in job["rows"]:
                current = report.get_result(row.get("task_id", ""))

                if current.get("post_status") != "Running":
                    continue

                message = (
                    "Previous run ended before the publish result could be "
                    "confirmed. Check the Page before retrying."
                )
                report.upsert_result(row, "Unknown", error=message)

                attempt = max(1, report.next_attempt(row) - 1)
                report.log_event(
                    row,
                    self.run_id,
                    f"publish:{row.get('post_id', '')}",
                    "Unknown",
                    attempt,
                    RuntimeError(message),
                )
                self._emit(row, "Unknown", message)

    def _run_job(self, job: dict, report: PageAutoReport) -> None:
        pending_rows = []

        for row in job["rows"]:
            result = report.get_result(row.get("task_id", ""))
            status = result.get("post_status")

            if status == "Published":
                self._emit(row, "Done", result.get("error", ""))
                continue

            if status == "Unknown":
                self._emit(row, "Unknown", result.get("error", ""))
                continue

            pending_rows.append(row)

        if not pending_rows:
            return

        valid_rows = []

        for row in pending_rows:
            try:
                row["_validated_image"] = validate_row(row)
                valid_rows.append(row)
            except Exception as error:
                message = str(error)
                report.upsert_result(row, "Failed", error=message)
                report.log_event(
                    row,
                    self.run_id,
                    f"validate:{row.get('post_id', '')}",
                    "Failed",
                    error=error,
                )
                self._emit(row, "Error", message)

        if not valid_rows:
            return

        profile_uid = str(valid_rows[0].get("profile_uid") or "").strip()

        if not profile_uid:
            error = ValueError(
                "AdsPower profile UID is missing from the ADSPOWER sheet."
            )

            for row in valid_rows:
                message = "AdsPower profile UID is missing."
                report.upsert_result(row, "Failed", error=message)
                report.log_event(
                    row,
                    self.run_id,
                    "profile:start",
                    "Failed",
                    error=error,
                )
                self._emit(row, "Error", message)

            return

        # ----- Delay before the next Page/job -----

        if self._last_post_finished_at is not None and not self._wait_between_posts():
            return

        try:
            profile_data = start_profile(profile_uid)
            report.log_event(
                valid_rows[0],
                self.run_id,
                "profile:start",
                "Started",
            )
        except Exception as error:
            report.log_event(
                valid_rows[0],
                self.run_id,
                "profile:start",
                "Failed",
                error=error,
            )

            for row in valid_rows:
                message = "Could not start the AdsPower profile. See DevLog."
                report.upsert_result(row, "Failed", error=message)
                self._emit(row, "Error", message)

            raise _FatalAutomationError(
                str(error),
                "AdsPower API failed. Check Settings and PageAuto_DevLog.xlsx.",
            ) from error

        driver = None
        fatal_error = None

        try:
            try:
                driver = connect_driver(profile_data)
            except Exception as error:
                report.log_event(
                    valid_rows[0],
                    self.run_id,
                    "browser:attach",
                    "Failed",
                    error=error,
                )

                for row in valid_rows:
                    message = "Could not connect to the AdsPower browser. See DevLog."
                    report.upsert_result(row, "Failed", error=message)
                    self._emit(row, "Error", message)

                fatal_error = _FatalAutomationError(
                    str(error),
                    "Could not connect to the AdsPower browser. "
                    "Check Selenium and PageAuto_DevLog.xlsx.",
                )

            if driver is not None:
                for index, row in enumerate(valid_rows):
                    if self.stop_requested:
                        break

                    # ----- Delay between posts -----

                    if index > 0 and not self._wait_between_posts():
                        break

                    self._publish_row(driver, row, report)
                    self._last_post_finished_at = datetime.now().astimezone()

        finally:
            if driver is not None:
                try:
                    driver.quit()
                except Exception as error:
                    report.log_event(
                        valid_rows[0],
                        self.run_id,
                        "browser:close",
                        "Failed",
                        error=error,
                    )

            try:
                stop_profile(profile_uid)
                report.log_event(
                    valid_rows[0],
                    self.run_id,
                    "profile:stop",
                    "Stopped",
                )
            except Exception as error:
                report.log_event(
                    valid_rows[0],
                    self.run_id,
                    "profile:stop",
                    "Failed",
                    error=error,
                )
                fatal_error = _FatalAutomationError(
                    str(error),
                    "Could not stop the AdsPower profile. "
                    "Check PageAuto_DevLog.xlsx.",
                )

        if fatal_error:
            raise fatal_error

    def _publish_row(self, driver, row: dict, report: PageAutoReport) -> None:
        attempt = report.next_attempt(row)
        post_id = row.get("post_id", "")
        caption = str(row.get("caption") or "").strip()

        report.upsert_result(row, "Running")
        self._emit(row, "Running")
        report.log_event(
            row,
            self.run_id,
            f"publish:{post_id}",
            "Running",
            attempt,
        )

        # ----- Publish post first -----
        try:
            publish_photo(driver, row)

        except PublishUnknownError as error:
            message = (
                "Publish result could not be confirmed. "
                "Check the Page before retrying."
            )

            report.upsert_result(row, "Unknown", error=message)
            report.log_event(
                row,
                self.run_id,
                f"publish:{post_id}",
                "Unknown",
                attempt,
                error,
            )
            self._emit(row, "Unknown", message)
            return

        except Exception as error:
            message = "Failed to publish the post. See PageAuto_DevLog.xlsx."

            report.upsert_result(row, "Failed", error=message)
            report.log_event(
                row,
                self.run_id,
                f"publish:{post_id}",
                "Failed",
                attempt,
                error,
            )
            self._emit(row, "Error", message)
            return

        published_at = datetime.now().astimezone().replace(tzinfo=None)
        comment = str(row.get("comment") or "")
        comment_error = None
        permalink_error = None
        post_url = ""

        # ----- Post the whole comment before retrieving URL -----
        if comment.strip():
            try:
                post_comment(driver, caption, comment)
            except Exception as error:
                comment_error = error

        # ----- Click timestamp and retrieve URL after comment attempt -----
        try:
            post_url = get_published_post_url(
                driver,
                caption,
                attempts=2,
            )

            report.log_event(
                row,
                self.run_id,
                f"permalink:{post_id}",
                "Retrieved",
                attempt,
                post_url=post_url,
            )

        except Exception as error:
            permalink_error = error

            report.log_event(
                row,
                self.run_id,
                f"permalink:{post_id}",
                "Failed",
                attempt,
                error,
            )

        # ----- Log comment result after URL retrieval -----
        row_errors = []

        if comment.strip():
            if comment_error is None:
                report.log_event(
                    row,
                    self.run_id,
                    f"comment:{post_id}",
                    "Published",
                    attempt,
                    post_url=post_url,
                )
            else:
                message = (
                    "Post was published, but the comment could not be added. "
                    "See PageAuto_DevLog.xlsx."
                )
                row_errors.append(message)

                report.log_event(
                    row,
                    self.run_id,
                    f"comment:{post_id}",
                    "Failed",
                    attempt,
                    comment_error,
                    post_url,
                )
        else:
            report.log_event(
                row,
                self.run_id,
                f"comment:{post_id}",
                "Skipped",
                attempt,
                post_url=post_url,
            )

        # ----- Preserve Published status if permalink retrieval fails -----
        if permalink_error is not None:
            row_errors.append(
                "Post was published, but its permalink could not be retrieved. "
                "See PageAuto_DevLog.xlsx."
            )

        row_error = " ".join(row_errors)

        report.upsert_result(
            row,
            "Published",
            published_at=published_at,
            post_url=post_url,
            error=row_error,
        )

        self._emit(row, "Done", row_error)

    def _order_is_complete(
        self,
        jobs: list[dict],
        report: PageAutoReport,
    ) -> bool:
        for job in jobs:
            for row in job["rows"]:
                status = report.get_result(row.get("task_id", "")).get("post_status")

                if status not in _TERMINAL_STATUSES:
                    return False

        return True

    def _wait_between_posts(self) -> bool:
        if self._last_post_finished_at is None:
            return not self.stop_requested

        delay_minutes = max(0.0, float(PAGE_AUTO_POST_DELAY))
        next_post_at = self._last_post_finished_at + timedelta(minutes=delay_minutes)

        return self._wait_until(next_post_at)

    def _wait_until(self, due_at: datetime | None) -> bool:
        if self.stop_requested:
            return False

        if due_at is None:
            return True

        while not self.stop_requested:
            now = datetime.now().astimezone()

            if now >= due_at:
                return True

            remaining = (due_at - now).total_seconds()
            time.sleep(min(1.0, max(0.1, remaining)))

        return False

    def _emit(self, row: dict, ui_status: str, error: str = "") -> None:
        self.progress.emit(
            {
                "task_id": row.get("task_id"),
                "ui_status": ui_status,
                "error": error,
            }
        )

    @staticmethod
    def _parse_order(value):
        try:
            return int(float(value)) if value not in (None, "") else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _parse_datetime(value):
        if not value:
            return None

        try:
            result = datetime.fromisoformat(str(value))
            return result.astimezone()
        except (TypeError, ValueError):
            return None


def _build_signature(rows: list[dict]) -> tuple:
    return tuple(tuple(row.get(field) for field in _SIGNATURE_FIELDS) for row in rows)
