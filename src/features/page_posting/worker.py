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
    check_connection,
    check_profiles,
    connect_driver,
    get_active_profile,
    get_profile_debugger_address,
    start_profile,
    stop_profile,
)
from src.features.page_posting.excel import (
    get_data_file_stamp,
    load_page_rows,
)
from src.features.page_posting.facebook import (
    FacebookPostError,
    FacebookSwitchError,
    PublishUnknownError,
    click_published_post_timestamp,
    comment_exists_on_opened_post,
    get_opened_post_url,
    open_and_verify_post_url,
    post_comment_on_opened_post,
    publish_photo,
    switch_to_page,
)
from src.features.page_posting.service import (
    build_page_jobs,
    flatten_page_jobs,
)
from src.features.page_posting.report import PageAutoReport
from src.features.page_posting import validation

from src.utils.cmd_log import cmd_log

# ----- Retry Settings -----
MAX_OPEN_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 2
MAX_STAGE_ATTEMPTS = 3
STAGE_RETRY_DELAY_SECONDS = 2


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
                    f"Page Auto media validation: {len(media_errors)} row(s) have media errors.",
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
            check_connection(self.api_key, api_url=local_api)
            cmd_log("SUCCESS", f"AdsPower API connected: {local_api}")

            if self.stop_requested:
                return

            time.sleep(1.2)

            if self.stop_requested:
                return

            checked_profiles = check_profiles(self.profile_uids)
            cmd_log("SUCCESS", f"AdsPower profiles verified: {len(checked_profiles)}")

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
        for row in self._flatten_rows():
            result = report.get_result(row.get("task_id", ""))
            status = str(result.get("post_status") or "").strip()

            if status in {"Running", "PublishSubmitting"}:
                message = (
                    "Previous run ended after the publish action may have started. "
                    "The Page must be checked before any new publish attempt."
                )
                report.upsert_result(
                    row,
                    "PublishUnknown",
                    published_at=result.get("published_at"),
                    post_url=result.get("post_url", ""),
                    error=message,
                )
                report.log_event(
                    row,
                    self.run_id,
                    f"publish:{row.get('post_id', '')}",
                    "Unknown",
                    attempt=max(1, report.next_attempt(row) - 1),
                    error=RuntimeError(message),
                    retryable=False,
                )
                self._emit_rows([row], "Unknown", message)

            elif status == "CommentSending":
                message = (
                    "Previous run ended while sending the comment. "
                    "The existing comment will be checked before retrying."
                )
                report.upsert_result(
                    row,
                    "CommentUnknown",
                    published_at=result.get("published_at"),
                    post_url=result.get("post_url", ""),
                    error=message,
                )
                report.log_event(
                    row,
                    self.run_id,
                    f"comment:{row.get('post_id', '')}",
                    "Unknown",
                    attempt=max(1, report.next_attempt(row) - 1),
                    error=RuntimeError(message),
                    retryable=True,
                )
                self._emit_rows([row], "Unknown", message)

    def _restore_result_statuses(
        self,
        targets: list[dict],
        report: PageAutoReport,
    ) -> None:
        for target in targets:
            row = target["rows"][0]
            result = report.get_result(row.get("task_id", ""))
            status = str(result.get("post_status") or "").strip()

            if status == "Completed":
                target["_saved_result_status"] = "Completed"
                self._emit_rows([row], "Done", result.get("error", ""))

            elif status in {"Unknown", "PublishUnknown", "CommentUnknown"}:
                # These statuses must be reconciled; they are never auto-marked Done.
                target["_saved_result_status"] = ""
                self._emit_rows([row], "Unknown", result.get("error", ""))

            else:
                target["_saved_result_status"] = ""
                self._emit_rows([row], "Queued")

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

            self._configure_adspower()
            report = PageAutoReport()
            self._recover_interrupted_rows(report)
            self._restore_result_statuses(targets, report)

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

                if resume_index is not None:
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
                        resume_index > 0
                        and bool(saved_after_key)
                        and targets[resume_index - 1].get("target_key")
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

                    if (
                        previous_target_matches
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
                if item.get("_saved_result_status") == "Completed":
                    continue

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

                saved_status = target.get("_saved_result_status")
                if saved_status == "Completed":
                    passed += 1
                    order_stats[current_order]["success"] += 1
                    order_positions[current_order] += 1
                    continue

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

                            self._log_target_failure(
                                target,
                                message,
                                action="open AdsPower profile",
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

                            cmd_log(
                                "INFO",
                                f"[{target['order_position']}/"
                                f"{target['order_total']}] "
                                f"{profile_action} AdsPower profile: "
                                f"{profile_name}",
                            )

                            session["last_row"] = target["rows"][0]

                            cmd_log(
                                "INFO",
                                "Switching to Facebook Page: "
                                f"{target.get('page_name') or target.get('page_id') or 'Unknown Page'}",
                            )

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
                                try:
                                    active_profile = get_active_profile(profile_uid)

                                except Exception as check_error:
                                    cmd_log(
                                        "WARNING",
                                        f"Could not check AdsPower profile "
                                        f"{profile_uid}: {check_error}",
                                    )

                                else:
                                    if active_profile:
                                        try:
                                            stop_profile(profile_uid)

                                        except Exception as close_error:
                                            cmd_log(
                                                "ERROR",
                                                f"Could not stop AdsPower profile "
                                                f"{profile_uid}: {close_error}",
                                            )

                                            if report is not None:
                                                try:
                                                    report.log_event(
                                                        target["rows"][0],
                                                        self.run_id,
                                                        "profile:stop",
                                                        "Failed",
                                                        error=close_error,
                                                        retryable=False,
                                                    )
                                                except Exception:
                                                    pass

                                        else:
                                            if report is not None:
                                                try:
                                                    report.log_event(
                                                        target["rows"][0],
                                                        self.run_id,
                                                        "profile:stop",
                                                        "Stopped",
                                                    )
                                                except Exception:
                                                    pass

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
                        self._clear_wait_state(report, run_status="COMPLETED")
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

            for _order, profile_uid in sorted(profiles_pending_close):
                if not profile_uid or profile_uid in session_uids:
                    continue

                try:
                    active_profile = get_active_profile(profile_uid)

                except Exception as check_error:
                    cmd_log(
                        "WARNING",
                        f"Could not check AdsPower profile "
                        f"{profile_uid} during cleanup: {check_error}",
                    )
                    continue

                if not active_profile:
                    continue

                try:
                    stop_profile(profile_uid)

                except Exception as close_error:
                    cmd_log(
                        "ERROR",
                        f"Could not stop AdsPower profile "
                        f"{profile_uid} during cleanup: {close_error}",
                    )

            if run_summary is not None:
                cmd_log("INFO", "PAGE AUTO COMPLETED")
                cmd_log(
                    "INFO",
                    f"Total: {run_summary['total']} | "
                    f"Success: {run_summary['success']} | "
                    f"Failed: {run_summary['failed']}",
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
                "AdsPower API key is missing. " "Connect AdsPower in Settings first."
            )

        check_connection(api_key, api_url=local_api)
        cmd_log("SUCCESS", f"AdsPower API connected: {local_api}")

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

        for index, row in enumerate(self._flatten_rows(), start=1):
            task_key = str(row.get("task_id") or "").strip()
            if not task_key:
                task_key = "|".join(
                    (
                        str(row.get("post_id") or "").strip(),
                        str(row.get("post_order") or "").strip(),
                        str(row.get("profile_uid") or "").strip(),
                        str(row.get("page_id") or "").strip(),
                        str(index),
                    )
                )

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
                f"Could not detach stale Selenium driver for profile "
                f"{profile_uid}: {error}",
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
            active_profile = None
            active_check_error = None

            try:
                active_profile = get_active_profile(profile_uid)
            except Exception as error:
                active_check_error = error

            driver_usable = self._driver_is_usable(driver)
            if active_profile and driver_usable:
                if self._driver_matches_profile(driver, active_profile):
                    return session

                expected = get_profile_debugger_address(active_profile)
                actual = self._driver_debugger_address(driver)
                cmd_log(
                    "WARNING",
                    f"Selenium profile binding mismatch for AdsPower UID {profile_uid}: "
                    f"expected debugger {expected}, connected debugger {actual}. "
                    "Reconnecting to the active profile.",
                )
            elif active_check_error is not None:
                cmd_log(
                    "WARNING",
                    f"Could not verify active AdsPower profile {profile_uid}: "
                    f"{active_check_error}. Reconnecting instead of reusing an "
                    "unverified browser session.",
                )
            else:
                cmd_log(
                    "WARNING",
                    f"AdsPower profile {profile_uid} is not active or its Selenium "
                    "driver is unresponsive. Reopening/reconnecting.",
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
        driver = None
        stage = "profile:check"

        try:
            profile_data = get_active_profile(profile_uid)

            if profile_data:
                report.log_event(
                    row,
                    self.run_id,
                    "profile:reuse",
                    "Active",
                )
            else:
                stage = "profile:start"
                profile_data = start_profile(profile_uid)
                profile_started = True
                report.log_event(
                    row,
                    self.run_id,
                    "profile:start",
                    "Started",
                )

            returned_uid = str(profile_data.get("user_id") or "").strip()
            if returned_uid and returned_uid != profile_uid:
                raise AdsPowerConnectionError(
                    f"AdsPower returned profile UID {returned_uid}, but Page Auto "
                    f"requested {profile_uid}. Check the profile_uid column in Excel."
                )

            stage = "browser:attach"
            driver = connect_driver(profile_data)
            if not self._driver_matches_profile(driver, profile_data):
                raise AdsPowerConnectionError(
                    f"Selenium connected to debugger {self._driver_debugger_address(driver)}, "
                    f"but AdsPower profile {profile_uid} uses "
                    f"{get_profile_debugger_address(profile_data)}."
                )

            cmd_log(
                "INFO",
                f"Selenium attached to AdsPower UID {profile_uid}; debugger: "
                f"{self._driver_debugger_address(driver)}; URL: {driver.current_url}",
            )
            report.log_event(
                row,
                self.run_id,
                "browser:attach",
                "Connected",
            )

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

            if driver is not None:
                try:
                    if profile_started:
                        driver.quit()
                    else:
                        driver.service.stop()
                except Exception as cleanup_error:
                    cmd_log(
                        "WARNING",
                        f"Could not clean up Selenium connection for "
                        f"profile {profile_uid}: {cleanup_error}",
                    )

            if profile_started:
                try:
                    stop_profile(profile_uid)
                except Exception as cleanup_error:
                    cmd_log(
                        "WARNING",
                        f"Could not stop AdsPower profile {profile_uid} "
                        f"after attach failure: {cleanup_error}",
                    )

            raise

    def _close_profile_sessions(
        self,
        sessions: dict[str, dict],
        report: PageAutoReport | None,
    ) -> None:
        for profile_uid, session in list(sessions.items()):
            driver = session.get("driver")
            row = session.get("last_row") or {}
            profile_started = bool(session.get("profile_started"))

            if driver is not None:
                try:
                    if profile_started:
                        driver.quit()
                    else:
                        # Detach our WebDriver connection without closing a profile
                        # that was already open before Page Auto attached to it.
                        driver.service.stop()
                except Exception as error:
                    cmd_log(
                        "WARNING",
                        f"Could not close Selenium connection for profile "
                        f"{profile_uid}: {error}",
                    )
                    try:
                        driver.service.stop()
                    except Exception:
                        pass
                    if report is not None:
                        try:
                            report.log_event(
                                row,
                                self.run_id,
                                "browser:close",
                                "Failed",
                                error=error,
                                retryable=False,
                            )
                        except Exception:
                            pass
                else:
                    if report is not None:
                        try:
                            report.log_event(
                                row,
                                self.run_id,
                                "browser:close",
                                "Closed" if profile_started else "Detached",
                            )
                        except Exception:
                            pass

            if not profile_started:
                cmd_log(
                    "INFO",
                    f"Leaving pre-existing AdsPower profile open: {profile_uid}",
                )
                continue

            try:
                stop_profile(profile_uid)
            except Exception as error:
                cmd_log(
                    "ERROR",
                    f"Could not stop AdsPower profile {profile_uid}: {error}",
                )
                if report is not None:
                    try:
                        report.log_event(
                            row,
                            self.run_id,
                            "profile:stop",
                            "Failed",
                            error=error,
                            retryable=False,
                        )
                    except Exception:
                        pass
            else:
                if report is not None:
                    try:
                        report.log_event(
                            row,
                            self.run_id,
                            "profile:stop",
                            "Stopped",
                        )
                    except Exception:
                        pass

    def _log_target_failure(
        self,
        target: dict,
        reason: str,
        action: str = "switch to Facebook Page",
    ) -> None:
        cmd_log("ERROR", f"Failed to {action}")
        cmd_log("ERROR", f"Reason: {reason}")
        cmd_log("INFO", "Skipping current Page")

    def _process_target(
        self,
        target: dict,
        report: PageAutoReport,
        driver=None,
        sessions: dict[str, dict] | None = None,
    ) -> str:
        rows = target["rows"]
        row = rows[0]

        profile_uid = target["profile_uid"]
        page_id = target["page_id"]
        page_name = target["page_name"]
        page_link = target["page_link"]

        action = f"switch_to_page:{page_link or page_id or page_name}"

        if not page_link:
            error = FacebookSwitchError(
                "page_link is missing in Excel.",
                retryable=False,
            )
            report.log_event(
                row, self.run_id, action, "Failed",
                attempt=1, error=error, retryable=False,
            )
            self._log_target_failure(target, str(error))
            self._emit_rows(rows, "Error", str(error))
            return "failed"

        if not profile_uid:
            error = FacebookSwitchError(
                "AdsPower profile UID is missing from Excel.",
                retryable=False,
            )
            report.log_event(
                row, self.run_id, action, "Failed",
                attempt=1, error=error, retryable=False,
            )
            self._log_target_failure(target, str(error))
            self._emit_rows(rows, "Error", str(error))
            return "failed"

        if driver is None:
            error = FacebookSwitchError(
                f"No active Selenium driver for AdsPower profile {profile_uid}.",
                retryable=False,
            )
            report.log_event(
                row, self.run_id, action, "Failed",
                attempt=1, error=error, retryable=False,
            )
            self._log_target_failure(target, str(error))
            self._emit_rows(rows, "Error", str(error))
            return "failed"

        for attempt in range(1, MAX_OPEN_ATTEMPTS + 1):
            if self.stop_requested:
                self._emit_rows(rows, "Stopped", "Stopped by user.")
                return "stopped"

            try:
                switch_to_page(
                    driver,
                    page_link,
                    page_id=page_id,
                    page_name=page_name,
                )

            except Exception as error:
                retryable = (
                    bool(getattr(error, "retryable", False))
                    and attempt < MAX_OPEN_ATTEMPTS
                )
                report.log_event(
                    row,
                    self.run_id,
                    action,
                    "Retrying" if retryable else "Failed",
                    attempt=attempt,
                    error=error,
                    retryable=retryable,
                )

                if retryable:
                    cmd_log(
                        "WARNING",
                        f"Page switch failed; retrying ({attempt + 1}/{MAX_OPEN_ATTEMPTS})",
                    )
                    if not self._wait_interruptibly(RETRY_DELAY_SECONDS):
                        self._emit_rows(
                            rows,
                            "Stopped",
                            "Stopped by user before the Page switch retry.",
                        )
                        return "stopped"

                    if sessions is not None:
                        try:
                            recovered = self._ensure_profile_session(
                                profile_uid, row, report, sessions
                            )
                            recovered["last_row"] = row
                            driver = recovered["driver"]
                        except Exception as recovery_error:
                            cmd_log(
                                "WARNING",
                                f"Could not recover AdsPower profile {profile_uid}: "
                                f"{recovery_error}",
                            )
                    continue

                self._log_target_failure(target, str(error))
                self._emit_rows(rows, "Error", str(error))
                return "failed"

            else:
                report.log_event(
                    row, self.run_id, action, "Success", attempt=attempt
                )
                cmd_log(
                    "SUCCESS",
                    f"Switched to Facebook Page: {page_name or page_id}",
                )
                break
        else:
            return "failed"

        original_handle = None
        original_handles = set()
        try:
            original_handle = driver.current_window_handle
            original_handles = set(driver.window_handles)
        except Exception:
            pass

        try:
            return self._process_post_pipeline(target, report, driver)
        finally:
            # The old permalink workflow may open the post in a new tab.
            try:
                current_handles = set(driver.window_handles)
                for handle in current_handles - original_handles:
                    driver.switch_to.window(handle)
                    driver.close()

                if original_handle and original_handle in driver.window_handles:
                    driver.switch_to.window(original_handle)
                elif original_handles:
                    remaining = set(driver.window_handles) & original_handles
                    if remaining:
                        driver.switch_to.window(next(iter(remaining)))
            except Exception:
                pass

    def _process_post_pipeline(
        self,
        target: dict,
        report: PageAutoReport,
        driver,
    ) -> str:
        row = target["rows"][0]
        task_id = row.get("task_id", "")
        post_id = str(row.get("post_id") or task_id or "unknown")
        caption = str(row.get("caption") or "").strip()
        comment = str(row.get("comment") or "").strip()
        page_link = str(row.get("page_link") or target.get("page_link") or "").strip()

        result = report.get_result(task_id)
        status = str(result.get("post_status") or "").strip()
        post_url = str(result.get("post_url") or "").strip()
        published_at = result.get("published_at")

        if status == "Completed":
            self._emit_rows([row], "Done")
            return "passed"

        # ----- Publish -----
        publish_completed_statuses = {
            "Published",
            "UrlPending",
            "UrlVerified",
            "CommentPending",
            "CommentSending",
            "CommentUnknown",
        }

        legacy_comment_unknown = status == "Unknown" and bool(post_url)
        comment_recovery_required = status in {
            "CommentSending",
            "CommentUnknown",
        } or legacy_comment_unknown

        if status in {"Running", "PublishSubmitting", "PublishUnknown", "Unknown"}:
            # An earlier Post click may have reached Facebook. Search for the post;
            # never call publish_photo again while the result is ambiguous.
            cmd_log(
                "WARNING",
                f"Checking whether post {post_id} was already published",
            )
            try:
                if post_url:
                    try:
                        open_and_verify_post_url(driver, post_url, caption)
                    except FacebookPostError:
                        post_url = ""

                if not post_url:
                    click_published_post_timestamp(
                        driver,
                        caption,
                        attempts=1,
                        page_link=page_link,
                    )
                    post_url = get_opened_post_url(driver)

                published_at = published_at or datetime.now().astimezone().replace(
                    tzinfo=None
                )
                recovered_status = (
                    "CommentUnknown" if legacy_comment_unknown else "Published"
                )
                report.upsert_result(
                    row,
                    recovered_status,
                    published_at=published_at,
                    post_url=post_url,
                    error="",
                )
                report.log_event(
                    row,
                    self.run_id,
                    f"publish:{post_id}",
                    "Recovered",
                    attempt=1,
                    retryable=False,
                )
                status = recovered_status

            except Exception as error:
                message = (
                    "Publish result is still uncertain. The post was not "
                    "submitted again to avoid creating a duplicate. "
                    f"Verification: {error}"
                )
                report.upsert_result(
                    row,
                    "PublishUnknown",
                    published_at=published_at,
                    post_url=post_url,
                    error=message,
                )
                report.log_event(
                    row,
                    self.run_id,
                    f"publish:{post_id}",
                    "Unknown",
                    attempt=1,
                    error=error,
                    retryable=False,
                )
                cmd_log("ERROR", f"Post {post_id}: publish result is unknown")
                self._emit_rows([row], "Unknown", message)
                return "failed"

        if status not in publish_completed_statuses and status != "Published":
            for attempt in range(1, MAX_STAGE_ATTEMPTS + 1):
                if self.stop_requested:
                    self._emit_rows([row], "Stopped", "Stopped by user.")
                    return "stopped"

                submit_started = {"value": False}

                def mark_submit_started():
                    submit_started["value"] = True
                    report.upsert_result(
                        row,
                        "PublishSubmitting",
                        published_at=published_at,
                        post_url=post_url,
                        error="",
                    )
                    report.log_event(
                        row,
                        self.run_id,
                        f"publish:{post_id}",
                        "Submitting",
                        attempt=attempt,
                        retryable=False,
                    )

                report.upsert_result(
                    row,
                    "PreparingPublish",
                    published_at=published_at,
                    post_url=post_url,
                    error="",
                )
                report.log_event(
                    row,
                    self.run_id,
                    f"publish:{post_id}",
                    "Running",
                    attempt=attempt,
                    retryable=True,
                )
                cmd_log("INFO", f"Publishing post {post_id}")

                try:
                    publish_photo(
                        driver,
                        row,
                        before_submit=mark_submit_started,
                    )

                except PublishUnknownError as error:
                    # The Post button was attempted. Reconcile by locating the
                    # expected caption; do not blindly retry the publication.
                    try:
                        click_published_post_timestamp(
                            driver,
                            caption,
                            attempts=1,
                            page_link=page_link,
                        )
                        post_url = get_opened_post_url(driver)
                    except Exception as verify_error:
                        message = (
                            "Facebook may have accepted the Post click, but "
                            "publication could not be verified. Do not retry "
                            "publishing until the Page is checked. "
                            f"Details: {verify_error}"
                        )
                        report.upsert_result(
                            row,
                            "PublishUnknown",
                            published_at=published_at,
                            post_url=post_url,
                            error=message,
                        )
                        report.log_event(
                            row,
                            self.run_id,
                            f"publish:{post_id}",
                            "Unknown",
                            attempt=attempt,
                            error=error,
                            retryable=False,
                        )
                        cmd_log(
                            "ERROR",
                            f"Post {post_id}: Post click outcome is unknown",
                        )
                        self._emit_rows([row], "Unknown", message)
                        return "failed"

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
                        f"publish:{post_id}",
                        "Recovered",
                        attempt=attempt,
                        retryable=False,
                    )
                    status = "Published"
                    break

                except Exception as error:
                    retryable = (
                        bool(getattr(error, "retryable", False))
                        and not submit_started["value"]
                        and attempt < MAX_STAGE_ATTEMPTS
                    )
                    report.log_event(
                        row,
                        self.run_id,
                        f"publish:{post_id}",
                        "Retrying" if retryable else "Failed",
                        attempt=attempt,
                        error=error,
                        retryable=retryable,
                    )

                    if retryable:
                        cmd_log(
                            "WARNING",
                            f"Publish preparation failed; retrying "
                            f"({attempt + 1}/{MAX_STAGE_ATTEMPTS})",
                        )
                        if not self._wait_interruptibly(STAGE_RETRY_DELAY_SECONDS):
                            self._emit_rows(
                                [row],
                                "Stopped",
                                "Stopped before the publish retry.",
                            )
                            return "stopped"
                        continue

                    final_status = (
                        "PublishUnknown" if submit_started["value"] else "Failed"
                    )
                    message = (
                        "Publish result is uncertain; verify the Page before "
                        "retrying."
                        if submit_started["value"]
                        else f"Failed to prepare the post: {error}"
                    )
                    report.upsert_result(
                        row,
                        final_status,
                        published_at=published_at,
                        post_url=post_url,
                        error=message,
                    )
                    cmd_log("ERROR", f"Post {post_id}: {message}")
                    self._emit_rows(
                        [row],
                        "Unknown" if submit_started["value"] else "Error",
                        message,
                    )
                    return "failed"

                else:
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
                        f"publish:{post_id}",
                        "Success",
                        attempt=attempt,
                    )
                    cmd_log("SUCCESS", f"Post {post_id} published")
                    status = "Published"
                    break

        # ----- Discover and verify post URL -----
        if (
            status not in {
                "UrlVerified",
                "CommentPending",
                "CommentSending",
                "CommentUnknown",
                "Completed",
            }
            or not post_url
        ):
            url_error = None

            for attempt in range(1, MAX_STAGE_ATTEMPTS + 1):
                if self.stop_requested:
                    self._emit_rows([row], "Stopped", "Stopped by user.")
                    return "stopped"

                try:
                    if post_url:
                        try:
                            post_url = open_and_verify_post_url(
                                driver,
                                post_url,
                                caption,
                            )
                        except FacebookPostError:
                            post_url = ""

                    if not post_url:
                        click_published_post_timestamp(
                            driver,
                            caption,
                            attempts=1,
                            page_link=page_link,
                        )
                        post_url = get_opened_post_url(driver)
                        post_url = open_and_verify_post_url(
                            driver,
                            post_url,
                            caption,
                        )

                    report.upsert_result(
                        row,
                        "UrlVerified",
                        published_at=published_at,
                        post_url=post_url,
                        error="",
                    )
                    report.log_event(
                        row,
                        self.run_id,
                        f"url:{post_id}",
                        "Verified",
                        attempt=attempt,
                    )
                    cmd_log("SUCCESS", f"Post URL verified: {post_url}")
                    status = "UrlVerified"
                    break

                except Exception as error:
                    url_error = error
                    retryable = bool(getattr(error, "retryable", False))
                    report.log_event(
                        row,
                        self.run_id,
                        f"url:{post_id}",
                        "Retrying" if retryable and attempt < MAX_STAGE_ATTEMPTS else "Failed",
                        attempt=attempt,
                        error=error,
                        retryable=retryable,
                    )

                    if retryable and attempt < MAX_STAGE_ATTEMPTS:
                        cmd_log(
                            "WARNING",
                            f"Post URL discovery failed; retrying "
                            f"({attempt + 1}/{MAX_STAGE_ATTEMPTS})",
                        )
                        if not self._wait_interruptibly(STAGE_RETRY_DELAY_SECONDS):
                            self._emit_rows(
                                [row],
                                "Stopped",
                                "Stopped before the URL retry.",
                            )
                            return "stopped"
                        continue
                    break

            if status != "UrlVerified":
                message = (
                    "Post was published, but its permalink could not be "
                    f"verified. URL discovery can be retried: {url_error}"
                )
                report.upsert_result(
                    row,
                    "UrlPending",
                    published_at=published_at,
                    post_url=post_url,
                    error=message,
                )
                cmd_log("ERROR", f"Post {post_id}: URL discovery failed")
                self._emit_rows([row], "Error", message)
                return "failed"

        # Always reopen and verify the saved permalink before commenting.
        try:
            post_url = open_and_verify_post_url(driver, post_url, caption)
        except Exception as error:
            message = f"Post URL could not be reopened and verified: {error}"
            report.upsert_result(
                row,
                "UrlPending",
                published_at=published_at,
                post_url=post_url,
                error=message,
            )
            report.log_event(
                row,
                self.run_id,
                f"url:{post_id}",
                "Failed",
                attempt=1,
                error=error,
                retryable=bool(getattr(error, "retryable", False)),
            )
            cmd_log("ERROR", f"Post {post_id}: saved URL verification failed")
            self._emit_rows([row], "Error", message)
            return "failed"

        if not comment:
            report.log_event(
                row,
                self.run_id,
                f"comment:{post_id}",
                "Skipped",
                attempt=1,
            )
            report.upsert_result(
                row,
                "Completed",
                published_at=published_at,
                post_url=post_url,
                error="",
            )
            self._emit_rows([row], "Done")
            cmd_log("SUCCESS", f"Post {post_id} completed (no comment)")
            return "passed"

        # ----- Publish and verify comment -----
        for attempt in range(1, MAX_STAGE_ATTEMPTS + 1):
            if self.stop_requested:
                self._emit_rows([row], "Stopped", "Stopped by user.")
                return "stopped"

            try:
                # This check makes recovery idempotent after an interrupted Send.
                if comment_exists_on_opened_post(
                    driver,
                    comment,
                    timeout=12 if comment_recovery_required else 3,
                ):
                    report.upsert_result(
                        row,
                        "Completed",
                        published_at=published_at,
                        post_url=post_url,
                        error="",
                    )
                    report.log_event(
                        row,
                        self.run_id,
                        f"comment:{post_id}",
                        "Recovered",
                        attempt=attempt,
                        retryable=False,
                    )
                    self._emit_rows([row], "Done")
                    cmd_log("SUCCESS", f"Comment already exists for post {post_id}")
                    return "passed"

                def mark_send_started():
                    report.upsert_result(
                        row,
                        "CommentSending",
                        published_at=published_at,
                        post_url=post_url,
                        error="",
                    )
                    report.log_event(
                        row,
                        self.run_id,
                        f"comment:{post_id}",
                        "Sending",
                        attempt=attempt,
                        retryable=False,
                    )

                report.upsert_result(
                    row,
                    "CommentPending",
                    published_at=published_at,
                    post_url=post_url,
                    error="",
                )
                confirmed = post_comment_on_opened_post(
                    driver,
                    comment,
                    before_send=mark_send_started,
                )

                if not confirmed:
                    raise FacebookPostError(
                        "Comment was not visually confirmed.",
                        retryable=True,
                    )

                report.upsert_result(
                    row,
                    "Completed",
                    published_at=published_at,
                    post_url=post_url,
                    error="",
                )
                report.log_event(
                    row,
                    self.run_id,
                    f"comment:{post_id}",
                    "Success",
                    attempt=attempt,
                )
                self._emit_rows([row], "Done")
                cmd_log("SUCCESS", f"Comment published for post {post_id}")
                return "passed"

            except PublishUnknownError as error:
                # Send may have succeeded; verify before any second Send.
                try:
                    exists = comment_exists_on_opened_post(
                        driver,
                        comment,
                        timeout=15,
                    )
                except Exception:
                    exists = False

                if exists:
                    report.upsert_result(
                        row,
                        "Completed",
                        published_at=published_at,
                        post_url=post_url,
                        error="",
                    )
                    report.log_event(
                        row,
                        self.run_id,
                        f"comment:{post_id}",
                        "Recovered",
                        attempt=attempt,
                        error=error,
                        retryable=False,
                    )
                    self._emit_rows([row], "Done")
                    cmd_log("SUCCESS", f"Comment verified for post {post_id}")
                    return "passed"

                message = (
                    "Comment Send was attempted, but Facebook did not confirm "
                    "whether it was published. The next run will check for an "
                    "existing comment before any retry."
                )
                report.upsert_result(
                    row,
                    "CommentUnknown",
                    published_at=published_at,
                    post_url=post_url,
                    error=message,
                )
                report.log_event(
                    row,
                    self.run_id,
                    f"comment:{post_id}",
                    "Unknown",
                    attempt=attempt,
                    error=error,
                    retryable=True,
                )
                cmd_log("ERROR", f"Post {post_id}: comment result is uncertain")
                self._emit_rows([row], "Unknown", message)
                return "failed"

            except Exception as error:
                retryable = bool(getattr(error, "retryable", False))
                report.log_event(
                    row,
                    self.run_id,
                    f"comment:{post_id}",
                    "Retrying" if retryable and attempt < MAX_STAGE_ATTEMPTS else "Failed",
                    attempt=attempt,
                    error=error,
                    retryable=retryable,
                )

                if retryable and attempt < MAX_STAGE_ATTEMPTS:
                    cmd_log(
                        "WARNING",
                        f"Comment preparation failed; retrying "
                        f"({attempt + 1}/{MAX_STAGE_ATTEMPTS})",
                    )
                    if not self._wait_interruptibly(STAGE_RETRY_DELAY_SECONDS):
                        self._emit_rows(
                            [row],
                            "Stopped",
                            "Stopped before the comment retry.",
                        )
                        return "stopped"
                    continue

                message = f"Post published, but comment failed: {error}"
                report.upsert_result(
                    row,
                    "CommentPending",
                    published_at=published_at,
                    post_url=post_url,
                    error=message,
                )
                cmd_log("ERROR", f"Post {post_id}: comment failed")
                self._emit_rows([row], "Error", message)
                return "failed"

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
