import math
import time
import uuid

from pathlib import Path
from PySide6.QtCore import QSettings, QThread, Signal

from src.configs.adspower import ADSPOWER_DEFAULT_URL
from src.configs.path import DATA_DIR
from src.configs import automation as automation_config
from src.features.page_posting.adspower import (
    check_connection,
    check_profiles,
    connect_driver,
    get_active_profile,
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
    open_page_link,
)
from src.features.page_posting.service import (
    build_page_jobs,
    flatten_page_jobs,
)
from src.features.page_posting.report import PageAutoReport
from src.features.page_posting import validation

from src.utils.cmd_log import cmd_log

# -----  -----
MAX_OPEN_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 2


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
    """Resolve Excel media filenames against the chosen media directory.

    Rows with missing media are retained and marked invalid so the UI can show
    the exact Excel row and filename instead of silently dropping them.
    """
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

            # Always re-check media files: the Excel workbook may be unchanged
            # while files are moved, added, deleted, or a different folder is selected.
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

            # Keep rows with missing media visible in the table. Run is disabled
            # by the UI whenever validation_errors is non-empty.
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
            check_connection(self.api_key)
            cmd_log("SUCCESS", "AdsPower API connected")

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

            cmd_log(
                "INFO",
                f"Collected target sequence: {len(targets)} targets",
            )

            total_data_rows = len(self._flatten_rows())
            unique_page_count = len(
                {
                    str(target.get("page_id") or "").strip()
                    for target in targets
                    if str(target.get("page_id") or "").strip()
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

            for index, target in enumerate(targets):
                current_order = str(target.get("post_order") or "").strip() or "unknown"

                if index > 0:
                    previous_order = (
                        str(targets[index - 1].get("post_order") or "").strip()
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

                        cmd_log("INFO", "Preparing next Post Order...")
                        _cmd_separator()

                        can_continue = self._wait_between_orders(
                            delay_seconds=order_delay_seconds,
                        )
                    else:
                        can_continue = self._wait_between_pages(
                            delay_seconds=page_delay_seconds,
                        )

                    if not can_continue:
                        remaining = targets[index:]

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
                    remaining = targets[index:]

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

            if (
                passed + failed == len(targets)
                and stopped == 0
                and not self.stop_requested
            ):
                run_summary = {
                    "total": len(targets),
                    "success": passed,
                    "failed": failed,
                    "post_orders": len(completed_orders),
                }

        except Exception as error:
            message = f"Page Auto failed: {error}"
            cmd_log("ERROR", message)
            self.error.emit(message)

        finally:
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
    ) -> bool:
        if self.stop_requested:
            return False

        if delay_seconds <= 0:
            return True

        deadline = time.monotonic() + delay_seconds

        while not self.stop_requested:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(0.5, remaining))

        if self.stop_requested:
            return False

        return True

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
    ) -> bool:
        if self.stop_requested:
            return False

        if delay_seconds <= 0:
            return True

        deadline = time.monotonic() + delay_seconds

        while not self.stop_requested:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(0.5, remaining))

        if self.stop_requested:
            return False

        return True

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

        set_credentials(
            api_key=api_key,
            api_url=local_api,
        )

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
            targets.append(
                {
                    "row_number": index,
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
            driver.execute_script("return 1")
        except Exception:
            return False

        return True

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
            active_check_failed = False

            try:
                active_profile = get_active_profile(profile_uid)
            except Exception as error:
                active_check_failed = True
                if self._driver_is_usable(driver):
                    cmd_log(
                        "WARNING",
                        f"Could not verify AdsPower profile {profile_uid}, but its "
                        f"Selenium driver is still responding; reusing it: {error}",
                    )
                    return session

                cmd_log(
                    "WARNING",
                    f"Could not verify AdsPower profile {profile_uid} and its "
                    f"Selenium driver is unresponsive: {error}",
                )

            if active_profile and self._driver_is_usable(driver):
                return session

            reason = (
                "active profile check failed / driver is unresponsive"
                if active_check_failed
                else "profile was closed or the Selenium driver stopped responding"
            )
            cmd_log(
                "WARNING",
                f"AdsPower profile {profile_uid} needs recovery because {reason}. "
                "Detaching the old driver and reopening/reconnecting.",
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

            stage = "browser:attach"
            driver = connect_driver(profile_data)
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

            if driver is not None:
                try:
                    driver.quit()
                except Exception as error:
                    cmd_log(
                        "WARNING",
                        f"Could not quit Selenium driver for profile "
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
                                "Closed",
                            )
                        except Exception:
                            pass

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
        action: str = "open Page link",
    ) -> None:
        position = target.get("order_position", target.get("row_number", "?"))
        total = target.get("order_total", "?")
        page_name = target.get("page_name") or target.get("page_id") or "Unknown Page"
        row_number = target.get("row_number", "?")
        cmd_log("ERROR", f"[{position}/{total}] Failed to {action}")
        cmd_log("ERROR", f"Page: {page_name} | Data row: {row_number}")
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

        action = f"open_page_link:{page_link or page_id or page_name}"

        if not page_link:
            error = FacebookSwitchError(
                "page_link is missing in Excel.",
                retryable=False,
            )
            report.log_event(
                row,
                self.run_id,
                action,
                "Failed",
                attempt=1,
                error=error,
                retryable=False,
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
                row,
                self.run_id,
                action,
                "Failed",
                attempt=1,
                error=error,
                retryable=False,
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
                row,
                self.run_id,
                action,
                "Failed",
                attempt=1,
                error=error,
                retryable=False,
            )
            self._log_target_failure(target, str(error))
            self._emit_rows(rows, "Error", str(error))
            return "failed"

        for attempt in range(1, MAX_OPEN_ATTEMPTS + 1):
            if self.stop_requested:
                self._emit_rows(
                    rows,
                    "Stopped",
                    "Stopped by user.",
                )
                return "stopped"

            try:
                open_page_link(driver, page_link)

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
                    if not self._wait_interruptibly(RETRY_DELAY_SECONDS):
                        self._emit_rows(
                            rows,
                            "Stopped",
                            "Stopped by user before the retry could run.",
                        )
                        return "stopped"

                    if sessions is not None and profile_uid:
                        try:
                            recovered_session = self._ensure_profile_session(
                                profile_uid,
                                row,
                                report,
                                sessions,
                            )
                        except Exception as recovery_error:
                            cmd_log(
                                "WARNING",
                                f"Could not recover AdsPower profile {profile_uid} "
                                f"after a Page navigation failure: {recovery_error}",
                            )
                        else:
                            recovered_session["last_row"] = row
                            driver = recovered_session["driver"]

                    continue

                self._log_target_failure(target, str(error))
                self._emit_rows(rows, "Error", str(error))
                return "failed"

            else:
                report.log_event(
                    row,
                    self.run_id,
                    action,
                    "Success",
                    attempt=attempt,
                )
                self._emit_rows(rows, "Done")
                return "passed"

        return "failed"

    def _emit_rows(
        self,
        rows: list[dict],
        ui_status: str,
        error: str = "",
    ):
        for row in rows:
            self.progress.emit(
                {
                    "task_id": row.get("task_id"),
                    "ui_status": ui_status,
                    "error": error,
                }
            )
