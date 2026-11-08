import math
import time
import uuid
from datetime import datetime, timedelta

from pathlib import Path
from urllib.parse import urlsplit

from PySide6.QtCore import QSettings, QThread, Signal

from src.configs.adspower import ADSPOWER_DEFAULT_URL
from src.configs.path import DATA_DIR
from src.configs import automation as automation_config
from src.features.page_posting.adspower import (
    AdsPowerConnectionError,
    check_profiles,
    connect_driver,
    get_active_profile,
    get_profile_debugger_address,
    set_credentials,
    start_profile,
    stop_profile,
)
from src.features.page_posting.excel import (
    get_data_file_stamp,
    load_page_rows,
)
from src.features.page_posting.facebook import (
    FacebookSwitchError,
    FacebookPostError,
    PublishUnknownError,
    switch_facebook_page,
    run_facebook_post,
    capture_published_post_url,
    open_published_post_url,
    post_comment_on_opened_post,
    verify_visible_published_comment,
    CommentSubmissionUnknownError,
)
from src.features.page_posting.service import (
    build_page_jobs,
    flatten_page_jobs,
)
from src.features.page_posting.report import PageAutoReport
from src.features.page_posting import validation

from src.utils.cmd_log import cmd_log

# ----- Config -----
MAX_PAGE_SWITCH_ATTEMPTS = 3
MAX_POST_PREPARE_ATTEMPTS = 3
MAX_COMMENT_PREPARE_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 2
COMMENT_PROFILE_CLOSE_DELAY_SECONDS = 10


# ---- Utility Functions -----
def _cmd_separator() -> None:
    print("-" * 65, flush=True)


# ----- Signature -----
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
    "page_name",
    "page_link",
    "page_status",
    "caption",
    "media",
    "comment",
)


def _normalize_row(row: dict) -> dict:
    normalized = dict(row)

    media = normalized.get("media") or normalized.get("image") or ""
    normalized["media"] = str(media).strip()
    normalized.setdefault("image", normalized["media"])
    normalized.setdefault("_status_media", normalized["media"])

    page_name = normalized.get("page_name") or normalized.get("page") or ""
    normalized["page"] = str(page_name).strip()
    normalized["page_name"] = normalized["page"]

    normalized.setdefault("status", "")
    normalized.setdefault("error", "")

    return normalized


def _validate_rows(rows: list[dict]) -> tuple[list[dict], list[str]]:
    normalized_rows = [_normalize_row(row) for row in rows]

    validate_all = getattr(validation, "validate_page_rows", None)

    if callable(validate_all):
        validated_rows, errors = validate_all(
            normalized_rows,
            return_errors=True,
        )
        return [_normalize_row(row) for row in validated_rows], errors

    validate_one = getattr(validation, "validate_row", None)

    if not callable(validate_one):
        raise RuntimeError(
            "The validation module has no validate_page_rows() "
            "or validate_row() function."
        )

    validated_rows = []
    errors = []

    for index, row in enumerate(normalized_rows, start=1):
        try:
            result = validate_one(row)

            if isinstance(result, dict):
                row.update(result)
            elif isinstance(result, str):
                row["_validated_media"] = result

            validated_rows.append(row)

        except Exception as error:
            post_id = row.get("post_id") or f"row {index}"
            errors.append(f"{post_id}: {error}")

    if errors:
        cmd_log(
            "WARNING",
            f"Page Auto validation: {len(errors)} row(s) skipped.",
        )

    return validated_rows, errors


def _build_signature(
    rows: list[dict],
    errors: list[str] | tuple[str, ...] = (),
) -> tuple:
    row_signature = tuple(
        tuple(str(row.get(field) or "") for field in _SIGNATURE_FIELDS) for row in rows
    )

    error_signature = tuple(str(error) for error in errors)

    return row_signature, error_signature


def _resolve_media_paths(
    rows: list[dict],
    media_folder: str | Path | None,
) -> tuple[list[dict], list[str]]:
    folder_text = str(media_folder or "").strip()
    folder = Path(folder_text).expanduser() if folder_text else Path(DATA_DIR)
    folder = folder.resolve()

    if not folder.is_dir():
        raise NotADirectoryError(f"Media folder does not exist: {folder}")

    resolved_rows: list[dict] = []
    errors: list[str] = []

    for index, source_row in enumerate(rows, start=1):
        row = _normalize_row(source_row)
        raw_media = str(row.get("media") or row.get("image") or "").strip()
        raw_media = raw_media.strip('"').strip("'").strip()

        excel_row = row.get("_excel_row") or row.get("_row_number")
        post_id = str(row.get("post_id") or "").strip()
        if excel_row and post_id:
            row_label = f"Excel row {excel_row} (post_id {post_id})"
        elif excel_row:
            row_label = f"Excel row {excel_row}"
        elif post_id:
            row_label = f"post_id {post_id}"
        else:
            row_label = f"Excel data row {index}"

        if not raw_media:
            message = f"{row_label}: Media file path is required."
            row["media"] = ""
            row["image"] = ""
            row["_media_resolution_error"] = message
            row["status"] = "Invalid"
            row["error"] = message
            errors.append(message)
            resolved_rows.append(row)
            continue

        raw_path = Path(raw_media).expanduser()
        candidates: list[Path] = []
        invalid_relative_path = False

        if raw_path.is_absolute():
            candidates.append(raw_path)
            fallback = folder / raw_path.name
            if fallback != raw_path:
                candidates.append(fallback)
        else:
            candidate = (folder / raw_path).resolve()
            try:
                candidate.relative_to(folder)
            except ValueError:
                invalid_relative_path = True
            else:
                candidates.append(candidate)

        media_path = None
        for candidate in candidates:
            try:
                resolved_candidate = candidate.resolve()
            except (OSError, RuntimeError):
                continue

            if resolved_candidate.is_file():
                media_path = resolved_candidate
                break

        if media_path is None:
            if invalid_relative_path:
                expected_path = folder / raw_path
                reason = "relative media path escapes the selected media folder"
            else:
                expected_path = candidates[-1] if candidates else folder / raw_path.name
                reason = f"Media file does not exist: '{raw_media}'"

            message = f"{row_label}: {reason}. Expected: {expected_path}"
            row["media"] = raw_media
            row["image"] = raw_media
            row["_media_resolution_error"] = message
            row["status"] = "Invalid"
            row["error"] = message
            errors.append(message)
            resolved_rows.append(row)
            continue

        resolved_media = str(media_path)
        row["media"] = resolved_media
        row["image"] = resolved_media
        row.pop("_media_resolution_error", None)
        resolved_rows.append(row)

    return resolved_rows, errors


