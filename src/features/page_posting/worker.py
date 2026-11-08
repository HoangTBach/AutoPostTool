from PySide6.QtCore import QThread, Signal

<<<<<<< Updated upstream
from src.features.page_posting.excel import get_data_file_stamp, load_page_rows
from src.features.page_posting.service import build_page_jobs, flatten_page_jobs
=======
from pathlib import Path
from urllib.parse import urlsplit
>>>>>>> Stashed changes

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


<<<<<<< Updated upstream
# ----- Signature -----
def _build_signature(rows: list[dict]) -> tuple:
    return tuple(tuple(row.get(field) for field in _SIGNATURE_FIELDS) for row in rows)
=======
        if session is not None:
            driver = session.get("driver")
            profile_data = session.get("profile_data") or {}

            driver_usable = self._driver_is_usable(driver)
            profile_matches = False

            if driver_usable and isinstance(profile_data, dict) and profile_data:
                try:
                    profile_matches = self._driver_matches_profile(
                        driver,
                        profile_data,
                    )
                except Exception:
                    profile_matches = False

            if profile_matches:
                return session

            if driver_usable:
                cmd_log(
                    "WARNING",
                    "AdsPower Selenium session could not be verified. Reconnecting.",
                )
            else:
                cmd_log(
                    "WARNING",
                    "AdsPower Selenium session is unresponsive. Reconnecting.",
                )

            self._detach_stale_driver(profile_uid, driver)
            sessions.pop(profile_uid, None)

        session = self._start_profile_session(profile_uid, row, report)
        sessions[profile_uid] = session

        return session

    def _start_profile_session(
        self,
        profile_uid: str,
        row: dict,
        report: PageAutoReport,
    ) -> dict:
        profile_started = False
        profile_data = None
        driver = None
        stage = "profile:check"
        profile_name = str(
            row.get("profile_name") or row.get("profile_id") or ""
        ).strip()
        if not profile_name or profile_name == profile_uid:
            profile_name = "Unnamed profile"

        try:
            # ----- A Timed-Out Active Check Must Not Prevent a Start Attempt -----
            try:
                profile_data = get_active_profile(profile_uid)
            except AdsPowerConnectionError as lookup_error:
                reason = str(lookup_error).replace(profile_uid, "[hidden]")
                cmd_log(
                    "WARNING",
                    f"AdsPower active-profile check failed for {profile_name}: "
                    f"{reason}. Trying to open the profile.",
                )
                profile_data = None

            if profile_data:
                report.log_event(row, self.run_id, "profile:reuse", "Active")
            else:
                stage = "profile:start"
                profile_data = start_profile(profile_uid)
                profile_started = True
                report.log_event(row, self.run_id, "profile:start", "Started")

            returned_uid = str(profile_data.get("user_id") or "").strip()
            if returned_uid and returned_uid != profile_uid:
                raise AdsPowerConnectionError(
                    "AdsPower returned a profile different from the requested one. "
                    "Check the profile_uid column in Excel."
                )

            stage = "browser:attach"
            driver = connect_driver(profile_data)
            if not self._driver_matches_profile(driver, profile_data):
                raise AdsPowerConnectionError(
                    "Selenium is attached to a different AdsPower profile."
                )

            report.log_event(row, self.run_id, "browser:attach", "Connected")
            return {
                "driver": driver,
                "last_row": row,
                "profile_started": profile_started,
                "profile_uid": profile_uid,
                "profile_data": profile_data,
            }

        except Exception as error:
            try:
                report.log_event(
                    row,
                    self.run_id,
                    stage,
                    "Failed",
                    attempt=1,
                    error=error,
                    retryable=bool(getattr(error, "retryable", False)),
                )
            except Exception:
                pass

            # ----- Clean Up Any Browser That Was Actually Opened -----
            if profile_data is not None:
                try:
                    stop_profile(profile_uid)
                    cmd_log("INFO", f"Closed AdsPower profile: {profile_name}")
                except Exception as cleanup_error:
                    reason = str(cleanup_error).replace(profile_uid, "[hidden]")
                    cmd_log(
                        "WARNING",
                        f"Could not close AdsPower profile: {profile_name}. "
                        f"Reason: {reason}",
                    )

            if driver is not None:
                try:
                    driver.service.stop()
                except Exception as cleanup_error:
                    reason = str(cleanup_error).replace(profile_uid, "[hidden]")
                    cmd_log(
                        "WARNING",
                        f"Cannot release Selenium for AdsPower profile: "
                        f"{profile_name}. Reason: {reason}",
                    )
            raise

    def _wait_after_comment_before_profile_close(self, target: dict) -> None:
        """Wait only after a confirmed Comment on a profile's last task."""
        finished_at = target.get("_comment_completed_at")
        if finished_at is None or self.stop_requested:
            return
        remaining = max(
            0.0,
            COMMENT_PROFILE_CLOSE_DELAY_SECONDS
            - (time.monotonic() - float(finished_at)),
        )
        if remaining <= 0:
            return
        cmd_log(
            "INFO",
            f"Waiting {math.ceil(remaining)}s after Comment before closing "
            "AdsPower profile...",
        )
        self._wait_interruptibly(remaining)

    def _close_profile_sessions(
        self,
        sessions: dict[str, dict],
        report: PageAutoReport | None,
    ) -> None:
        """Stop AdsPower browsers once their final Page task has finished."""
        for profile_uid, session in list(sessions.items()):
            driver = session.get("driver")
            row = session.get("last_row") or {}
            profile_name = str(
                row.get("profile_name") or row.get("profile_id") or ""
            ).strip()
            if not profile_name or profile_name == profile_uid:
                profile_name = "Unnamed profile"

            # ----- Close the Actual AdsPower Browser -----
            try:
                stop_profile(profile_uid)
            except Exception as error:
                # Never expose the internal AdsPower UID in user-facing logs.
                reason = str(error).replace(profile_uid, "[hidden]")
                cmd_log(
                    "WARNING",
                    f"Could not close AdsPower profile: {profile_name}. "
                    f"Reason: {reason}",
                )
                if report is not None:
                    report.log_event(
                        row,
                        self.run_id,
                        "profile:stop",
                        "Failed",
                        error=error,
                        retryable=True,
                    )
            else:
                cmd_log("INFO", f"Closed AdsPower profile: {profile_name}")
                if report is not None:
                    report.log_event(
                        row,
                        self.run_id,
                        "profile:stop",
                        "Stopped",
                    )
            finally:
                # ----- Release the Selenium Driver Process -----
                if driver is not None:
                    try:
                        driver.service.stop()
                    except Exception as error:
                        reason = str(error).replace(profile_uid, "[hidden]")
                        cmd_log(
                            "WARNING",
                            f"Cannot release Selenium for AdsPower profile: "
                            f"{profile_name}. Reason: {reason}",
                        )
                        if report is not None:
                            report.log_event(
                                row,
                                self.run_id,
                                "browser:close",
                                "Failed",
                                error=error,
                                retryable=False,
                            )
                    else:
                        if report is not None:
                            report.log_event(
                                row,
                                self.run_id,
                                "browser:close",
                                "Detached",
                            )

    def _log_target_failure(
        self,
        target: dict,
        reason: str,
        action: str = "switch to Facebook Page",
    ) -> None:
        row = target["rows"][0]
        page_name = target.get("page_name") or target.get("page_id") or "Unknown Page"
        excel_row = row.get("_excel_row") or target.get("row_number", "?")

        cmd_log("ERROR", f"Failed to {action}")
        cmd_log("ERROR", f"Page: {page_name} | Excel row: {excel_row}")
        cmd_log("ERROR", f"Reason: {reason}")
        cmd_log("INFO", "Skipping current Page")

    # ----- Comment on an Opened Published Post -----
    def _post_comment(
        self,
        target: dict,
        report: PageAutoReport,
        driver,
        post_url: str,
        attempt: int,
        published_at,
    ) -> str:
        row = target["rows"][0]
        comment = str(row.get("comment") or "").strip()
        if not comment:
            self._emit_rows(target["rows"], "Done")
            return "passed"

        cmd_log("INFO", "Posting comment...")

        for comment_attempt in range(1, MAX_COMMENT_PREPARE_ATTEMPTS + 1):
            if self.stop_requested:
                # The comment has not been sent in this iteration.
                message = (
                    "Post published; Comment not sent (retryable): "
                    "Stopped before sending Comment."
                )
                report.upsert_result(
                    row,
                    "Published",
                    published_at=published_at,
                    post_url=post_url,
                    error=message,
                )
                report.log_event(
                    row,
                    self.run_id,
                    "post:comment",
                    "Interrupted",
                    attempt=comment_attempt,
                    retryable=True,
                )
                self._emit_rows(target["rows"], "Done", message)
                return "stopped"

            comment_send_started = False

            def before_comment_send():
                nonlocal comment_send_started
                if self.stop_requested:
                    raise FacebookPostError(
                        "Stopped before sending Comment.",
                        retryable=True,
                    )
                # Persist the irreversible boundary before the one send.
                report.log_event(
                    row,
                    self.run_id,
                    "post:comment",
                    "Sending",
                    attempt=comment_attempt,
                    retryable=False,
                )
                comment_send_started = True

            try:
                confirmed = post_comment_on_opened_post(
                    driver,
                    comment,
                    post_url=post_url,
                    on_before_send=before_comment_send,
                )
                if not confirmed:
                    raise CommentSubmissionUnknownError(
                        "Comment send was not confirmed. Do not resend.",
                    )
            except Exception as error:
                uncertain = comment_send_started or isinstance(
                    error, CommentSubmissionUnknownError
                )
                retryable = not uncertain and bool(getattr(error, "retryable", False))
                will_retry = (
                    retryable
                    and comment_attempt < MAX_COMMENT_PREPARE_ATTEMPTS
                    and not self.stop_requested
                )
                reason = str(error).splitlines()[0][:300]

                if will_retry:
                    report.log_event(
                        row,
                        self.run_id,
                        "post:comment",
                        "Retrying",
                        attempt=comment_attempt,
                        error=error,
                        retryable=True,
                    )
                    cmd_log(
                        "WARNING",
                        f"Comment preparation attempt {comment_attempt}/"
                        f"{MAX_COMMENT_PREPARE_ATTEMPTS} failed: {reason}. "
                        "Retrying Comment only.",
                    )
                    if self._wait_interruptibly(RETRY_DELAY_SECONDS):
                        # Reset the abandoned unsent Lexical draft before
                        # retrying Comment. Never repeat Publish or Send.
                        cmd_log("INFO", "Reloading Post page for Comment retry...")
                        try:
                            driver.refresh()
                            open_published_post_url(driver, post_url)
                        except Exception as reload_error:
                            detail = str(reload_error).splitlines()[0][:200]
                            profile_uid = str(target.get("profile_uid") or "").strip()
                            if profile_uid:
                                detail = detail.replace(profile_uid, "[hidden]")
                            cmd_log(
                                "WARNING",
                                f"Could not reload Post page for Comment retry: {detail}",
                            )
                        continue
                    # Stopped before Send; safe to resume on a future run.
                    retryable = True
                    reason = "Stopped before retrying Comment."

                # Keep Published and its permalink, regardless of Comment outcome.
                # A prefix for verified *pre-send* failures permits Comment-only
                # recovery on the next run; it never calls Publish again.
                if uncertain:
                    message = (
                        "Post published; Comment outcome requires verification: "
                        + reason
                    )
                    event_status = "Unknown"
                    retryable = False
                elif retryable:
                    message = "Post published; Comment not sent (retryable): " + reason
                    event_status = "Failed"
                else:
                    message = "Post published; Comment not sent: " + reason
                    event_status = "Failed"

                report.upsert_result(
                    row,
                    "Published",
                    published_at=published_at,
                    post_url=post_url,
                    error=message,
                )
                report.log_event(
                    row,
                    self.run_id,
                    "post:comment",
                    event_status,
                    attempt=comment_attempt,
                    error=error,
                    retryable=retryable,
                )
                cmd_log("WARNING", message)
                self._emit_rows(target["rows"], "Done", message)
                return "passed"

            report.upsert_result(
                row,
                "Published",
                published_at=published_at,
                post_url=post_url,
                error="",
            )
            report.log_event(
                row,
                self.run_id,
                "post:comment",
                "Success",
                attempt=comment_attempt,
                retryable=False,
            )
            cmd_log("SUCCESS", "Comment posted successfully")
            target["_comment_completed_at"] = time.monotonic()
            self._emit_rows(target["rows"], "Done")
            return "passed"

        return "passed"

    # ----- Recheck an Uncertain Comment Without Resending -----
    def _verify_existing_comment(self, target, report, driver) -> str:
        row = target["rows"][0]
        saved = report.get_result(row.get("task_id", ""))
        post_url = str(saved.get("post_url") or "").strip()
        comment = str(row.get("comment") or "").strip()
        cmd_log("INFO", "Switching post...")
        try:
            opened_url = open_published_post_url(driver, post_url)
            cmd_log("SUCCESS", f"Facebook Post URL: {opened_url}")
            cmd_log("INFO", "Verifying existing comment...")
            confirmed = verify_visible_published_comment(
                driver,
                comment,
                post_url=opened_url,
                timeout=25,
            )
        except Exception as error:
            reason = str(error).splitlines()[0][:240]
            message = "Comment verification is still uncertain: " + reason
            report.log_event(
                row,
                self.run_id,
                "post:comment",
                "Unknown",
                attempt=0,
                error=error,
                retryable=False,
            )
            cmd_log("WARNING", message)
            self._emit_rows(target["rows"], "Done", message)
            return "passed"

        if not confirmed:
            message = str(saved.get("error") or "Comment still requires verification.")
            cmd_log(
                "WARNING", "Existing Comment was not found; no new Comment was sent."
            )
            report.log_event(
                row,
                self.run_id,
                "post:comment",
                "Unknown",
                attempt=0,
                retryable=False,
            )
            self._emit_rows(target["rows"], "Done", message)
            return "passed"

        report.upsert_result(
            row,
            "Published",
            published_at=saved.get("published_at"),
            post_url=opened_url,
            error="",
        )
        report.log_event(
            row,
            self.run_id,
            "post:comment",
            "Verified",
            attempt=0,
            retryable=False,
        )
        cmd_log("SUCCESS", "Existing Comment verified successfully")
        self._emit_rows(target["rows"], "Done")
        return "passed"

    # ----- Capture Post URL After Submission -----
    def _capture_post_url(
        self,
        target: dict,
        report: PageAutoReport,
        driver,
        attempt: int,
    ) -> str:
        row = target["rows"][0]

        # ----- Find and Verify the New Post Before Reporting Success -----
        try:
            post_url = capture_published_post_url(
                driver,
                row,
                published_after=target.get("_submit_started_at"),
                should_stop=lambda: self.stop_requested,
            )
        except Exception as error:
            message = (
                "Post submission was attempted, but its URL is unverified. "
                f"Do not republish: {error}"
            )
            report.upsert_result(row, "Unknown", error=message)
            report.log_event(
                row,
                self.run_id,
                "post:url",
                "Unknown",
                attempt=attempt,
                error=error,
                retryable=False,
            )
            cmd_log("WARNING", message)
            self._emit_rows(target["rows"], "Unknown", message)
            return "failed"

        # ----- Save the Verified URL Before Any Additional Navigation -----
        published_at = datetime.now().astimezone().replace(tzinfo=None)
        report.upsert_result(
            row,
            "Published",
            published_at=published_at,
            post_url=post_url,
            error="",
        )
        report.log_event(
            row,
            self.run_id,
            "post:url",
            "Captured",
            attempt=attempt,
            retryable=False,
        )
        cmd_log("SUCCESS", "Post published successfully")

        # ----- Switch to the Exact Captured Post Page -----
        cmd_log("INFO", "Switching post...")
        try:
            opened_url = open_published_post_url(driver, post_url)
        except Exception as error:
            # Publication was verified and its URL is saved. A navigation
            # problem must not turn this completed post into an unsafe retry.
            message = f"Post URL saved, but could not open its page: {error}"
            report.log_event(
                row,
                self.run_id,
                "post:navigate",
                "Failed",
                attempt=attempt,
                error=error,
                retryable=False,
            )
            cmd_log("WARNING", message)
            cmd_log("SUCCESS", f"Facebook Post URL: {post_url}")
            self._emit_rows(target["rows"], "Done", message)
            return "passed"

        report.log_event(
            row,
            self.run_id,
            "post:navigate",
            "Success",
            attempt=attempt,
            retryable=False,
        )
        cmd_log("SUCCESS", f"Facebook Post URL: {opened_url}")
        # ----- Separate Comment Group After Post Navigation -----
        return self._post_comment(
            target,
            report,
            driver,
            opened_url,
            attempt,
            published_at,
        )

    def _process_target(
        self,
        target: dict,
        report: PageAutoReport,
        driver=None,
        sessions: dict[str, dict] | None = None,
    ) -> str:
        rows = target["rows"]
        row = rows[0]

        profile_uid = str(target.get("profile_uid") or "").strip()
        page_name = str(target.get("page_name") or "").strip()
        page_link = str(target.get("page_link") or "").strip()

        # ----- Validate Page Target -----
        missing = (
            "Page name is missing."
            if not page_name
            else (
                "Page link is missing."
                if not page_link
                else (
                    "AdsPower profile UID is missing."
                    if not profile_uid
                    else (
                        "AdsPower WebDriver is not available." if driver is None else ""
                    )
                )
            )
        )

        if missing:
            retryable = driver is None and bool(profile_uid and page_name and page_link)

            report.upsert_page_result(
                row,
                "FAILED",
                error=missing,
                retryable=retryable,
            )

            report.log_event(
                row,
                self.run_id,
                "page:switch",
                "Failed",
                error=FacebookSwitchError(missing, retryable=retryable),
                retryable=retryable,
            )

            self._emit_rows(rows, "Error", missing)
            return "failed"

        # ----- Retry Facebook Page Switch -----
        for attempt in range(1, MAX_PAGE_SWITCH_ATTEMPTS + 1):
            if self.stop_requested:
                report.upsert_page_result(
                    row,
                    "INTERRUPTED",
                    attempt=attempt - 1,
                    error="Stopped before Page switch.",
                    retryable=True,
                )
                return "stopped"

            report.upsert_page_result(row, "RUNNING", attempt=attempt)

            report.log_event(
                row,
                self.run_id,
                "page:switch",
                "Running",
                attempt=attempt,
            )

            try:
                switch_facebook_page(
                    driver,
                    page_name=page_name,
                    page_link=page_link,
                )

            except Exception as error:
                retryable = bool(getattr(error, "retryable", False))

                will_retry = retryable and attempt < MAX_PAGE_SWITCH_ATTEMPTS

                report.upsert_page_result(
                    row,
                    "RUNNING" if will_retry else "FAILED",
                    attempt=attempt,
                    error=str(error),
                    retryable=retryable,
                )

                report.log_event(
                    row,
                    self.run_id,
                    "page:switch",
                    "Retrying" if will_retry else "Failed",
                    attempt=attempt,
                    error=error,
                    retryable=retryable,
                )

                if not will_retry:
                    self._log_target_failure(target, str(error), "switch Facebook Page")
                    self._emit_rows(rows, "Error", str(error))
                    return "failed"

                if not self._wait_interruptibly(RETRY_DELAY_SECONDS):
                    report.upsert_page_result(
                        row,
                        "INTERRUPTED",
                        attempt=attempt,
                        error="Stopped before Page switch retry.",
                        retryable=True,
                    )
                    return "stopped"

                if sessions is not None:
                    try:
                        session = self._ensure_profile_session(
                            profile_uid, row, report, sessions
                        )
                        session["last_row"] = row
                        driver = session["driver"]

                    except Exception as recovery_error:
                        cmd_log(
                            "WARNING",
                            f"Browser recovery failed: {recovery_error}",
                        )

                continue

            cmd_log("SUCCESS", f"Facebook Page ready: {page_name}")
            report.upsert_page_result(row, "SUCCESS", attempt=attempt)

            report.log_event(
                row,
                self.run_id,
                "page:switch",
                "Success",
                attempt=attempt,
            )
            break

        # ----- Resume URL Capture Without Reposting -----
        if target.get("_capture_url_only"):
            cmd_log("INFO", f"Retrying URL capture only: {page_name}")
            self._emit_rows(rows, "Running")
            return self._capture_post_url(target, report, driver, attempt=0)

        # ----- Verify a Previously Submitted Comment Without Sending -----
        if target.get("_verify_comment_only"):
            return self._verify_existing_comment(target, report, driver)

        # ----- Resume Only a Previously Unsent, Retryable Comment -----
        if target.get("_comment_only"):
            saved = report.get_result(row.get("task_id", ""))
            post_url = str(saved.get("post_url") or "").strip()
            published_at = saved.get("published_at")
            cmd_log("INFO", "Switching post...")
            try:
                opened_url = open_published_post_url(driver, post_url)
            except Exception as error:
                reason = str(error).splitlines()[0][:300]
                message = f"Post URL saved; Comment page could not be opened: {reason}"
                report.log_event(
                    row,
                    self.run_id,
                    "post:comment:navigate",
                    "Failed",
                    error=error,
                    retryable=bool(getattr(error, "retryable", False)),
                )
                cmd_log("WARNING", message)
                self._emit_rows(rows, "Done", message)
                return "passed"
            cmd_log("SUCCESS", f"Facebook Post URL: {opened_url}")
            return self._post_comment(
                target,
                report,
                driver,
                opened_url,
                attempt=0,
                published_at=published_at,
            )

        # ----- Retry Entire Post Only Before Publish -----
        for attempt in range(1, MAX_POST_PREPARE_ATTEMPTS + 1):
            if self.stop_requested:
                return "stopped"

            # A crash during preparation is safe to retry.
            report.upsert_result(
                row,
                "Preparing",
                error="",
            )

            report.log_event(
                row,
                self.run_id,
                "post:prepare",
                "Running",
                attempt=attempt,
                retryable=True,
            )

            # ----- Persist the Irreversible Boundary -----
            def before_submit():
                if self.stop_requested:
                    raise FacebookPostError(
                        "Stopped before Publish.",
                        retryable=False,
                    )

                # Save BEFORE clicking Publish.
                target["_submit_started_at"] = time.time()
                report.upsert_result(
                    row,
                    "Publishing",
                    error="",
                )

                report.log_event(
                    row,
                    self.run_id,
                    "post:publish",
                    "Publishing",
                    attempt=attempt,
                    retryable=False,
                )

            try:
                cmd_log("INFO", "Publishing post...")
                # ----- Run the Entire Facebook Post -----
                result = run_facebook_post(
                    driver,
                    row,
                    on_before_submit=before_submit,
                )

                if result != "Running":
                    raise FacebookPostError(
                        f"Unexpected Facebook Post result: {result}",
                        retryable=False,
                    )

            except PublishUnknownError as error:
                # ----- Never Retry an Uncertain Publish -----
                report.upsert_result(
                    row,
                    "Unknown",
                    error=str(error),
                )

                report.log_event(
                    row,
                    self.run_id,
                    "post:publish",
                    "Unknown",
                    attempt=attempt,
                    error=error,
                    retryable=False,
                )

                self._emit_rows(
                    rows,
                    "Unknown",
                    str(error),
                )

                return "failed"

            except Exception as error:
                # ----- Check Whether Publish May Have Started -----
                saved = report.get_result(row.get("task_id", ""))

                current_status = str(saved.get("post_status") or "").strip()

                if current_status in {
                    "Publishing",
                    "Running",
                }:
                    message = (
                        "Publish outcome cannot be verified. "
                        "Do not retry automatically: "
                        f"{error}"
                    )

                    report.upsert_result(
                        row,
                        "Unknown",
                        error=message,
                    )

                    report.log_event(
                        row,
                        self.run_id,
                        "post:publish",
                        "Unknown",
                        attempt=attempt,
                        error=error,
                        retryable=False,
                    )

                    self._emit_rows(
                        rows,
                        "Unknown",
                        message,
                    )

                    return "failed"

                # ----- Retry Only Before Publish -----
                retryable = bool(getattr(error, "retryable", False))

                will_retry = (
                    retryable
                    and attempt < MAX_POST_PREPARE_ATTEMPTS
                    and not self.stop_requested
                )

                report.upsert_result(
                    row,
                    "Preparing" if will_retry else "Failed",
                    error=str(error),
                )

                report.log_event(
                    row,
                    self.run_id,
                    "post:prepare",
                    "Retrying" if will_retry else "Failed",
                    attempt=attempt,
                    error=error,
                    retryable=retryable,
                )

                if not will_retry:
                    self._log_target_failure(
                        target,
                        str(error),
                        "prepare Facebook Post",
                    )

                    self._emit_rows(
                        rows,
                        "Error",
                        str(error),
                    )

                    return "failed"

                cmd_log(
                    "WARNING",
                    f"Facebook Post attempt {attempt}/"
                    f"{MAX_POST_PREPARE_ATTEMPTS} failed: {error}. "
                    "Restarting the whole post.",
                )

                # ----- Wait Before Restarting Whole Post -----
                if not self._wait_interruptibly(RETRY_DELAY_SECONDS):
                    return "stopped"

                # ----- Recover Browser Connection -----
                if sessions is not None:
                    try:
                        session = self._ensure_profile_session(
                            profile_uid,
                            row,
                            report,
                            sessions,
                        )

                        session["last_row"] = row
                        driver = session["driver"]

                    except Exception as recovery_error:
                        cmd_log(
                            "WARNING",
                            f"Browser recovery failed: " f"{recovery_error}",
                        )

                continue

            # ----- Publish Click Sent; Verification Is Not Yet Complete -----
            target["_submit_started_at"] = time.time()
            report.upsert_result(
                row,
                "Running",
                error="",
            )

            report.log_event(
                row,
                self.run_id,
                "post:publish",
                "Running",
                attempt=attempt,
                retryable=False,
            )

            # ----- Separate URL Capture Group -----
            self._emit_rows(rows, "Running")
            return self._capture_post_url(target, report, driver, attempt)

        return "failed"

    def _publish_target(self, driver, target: dict, report: PageAutoReport) -> str:
        """Publish one row with retries restricted to pre-submit failures."""
        row = target["rows"][0]
        action = f"post:publish:{row.get('post_id', '')}"
        comment = str(row.get("comment") or "").strip()
        caption = str(row.get("caption") or "").strip()

        saved = report.get_result(row.get("task_id", ""))
        try:
            previous_attempts = max(0, int(saved.get("post_attempt_count") or 0))
        except (TypeError, ValueError):
            previous_attempts = 0

        for retry_index in range(1, MAX_POST_PREPARE_ATTEMPTS + 1):
            attempt = previous_attempts + retry_index
            if self.stop_requested:
                return "stopped"

            # Mark Preparing before any composer action. A restarted run
            # can safely retry it if the process crashes here.
            report.upsert_result(
                row,
                "Preparing",
                error="",
                attempt=attempt,
                retryable=True,
            )
            self._emit_rows(target["rows"], "Running")
            report.log_event(
                row,
                self.run_id,
                action,
                "Preparing",
                attempt=attempt,
                retryable=True,
            )

            def before_submit():
                if self.stop_requested:
                    raise FacebookPostError(
                        "Stop requested before publishing.",
                        retryable=False,
                    )
                # Persist BEFORE clicking Post. If the app crashes after this
                # point, the next run must NOT submit the same post again.
                report.upsert_result(
                    row,
                    "Publishing",
                    error="",
                    attempt=attempt,
                    retryable=False,
                )
                report.log_event(
                    row,
                    self.run_id,
                    action,
                    "Publishing",
                    attempt=attempt,
                    retryable=False,
                )

            try:
                run_facebook_post(driver, row, on_before_submit=before_submit)
            except PublishUnknownError as error:
                report.upsert_result(
                    row,
                    "Unknown",
                    error=str(error),
                    attempt=attempt,
                    retryable=False,
                )
                report.log_event(
                    row,
                    self.run_id,
                    action,
                    "Unknown",
                    attempt=attempt,
                    error=error,
                    retryable=False,
                )
                self._emit_rows(target["rows"], "Unknown", str(error))
                return "failed"
            except Exception as error:
                # A callback may have stored Publishing before raising.
                # Treat it as unsafe to retry whenever that status is present.
                current = report.get_result(row["task_id"])
                if current.get("post_status") == "Publishing":
                    report.upsert_result(
                        row,
                        "Unknown",
                        error=str(error),
                        attempt=attempt,
                        retryable=False,
                    )
                    self._emit_rows(target["rows"], "Unknown", str(error))
                    return "failed"

                retryable = bool(getattr(error, "retryable", False))
                will_retry = (
                    retryable
                    and retry_index < MAX_POST_PREPARE_ATTEMPTS
                    and not self.stop_requested
                )
                report.log_event(
                    row,
                    self.run_id,
                    action,
                    "Retrying" if will_retry else "Failed",
                    attempt=attempt,
                    error=error,
                    retryable=retryable,
                )
                if will_retry:
                    cmd_log(
                        "WARNING",
                        f"Post preparation try {retry_index}/"
                        f"{MAX_POST_PREPARE_ATTEMPTS} failed; retrying: {error}",
                    )
                    if self._wait_interruptibly(RETRY_DELAY_SECONDS):
                        continue
                    return "stopped"

                report.upsert_result(
                    row,
                    "Failed",
                    error=str(error),
                    attempt=attempt,
                    retryable=retryable,
                )
                self._emit_rows(target["rows"], "Error", str(error))
                return "failed"

            # A submission was attempted. From here onward, only verification
            # and comment handling are allowed; never publish a second time.
            published_at = datetime.now().astimezone().replace(tzinfo=None)
            try:
                click_published_post_timestamp(
                    driver,
                    caption,
                    attempts=POST_TIMESTAMP_CYCLES,
                    page_link=str(row.get("page_link") or "").strip(),
                )
                post_url = get_opened_post_url(driver)
                report.log_event(
                    row,
                    self.run_id,
                    "post:url",
                    "Captured",
                    attempt=attempt,
                )
            except Exception as error:
                message = f"Post submitted; URL verification failed: {error}"
                report.upsert_result(
                    row,
                    "Unknown",
                    published_at=published_at,
                    error=message,
                    attempt=attempt,
                    retryable=False,
                )
                report.log_event(
                    row,
                    self.run_id,
                    "post:url",
                    "Unknown",
                    attempt=attempt,
                    error=error,
                    retryable=False,
                )
                self._emit_rows(target["rows"], "Unknown", message)
                return "failed"

            if comment:
                try:
                    confirmed = post_comment_on_opened_post(driver, comment)
                    if not confirmed:
                        raise PublishUnknownError("Comment was not confirmed.")
                except Exception as error:
                    message = f"Post published; comment requires verification: {error}"
                    report.upsert_result(
                        row,
                        "Unknown",
                        published_at=published_at,
                        post_url=post_url,
                        error=message,
                        attempt=attempt,
                        retryable=False,
                    )
                    report.log_event(
                        row,
                        self.run_id,
                        "post:comment",
                        "Unknown",
                        attempt=attempt,
                        error=error,
                        retryable=False,
                    )
                    self._emit_rows(target["rows"], "Unknown", message)
                    return "failed"
                report.log_event(
                    row,
                    self.run_id,
                    "post:comment",
                    "Published",
                    attempt=attempt,
                )

            report.upsert_result(
                row,
                "Published",
                published_at=published_at,
                post_url=post_url,
                error="",
                attempt=attempt,
                retryable=False,
            )
            report.log_event(
                row,
                self.run_id,
                action,
                "Published",
                attempt=attempt,
            )
            self._emit_rows(target["rows"], "Done")
            return "passed"

        return "failed"

    def _emit_rows(
        self,
        rows: list[dict],
        ui_status: str,
        error: str = "",
    ):
        if str(ui_status).strip().lower() == "stopped":
            ui_status = "Queued"
            error = ""

        for row in rows:
            self.progress.emit(
                {
                    "task_id": row.get("task_id"),
                    "ui_status": ui_status,
                    "error": error,
                }
            )
>>>>>>> Stashed changes