# ----- Import Worker -----
class PageImportWorker(QThread):
    result = Signal(object)
    error = Signal(str)

    def __init__(
        self,
        previous_stamp=None,
        previous_signature=None,
        media_folder: str = "",
    ):
        super().__init__()

        self.previous_stamp = previous_stamp
        self.previous_signature = previous_signature
        self.media_folder = str(media_folder or "").strip()

    def run(self):
        try:
            file_stamp = get_data_file_stamp()

            source_rows = load_page_rows()
            resolved_rows, media_errors = _resolve_media_paths(
                source_rows,
                self.media_folder,
            )

            invalid_media_rows = [
                row for row in resolved_rows if row.get("_media_resolution_error")
            ]
            rows_to_validate = [
                row for row in resolved_rows if not row.get("_media_resolution_error")
            ]

            if rows_to_validate:
                validated_rows, validation_errors = _validate_rows(rows_to_validate)
            else:
                validated_rows, validation_errors = [], []

            validation_errors = list(
                dict.fromkeys([*media_errors, *(validation_errors or [])])
            )

            if media_errors:
                cmd_log(
                    "WARNING",
                    f"Page Auto media validation: {len(media_errors)} row(s) "
                    "have media errors.",
                )
                for media_error in media_errors:
                    cmd_log("WARNING", media_error)

            jobs = build_page_jobs(validated_rows)
            ordered_rows = flatten_page_jobs(jobs)

            display_rows = ordered_rows + invalid_media_rows
            for row_number, row in enumerate(display_rows, start=1):
                row["no"] = row_number

            if not display_rows and not validation_errors:
                raise ValueError(
                    "No Page Auto jobs were created. "
                    "Select posts by filling both page_id and post_order."
                )

            signature = _build_signature(display_rows, validation_errors)

            if signature == self.previous_signature:
                self.result.emit(
                    {
                        "changed": False,
                        "file_stamp": file_stamp,
                        "signature": signature,
                        "validation_errors": validation_errors,
                        "media_folder": self.media_folder,
                    }
                )
                return

            self.result.emit(
                {
                    "changed": True,
                    "file_stamp": file_stamp,
                    "signature": signature,
                    "jobs": jobs,
                    "rows": display_rows,
                    "validation_errors": validation_errors,
                    "media_folder": self.media_folder,
                }
            )

        except Exception as error:
            self.error.emit(str(error))


# ----- Preflight Worker -----
class PagePreflightWorker(QThread):
    result = Signal(object)
    error = Signal(str)

    def __init__(self, api_key: str, profile_uids: list[str]):
        super().__init__()
        self.api_key = str(api_key or "").strip()
        self.profile_uids = [
            str(profile_uid or "").strip()
            for profile_uid in profile_uids
            if str(profile_uid or "").strip()
        ]
        self.stop_requested = False

    def request_stop(self):
        self.stop_requested = True

    def run(self):
        if self.stop_requested:
            return

        try:
            cmd_log("INFO", "Checking Page Auto configuration...")

            settings = QSettings(
                QSettings.Format.IniFormat,
                QSettings.Scope.UserScope,
                "AutoPostTool",
                "AutoPostTool",
            )

            local_api = str(
                settings.value("adspower/local_api", ADSPOWER_DEFAULT_URL)
                or ADSPOWER_DEFAULT_URL
            ).strip()

            set_credentials(self.api_key, api_url=local_api)

            if self.stop_requested:
                return

            checked_profiles = check_profiles(self.profile_uids)

            cmd_log(
                "SUCCESS",
                f"AdsPower API connected; profiles verified: {len(checked_profiles)}",
            )

        except Exception as error:
            message = str(error)
            cmd_log("ERROR", f"AdsPower preflight failed: {message}")

            if not self.stop_requested:
                self.error.emit(message)

            return

        if self.stop_requested:
            return

        cmd_log("SUCCESS", "Preflight checks passed")

        self.result.emit(
            {
                "ok": True,
                "message": (
                    "AdsPower API connection and "
                    f"{len(checked_profiles)} profile(s) verified."
                ),
            }
        )


# ----- Posting Worker -----
class PageAutoWorker(QThread):
    error = Signal(str)
    progress = Signal(object)
    state_changed = Signal(object)
    order_completed = Signal(object)
    run_completed = Signal(object)

    def __init__(self, jobs: list[dict]):
        super().__init__()

        self.jobs = jobs
        self.stop_requested = False
        self.run_id = str(uuid.uuid4())

    def request_stop(self):
        if not self.stop_requested:
            self.stop_requested = True
            cmd_log(
                "INFO",
                "Stop requested. The current browser action will finish safely; "
                "no new Page row will start afterward.",
            )

    def _recover_interrupted_rows(self, report: PageAutoReport) -> None:
        # ----- Recover Interrupted Page and Composer Steps -----
        for row in self._flatten_rows():
            result = report.get_result(row.get("task_id", ""))

            page_status = str(result.get("page_status") or "").strip().upper()

            post_status = str(result.get("post_status") or "").strip()

            # ----- Recover Interrupted Page Switch -----
            if page_status == "RUNNING":
                message = "Previous Page switch was interrupted; retry allowed."

                report.upsert_page_result(
                    row,
                    "INTERRUPTED",
                    attempt=result.get("page_attempt_count") or 0,
                    error=message,
                    retryable=True,
                )

                report.log_event(
                    row,
                    self.run_id,
                    "page:switch",
                    "Interrupted",
                    error=RuntimeError(message),
                    retryable=True,
                )

            # ----- Recover Interrupted Composer Preparation -----
            if post_status == "Preparing":
                # No publish submission was recorded.
                message = (
                    "Previous composer preparation was interrupted; " "retry allowed."
                )

                report.upsert_result(
                    row,
                    "Failed",
                    error=message,
                )

                report.log_event(
                    row,
                    self.run_id,
                    "composer:open",
                    "Interrupted",
                    error=RuntimeError(message),
                    retryable=True,
                )

            # ----- Protect Uncertain Publish Outcomes -----
            elif post_status in {"Publishing", "Running", "Submitted"}:
                # Preserve uncertainty from older versions.
                message = "Previous publish outcome is unknown. " "Verify on Facebook."

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
                    error=RuntimeError(message),
                    retryable=False,
                )

    def _restore_result_statuses(
        self,
        targets: list[dict],
        report: PageAutoReport,
    ) -> None:
        # ----- Restore Saved Task Statuses -----
        for target in targets:
            row = target["rows"][0]
            saved = report.get_result(row.get("task_id", ""))

            post_status = str(saved.get("post_status") or "").strip()

            page_status = str(saved.get("page_status") or "").strip().upper()

            current_name = str(target.get("page_name") or "").strip()

            current_link = str(target.get("page_link") or "").strip()

            saved_name = str(saved.get("page_name") or "").strip()

            saved_link = str(saved.get("page_link") or "").strip()

            page_changed = current_name != saved_name or current_link != saved_link

            target["_skip_page_task"] = False
            target["_saved_page_status"] = page_status
            target["_saved_post_status"] = post_status
            target["_capture_url_only"] = False
            target["_comment_only"] = False
            target["_verify_comment_only"] = False

            # ----- Recheck a Previously Submitted Comment Without Sending Again -----
            # The previous run has crossed the irreversible Send boundary.
            # A read-only verification can clear the warning safely.
            saved_error = str(saved.get("error") or "")
            if (
                post_status == "Published"
                and saved_error.startswith(
                    "Post published; Comment outcome requires verification: "
                )
                and str(row.get("comment") or "").strip()
                and str(saved.get("post_url") or "").strip()
                and page_status == "SUCCESS"
                and not page_changed
            ):
                target["_verify_comment_only"] = True
                self._emit_rows(target["rows"], "Queued")
                continue

            # ----- Resume Only Retryable Comment Preparation -----
            # Only this exact prefix is written before the send boundary.
            saved_error = str(saved.get("error") or "")
            # This precise legacy error was raised before any Comment Send.
            # Resume Comment only; never submit the already published post.
            legacy_unsent_draft = saved_error.strip() == (
                "Post published; Comment not sent: "
                "Comment draft changed before sending; nothing was sent."
            )
            if (
                post_status == "Published"
                and (
                    saved_error.startswith(
                        "Post published; Comment not sent (retryable): "
                    )
                    or legacy_unsent_draft
                )
                and str(row.get("comment") or "").strip()
                and str(saved.get("post_url") or "").strip()
                and page_status == "SUCCESS"
                and not page_changed
            ):
                target["_comment_only"] = True
                self._emit_rows(target["rows"], "Queued")
                continue

            # ----- Resume Only URL Verification After a Prior URL Failure -----
            # An Unknown publish outcome must not trigger another Publish.
            # Only the URL-capture failure written by _capture_post_url qualifies.
            saved_error = str(saved.get("error") or "")
            if (
                post_status == "Unknown"
                and saved_error.startswith(
                    "Post submission was attempted, but its URL is unverified."
                )
                and page_status == "SUCCESS"
                and not page_changed
            ):
                target["_capture_url_only"] = True
                self._emit_rows(target["rows"], "Queued")
                continue

            # ----- Never Resubmit Published or Uncertain Posts -----
            if post_status in {
                "Published",
                "Unknown",
            }:
                target["_skip_page_task"] = True

                self._emit_rows(
                    target["rows"],
                    ("Done" if post_status == "Published" else post_status),
                    (str(saved.get("error") or "") if post_status == "Unknown" else ""),
                )

                continue

            # ----- Continue Prepared Posts to Publish -----
            # PostPrepared is not a submitted or published result.

            # ----- Reset Page Status When Target Changes -----
            if page_changed and page_status in {
                "SUCCESS",
                "FAILED",
                "INTERRUPTED",
            }:
                report.upsert_page_result(
                    row,
                    "PENDING",
                    attempt=0,
                    error="",
                    retryable=True,
                )

                report.log_event(
                    row,
                    self.run_id,
                    "page:target_changed",
                    "Pending",
                    retryable=True,
                )

                target["_saved_page_status"] = "PENDING"

            # ----- Continue Old Composer Tasks to Media and Caption -----
            # A ComposerOpened result is not a completed Facebook Post.
            # A PostPrepared result is invalid if the Page changed.
            if post_status == "ComposerOpened" or (
                post_status == "PostPrepared"
                and (page_changed or page_status != "SUCCESS")
            ):
                report.upsert_result(
                    row,
                    "Pending",
                    error="",
                )

                target["_saved_post_status"] = "Pending"

            # ----- Requeue Failed and Incomplete Tasks -----
            self._emit_rows(
                target["rows"],
                "Queued",
            )

    def run(self):
        _cmd_separator()
        cmd_log("INFO", "Starting Page Auto")

        sessions: dict[str, dict] = {}
        profiles_pending_close: set[tuple[str, str]] = set()
        report = None
        targets: list[dict] = []

        passed = 0
        failed = 0
        stopped = 0

        order_totals: dict[str, int] = {}
        order_stats: dict[str, dict[str, int]] = {}
        order_positions: dict[str, int] = {}

        started_orders: set[str] = set()
        completed_orders: set[str] = set()
        finished_orders: set[str] = set()

        last_active_order: str | None = None
        run_summary = None
        run_failed = False
        resume_wait = None
        skipped_success = 0
        skipped_failed = 0

        try:
            targets = self._collect_targets()

            if self.stop_requested:
                for target in targets:
                    self._emit_rows(
                        target["rows"],
                        "Stopped",
                        "Stopped by user.",
                    )
                    stopped += len(target["rows"])
                return

            if not targets:
                raise RuntimeError(
                    "No Page link targets found. Check the imported Excel jobs."
                )

            report = PageAutoReport()
            self._recover_interrupted_rows(report)
            self._restore_result_statuses(targets, report)

            all_targets = list(targets)
            skipped_success = sum(
                target.get("_skip_page_task")
                and target.get("_saved_post_status") == "Published"
                for target in all_targets
            )
            skipped_failed = sum(
                target.get("_skip_page_task")
                and target.get("_saved_post_status") == "Unknown"
                for target in all_targets
            )
            targets = [
                target for target in all_targets if not target.get("_skip_page_task")
            ]

            if not targets:
                if skipped_failed:
                    cmd_log(
                        "INFO",
                        f"No safe pending tasks. {skipped_failed} "
                        "Unknown publish outcome(s) require manual verification.",
                    )
                else:
                    cmd_log(
                        "INFO",
                        "No pending tasks. All Page tasks are already successful.",
                    )

                run_summary = {
                    "total": 0,
                    "success": 0,
                    "failed": 0,
                    "post_orders": 0,
                    "skipped_success": skipped_success,
                    "skipped_failed": skipped_failed,
                }
                return

            self._configure_adspower()

            # ----- Restore an interrupted delay, if one exists -----
            saved_state = report.get_state()
            saved_wait_type = str(saved_state.get("wait_type") or "").strip().upper()
            saved_resume_key = str(saved_state.get("resume_target_key") or "").strip()
            saved_deadline = self._parse_deadline(saved_state.get("wait_deadline"))

            if (
                saved_wait_type in {"PAGE", "ORDER"}
                and saved_resume_key
                and saved_deadline is not None
            ):
                resume_index = next(
                    (
                        index
                        for index, item in enumerate(targets)
                        if item.get("target_key") == saved_resume_key
                    ),
                    None,
                )
                all_resume_index = next(
                    (
                        index
                        for index, item in enumerate(all_targets)
                        if item.get("target_key") == saved_resume_key
                    ),
                    None,
                )

                if resume_index is not None and all_resume_index is not None:
                    resume_target = targets[resume_index]
                    saved_before_order = str(
                        saved_state.get("wait_before_order") or ""
                    ).strip()
                    saved_after_order = str(
                        saved_state.get("wait_after_order") or ""
                    ).strip()
                    saved_after_key = str(
                        saved_state.get("wait_after_target_key") or ""
                    ).strip()
                    current_order = str(resume_target.get("post_order") or "").strip()
                    previous_target_matches = (
                        all_resume_index > 0
                        and bool(saved_after_key)
                        and all_targets[all_resume_index - 1].get("target_key")
                        == saved_after_key
                    )
                    order_transition_matches = (
                        saved_wait_type == "PAGE"
                        and (
                            not saved_after_order or saved_after_order == current_order
                        )
                    ) or (
                        saved_wait_type == "ORDER"
                        and (
                            not saved_after_order or saved_after_order != current_order
                        )
                    )

                    pending_before_resume = any(
                        item.get("target_key")
                        in {pending.get("target_key") for pending in targets}
                        for item in all_targets[:all_resume_index]
                    )
                    if (
                        not pending_before_resume
                        and previous_target_matches
                        and order_transition_matches
                        and (
                            not saved_before_order
                            or saved_before_order == current_order
                        )
                    ):
                        targets = targets[resume_index:]
                        resume_wait = {
                            "wait_type": saved_wait_type,
                            "deadline": saved_deadline,
                        }
                        cmd_log(
                            "INFO",
                            f"Resuming interrupted {saved_wait_type.lower()} delay",
                        )

            if resume_wait is None:
                self._clear_wait_state(report, run_status="RUNNING")
            else:
                report.set_state({"run_status": "WAITING"})

            cmd_log(
                "INFO",
                f"Collected target sequence: {len(targets)} targets",
            )

            total_data_rows = len(self._flatten_rows())
            unique_page_count = len(
                {
                    str(row.get("page_id") or "").strip()
                    for row in self._flatten_rows()
                    if str(row.get("page_id") or "").strip()
                }
            )

            cmd_log(
                "INFO",
                f"Total data: {total_data_rows} rows • "
                f"{unique_page_count} page targets",
            )
            _cmd_separator()

            for target in targets:
                order_key = str(target.get("post_order") or "").strip() or "unknown"

                order_totals[order_key] = order_totals.get(order_key, 0) + 1

                order_stats.setdefault(
                    order_key,
                    {"success": 0, "failed": 0, "stopped": 0},
                )

                order_positions.setdefault(order_key, 0)

            page_delay_seconds = self._get_page_delay_minutes() * 60
            order_delay_seconds = self._get_order_delay_minutes() * 60

            remaining_by_order_profile: dict[tuple[str, str], int] = {}

            for item in targets:
                uid = str(item.get("profile_uid") or "").strip()
                order = str(item.get("post_order") or "").strip() or "unknown"

                if uid:
                    key = (order, uid)
                    remaining_by_order_profile[key] = (
                        remaining_by_order_profile.get(key, 0) + 1
                    )

            targets_to_process = targets

            if resume_wait is not None:
                can_continue = self._wait_until_deadline(
                    deadline=resume_wait["deadline"],
                    wait_type=resume_wait["wait_type"],
                    report=report,
                )

                if can_continue:
                    self._clear_wait_state(report, run_status="RUNNING")
                else:
                    for pending in targets:
                        self._emit_rows(
                            pending["rows"],
                            "Stopped",
                            "Stopped by user.",
                        )
                    stopped += len(targets)
                    targets_to_process = []

            for index, target in enumerate(targets_to_process):
                current_order = str(target.get("post_order") or "").strip() or "unknown"

                if index > 0:
                    previous_order = (
                        str(
                            targets_to_process[index - 1].get("post_order") or ""
                        ).strip()
                        or "unknown"
                    )

                    if previous_order != current_order:
                        self._finish_order(
                            previous_order,
                            order_stats,
                            order_totals,
                            completed_orders,
                            finished_orders,
                        )

                        if previous_order in completed_orders:
                            self._save_last_completed_order(report, previous_order)

                        cmd_log("INFO", "Preparing next Post Order...")
                        _cmd_separator()

                        can_continue = self._wait_between_orders(
                            delay_seconds=order_delay_seconds,
                            report=report,
                            previous_target=targets_to_process[index - 1],
                            next_target=target,
                        )
                    else:
                        can_continue = self._wait_between_pages(
                            delay_seconds=page_delay_seconds,
                            report=report,
                            previous_target=targets_to_process[index - 1],
                            next_target=target,
                        )

                    if not can_continue:
                        remaining = targets_to_process[index:]

                        for pending in remaining:
                            self._emit_rows(
                                pending["rows"],
                                "Stopped",
                                "Stopped by user.",
                            )

                            pending_order = (
                                str(pending.get("post_order") or "").strip()
                                or "unknown"
                            )

                            order_stats.setdefault(
                                pending_order,
                                {
                                    "success": 0,
                                    "failed": 0,
                                    "stopped": 0,
                                },
                            )
                            order_stats[pending_order]["stopped"] += 1

                        stopped += len(remaining)
                        break

                if self.stop_requested:
                    remaining = targets_to_process[index:]

                    for pending in remaining:
                        self._emit_rows(
                            pending["rows"],
                            "Stopped",
                            "Stopped by user.",
                        )

                        pending_order = (
                            str(pending.get("post_order") or "").strip() or "unknown"
                        )

                        order_stats.setdefault(
                            pending_order,
                            {
                                "success": 0,
                                "failed": 0,
                                "stopped": 0,
                            },
                        )
                        order_stats[pending_order]["stopped"] += 1

                    stopped += len(remaining)
                    break

                if current_order not in started_orders:
                    cmd_log(
                        "INFO",
                        f"POST ORDER {current_order} STARTED",
                    )
                    started_orders.add(current_order)

                last_active_order = current_order

                target["order_position"] = order_positions[current_order] + 1
                target["order_total"] = order_totals[current_order]

                profile_uid = str(target.get("profile_uid") or "").strip()

                order_profile_key = (current_order, profile_uid)

                if profile_uid:
                    profiles_pending_close.add(order_profile_key)

                outcome = "failed"
                self._emit_rows(target["rows"], "Running")

                try:
                    if not target.get("page_link") or not profile_uid:
                        outcome = self._process_target(
                            target,
                            report,
                            driver=None,
                            sessions=sessions,
                        )

                    else:
                        profile_name = str(
                            target.get("profile_name")
                            or target.get("profile_id")
                            or profile_uid
                        ).strip()

                        _cmd_separator()

                        previous_session = sessions.get(profile_uid)

                        try:
                            session = self._ensure_profile_session(
                                profile_uid,
                                target["rows"][0],
                                report,
                                sessions,
                            )

                        except Exception as error:
                            message = str(error)
                            is_retryable = bool(getattr(error, "retryable", False))

                            self._log_target_failure(
                                target,
                                message,
                                action="open AdsPower profile",
                            )

                            report.upsert_page_result(
                                target["rows"][0],
                                "FAILED",
                                attempt=0,
                                error=message,
                                retryable=is_retryable,
                            )

                            self._emit_rows(
                                target["rows"],
                                "Error",
                                message,
                            )

                            session = None

                        if session is not None:
                            if (
                                previous_session is not None
                                and session is previous_session
                            ):
                                profile_action = "Reusing"
                            else:
                                profile_action = "Connected to"

                            # ----- Compact Progress Log (No Profile UID) -----
                            page_code = str(
                                target.get("page_id") or "Unknown Page"
                            ).strip()
                            via_code = str(
                                target["rows"][0].get("via_id") or "Unknown Via"
                            ).strip()
                            cmd_log(
                                "INFO",
                                f"[{target['order_position']}/"
                                f"{target['order_total']}] "
                                f"Processing {page_code} | {via_code}",
                            )

                            session["last_row"] = target["rows"][0]

                            page_label = (
                                target.get("page_name")
                                or target.get("page_id")
                                or "Unknown Page"
                            )
                            cmd_log("INFO", "Switching to Facebook Page...")

                            outcome = self._process_target(
                                target,
                                report,
                                driver=session["driver"],
                                sessions=sessions,
                            )

                finally:
                    if order_profile_key in remaining_by_order_profile:
                        remaining_by_order_profile[order_profile_key] -= 1

                        if remaining_by_order_profile[order_profile_key] <= 0:
                            # Keep the final Post visible briefly after a
                            # successfully verified Comment before stopping AdsPower.
                            if sessions.get(profile_uid) is not None:
                                self._wait_after_comment_before_profile_close(target)
                            session_to_close = sessions.pop(
                                profile_uid,
                                None,
                            )

                            if session_to_close is not None:
                                self._close_profile_sessions(
                                    {profile_uid: session_to_close},
                                    report,
                                )

                            else:
                                # ----- Recover an Open Browser Without Selenium -----
                                profile_name = str(
                                    target.get("profile_name")
                                    or target.get("profile_id")
                                    or ""
                                ).strip()
                                if not profile_name or profile_name == profile_uid:
                                    profile_name = "Unnamed profile"
                                try:
                                    if get_active_profile(profile_uid):
                                        stop_profile(profile_uid)
                                        cmd_log(
                                            "INFO",
                                            f"Closed AdsPower profile: {profile_name}",
                                        )
                                except Exception as error:
                                    reason = str(error).replace(profile_uid, "[hidden]")
                                    cmd_log(
                                        "WARNING",
                                        f"Cannot verify AdsPower profile closure: "
                                        f"{profile_name}. Reason: {reason}",
                                    )

                            profiles_pending_close.discard(order_profile_key)

                stats = order_stats[current_order]

                if outcome == "passed":
                    passed += 1
                    stats["success"] += 1

                elif outcome == "stopped":
                    stopped += 1
                    stats["stopped"] += 1

                else:
                    failed += 1
                    stats["failed"] += 1

                order_positions[current_order] += 1

            if last_active_order is not None:
                self._finish_order(
                    last_active_order,
                    order_stats,
                    order_totals,
                    completed_orders,
                    finished_orders,
                )

                if last_active_order in completed_orders:
                    self._save_last_completed_order(report, last_active_order)

            if (
                passed + failed == len(targets_to_process)
                and stopped == 0
                and not self.stop_requested
            ):
                run_summary = {
                    "total": len(targets_to_process),
                    "success": passed,
                    "failed": failed,
                    "post_orders": len(completed_orders),
                    "skipped_success": skipped_success,
                    "skipped_failed": skipped_failed,
                }

        except Exception as error:
            run_failed = True
            message = f"Page Auto failed: {error}"
            cmd_log("ERROR", message)
            self.error.emit(message)

        finally:
            if report is not None:
                try:
                    if run_summary is not None:
                        has_errors = bool(
                            run_summary.get("failed")
                            or run_summary.get("skipped_failed")
                        )
                        completion_status = (
                            "COMPLETED_WITH_ERRORS" if has_errors else "COMPLETED"
                        )
                        self._clear_wait_state(report, run_status=completion_status)
                    elif self.stop_requested:
                        # Keep an active delay's deadline and resume target intact.
                        report.set_state({"run_status": "STOPPED"})
                    elif run_failed:
                        report.set_state({"run_status": "FAILED"})
                except Exception as state_error:
                    cmd_log(
                        "ERROR",
                        f"Could not update Page Auto run state: {state_error}",
                    )

            session_uids = set(sessions)
            self._close_profile_sessions(sessions, report)

            # ----- Stop Any Browser Opened Before Selenium Could Attach -----
            for _order, profile_uid in sorted(profiles_pending_close):
                if not profile_uid or profile_uid in session_uids:
                    continue
                try:
                    active = get_active_profile(profile_uid)
                    if active:
                        stop_profile(profile_uid)
                        cmd_log(
                            "INFO", "Closed AdsPower profile after session recovery."
                        )
                except Exception as error:
                    reason = str(error).replace(profile_uid, "[hidden]")
                    cmd_log(
                        "WARNING",
                        f"Cannot confirm AdsPower profile shutdown: {reason}",
                    )

            if run_summary is not None:
                cmd_log("INFO", "PAGE AUTO COMPLETED")
                cmd_log(
                    "INFO",
                    f"Total: {run_summary['total']} | "
                    f"Success: {run_summary['success']} | "
                    f"Failed: {run_summary['failed']}",
                )
                if run_summary.get("skipped_success") or run_summary.get(
                    "skipped_failed"
                ):
                    cmd_log(
                        "INFO",
                        "Skipped: "
                        f"{run_summary.get('skipped_success', 0)} successful | "
                        f"{run_summary.get('skipped_failed', 0)} unknown outcomes",
                    )

                report_path = (
                    getattr(report, "result_path", None) if report is not None else None
                )

                try:
                    if report_path is not None and report_path.is_file():
                        cmd_log("SUCCESS", "Report saved successfully")
                except Exception:
                    pass

                _cmd_separator()
                self.run_completed.emit(run_summary)

            elif self.stop_requested:
                cmd_log("INFO", "PAGE AUTO STOPPED")
                cmd_log(
                    "INFO",
                    f"Total: {passed + failed} | "
                    f"Success: {passed} | "
                    f"Failed: {failed} | "
                    f"Stopped: {stopped}",
                )
                _cmd_separator()

    def _finish_order(
        self,
        order_key: str,
        order_stats: dict[str, dict[str, int]],
        order_totals: dict[str, int],
        completed_orders: set[str],
        finished_orders: set[str],
    ) -> None:
        if not order_key or order_key in finished_orders:
            return

        stats = order_stats.get(
            order_key,
            {"success": 0, "failed": 0, "stopped": 0},
        )

        total = int(order_totals.get(order_key, 0))
        success = int(stats.get("success", 0))
        failed = int(stats.get("failed", 0))
        stopped = int(stats.get("stopped", 0))

        processed = success + failed

        is_complete = total > 0 and processed >= total and stopped == 0

        finished_orders.add(order_key)

        if is_complete:
            completed_orders.add(order_key)

            _cmd_separator()
            cmd_log("INFO", f"POST ORDER {order_key} COMPLETED")
            cmd_log(
                "INFO",
                f"Processed: {processed} | "
                f"Success: {success} | "
                f"Failed: {failed}",
            )

            self.order_completed.emit(
                {
                    "post_order": order_key,
                    "total": total,
                    "processed": processed,
                    "success": success,
                    "failed": failed,
                    "stopped": stopped,
                }
            )

        else:
            state = "STOPPED" if self.stop_requested or stopped > 0 else "INCOMPLETE"

            cmd_log("INFO", f"POST ORDER {order_key} {state}")
            cmd_log(
                "INFO",
                f"Processed: {processed}/{total} | "
                f"Success: {success} | "
                f"Failed: {failed} | "
                f"Stopped: {stopped}",
            )

        _cmd_separator()

    @staticmethod
    def _get_saved_delay_minutes(
        setting_key: str,
        config_name: str,
        default_value: float,
    ) -> float:
        settings = QSettings(
            QSettings.Format.IniFormat,
            QSettings.Scope.UserScope,
            "AutoPostTool",
            "AutoPostTool",
        )
        raw_value = settings.value(
            setting_key,
            getattr(automation_config, config_name, default_value),
        )

        try:
            delay_minutes = float(raw_value)
        except (TypeError, ValueError) as error:
            raise RuntimeError(f"{setting_key} must be a number of minutes.") from error

        if not math.isfinite(delay_minutes) or not 0 <= delay_minutes <= 10080:
            raise RuntimeError(f"{setting_key} must be between 0 and 10080 minutes.")

        return delay_minutes

    @staticmethod
    def _get_page_delay_minutes() -> float:
        """Read the saved delay between Pages, falling back to automation.py."""
        return PageAutoWorker._get_saved_delay_minutes(
            "page_auto/post_delay_minutes",
            "PAGE_AUTO_POST_DELAY",
            0,
        )

    @staticmethod
    def _get_order_delay_minutes() -> float:
        """Read the saved delay between post_order groups."""
        return PageAutoWorker._get_saved_delay_minutes(
            "page_auto/order_delay_minutes",
            "PAGE_AUTO_ORDER_DELAY",
            150,
        )

    def _wait_between_pages(
        self,
        delay_seconds: float,
        report: PageAutoReport,
        previous_target: dict,
        next_target: dict,
    ) -> bool:
        return self._wait_for_transition(
            wait_type="PAGE",
            delay_seconds=delay_seconds,
            report=report,
            previous_target=previous_target,
            next_target=next_target,
        )

    def _wait_interruptibly(self, delay_seconds: float) -> bool:
        deadline = time.monotonic() + max(0.0, float(delay_seconds))
        while not self.stop_requested:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return True
            time.sleep(min(0.25, remaining))
        return False

    def _wait_between_orders(
        self,
        delay_seconds: float,
        report: PageAutoReport,
        previous_target: dict,
        next_target: dict,
    ) -> bool:
        return self._wait_for_transition(
            wait_type="ORDER",
            delay_seconds=delay_seconds,
            report=report,
            previous_target=previous_target,
            next_target=next_target,
        )

    def _wait_for_transition(
        self,
        wait_type: str,
        delay_seconds: float,
        report: PageAutoReport,
        previous_target: dict,
        next_target: dict,
    ) -> bool:
        if self.stop_requested:
            return False

        if delay_seconds <= 0:
            self._clear_wait_state(report, run_status="RUNNING")
            return True

        deadline = datetime.now().astimezone() + timedelta(seconds=float(delay_seconds))
        deadline_text = deadline.isoformat()
        previous_order = str(previous_target.get("post_order") or "").strip()
        next_order = str(next_target.get("post_order") or "").strip()

        state = {
            "run_status": "WAITING",
            "wait_type": wait_type,
            "wait_deadline": deadline_text,
            "resume_target_key": next_target["target_key"],
            "wait_after_target_key": previous_target["target_key"],
            "wait_before_target_key": next_target["target_key"],
            "wait_after_order": previous_order,
            "wait_before_order": next_order,
            "next_page_at": deadline_text if wait_type == "PAGE" else None,
            "next_order_at": deadline_text if wait_type == "ORDER" else None,
        }

        if wait_type == "ORDER":
            completed_order = self._order_state_value(previous_order)
            if completed_order is not None:
                state["last_completed_order"] = completed_order

        report.set_state(state)
        return self._wait_until_deadline(
            deadline=deadline,
            wait_type=wait_type,
            report=report,
        )

    def _wait_until_deadline(
        self,
        deadline: datetime,
        wait_type: str,
        report: PageAutoReport,
    ) -> bool:
        report.set_state({"run_status": "WAITING"})

        while not self.stop_requested:
            remaining = (deadline - datetime.now().astimezone()).total_seconds()
            if remaining <= 0:
                break
            time.sleep(min(0.5, remaining))

        if self.stop_requested:
            # Keep the original absolute deadline for the next Run.
            report.set_state({"run_status": "STOPPED"})
            cmd_log(
                "INFO",
                f"Stopped during {wait_type.lower()} delay; remaining time saved",
            )
            return False

        self._clear_wait_state(report, run_status="RUNNING")
        return True

    @staticmethod
    def _parse_deadline(value) -> datetime | None:
        if not value:
            return None

        try:
            deadline = datetime.fromisoformat(str(value))
        except (TypeError, ValueError):
            return None

        if deadline.tzinfo is None:
            return deadline.astimezone()
        return deadline.astimezone()

    @staticmethod
    def _order_state_value(order_key: str):
        try:
            return int(float(order_key))
        except (TypeError, ValueError):
            return None

    def _save_last_completed_order(
        self,
        report: PageAutoReport,
        order_key: str,
    ) -> None:
        completed_order = self._order_state_value(order_key)
        if completed_order is not None:
            report.set_state({"last_completed_order": completed_order})

    @staticmethod
    def _clear_wait_state(report: PageAutoReport, run_status: str) -> None:
        report.set_state(
            {
                "run_status": run_status,
                "wait_type": "",
                "wait_deadline": None,
                "resume_target_key": "",
                "wait_after_target_key": "",
                "wait_before_target_key": "",
                "wait_after_order": "",
                "wait_before_order": "",
                "next_page_at": None,
                "next_order_at": None,
            }
        )

    def _configure_adspower(self):
        settings = QSettings(
            QSettings.Format.IniFormat,
            QSettings.Scope.UserScope,
            "AutoPostTool",
            "AutoPostTool",
        )

        api_key = str(settings.value("adspower/api_key", "") or "").strip()

        local_api = str(
            settings.value(
                "adspower/local_api",
                ADSPOWER_DEFAULT_URL,
            )
            or ADSPOWER_DEFAULT_URL
        ).strip()

        if not api_key:
            raise RuntimeError(
                "AdsPower API key is missing. Connect AdsPower in Settings first."
            )

        set_credentials(api_key, api_url=local_api)
        cmd_log("INFO", "AdsPower API credentials configured")

    def _flatten_rows(self) -> list[dict]:
        rows = []

        for job in self.jobs:
            if not isinstance(job, dict):
                continue

            job_rows = job.get("rows")

            if isinstance(job_rows, list):
                rows.extend(row for row in job_rows if isinstance(row, dict))
            else:
                rows.append(job)

        return rows

    def _collect_targets(self) -> list[dict]:
        targets = []

        for index, source_row in enumerate(self._flatten_rows(), start=1):
            row = source_row
            task_key = str(row.get("task_id") or row.get("_task_id") or "").strip()

            if not task_key:
                task_key = "|".join(
                    (
                        str(row.get("post_id") or "").strip(),
                        str(
                            row.get("profile_id") or row.get("profile_uid") or ""
                        ).strip(),
                        str(row.get("via_id") or "").strip(),
                        str(row.get("page_id") or "").strip(),
                    )
                )

            if not task_key.strip("|"):
                excel_row = row.get("_excel_row") or index
                raise ValueError(
                    f"Could not build a stable task_id for Excel row {excel_row}."
                )

            row["task_id"] = task_key

            targets.append(
                {
                    "row_number": index,
                    "target_key": task_key,
                    "profile_uid": str(row.get("profile_uid") or "").strip(),
                    "profile_id": str(row.get("profile_id") or "").strip(),
                    "profile_name": str(row.get("profile_name") or "").strip(),
                    "post_order": str(row.get("post_order") or "").strip(),
                    "page_id": str(row.get("page_id") or "").strip(),
                    "page_link": str(row.get("page_link") or "").strip(),
                    "page_name": str(
                        row.get("page_name") or row.get("page") or ""
                    ).strip(),
                    "rows": [row],
                }
            )

        return targets

    @staticmethod
    def _driver_is_usable(driver) -> bool:
        if driver is None:
            return False

        try:
            if not driver.window_handles:
                return False
            return driver.execute_script("return 1") == 1
        except Exception:
            return False

    @staticmethod
    def _normalize_debugger_address(address: str) -> tuple[str, int] | None:
        value = str(address or "").strip()
        if not value:
            return None

        parsed = urlsplit(value if "://" in value else f"//{value}")
        host = str(parsed.hostname or "").strip().lower()
        port = parsed.port
        if not host or port is None:
            return None
        if host in {"localhost", "::1"}:
            host = "127.0.0.1"
        return host, port

    @classmethod
    def _driver_matches_profile(cls, driver, profile_data: dict) -> bool:
        """Check that a live Selenium session is attached to this profile endpoint."""
        expected_address = get_profile_debugger_address(profile_data)
        capabilities = getattr(driver, "capabilities", {}) or {}
        chrome_options = capabilities.get("goog:chromeOptions") or {}
        actual_address = str(chrome_options.get("debuggerAddress") or "").strip()

        # Some older ChromeDriver builds omit debuggerAddress from capabilities.
        # In that case, use the live-session checks rather than rejecting it.
        if not actual_address:
            return cls._driver_is_usable(driver)

        expected = cls._normalize_debugger_address(expected_address)
        actual = cls._normalize_debugger_address(actual_address)
        if expected is None or actual is None:
            return cls._driver_is_usable(driver)
        return expected == actual

    @staticmethod
    def _driver_debugger_address(driver) -> str:
        capabilities = getattr(driver, "capabilities", {}) or {}
        chrome_options = capabilities.get("goog:chromeOptions") or {}
        return str(chrome_options.get("debuggerAddress") or "unknown").strip()

    @staticmethod
    def _detach_stale_driver(profile_uid: str, driver) -> None:
        if driver is None:
            return

        try:
            driver.service.stop()
        except Exception as error:
            cmd_log(
                "WARNING",
                "Could not detach stale Selenium driver for AdsPower profile.",
            )

    def _ensure_profile_session(
        self,
        profile_uid: str,
        row: dict,
        report: PageAutoReport,
        sessions: dict[str, dict],
    ) -> dict:
        session = sessions.get(profile_uid)

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
