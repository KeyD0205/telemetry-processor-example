from __future__ import annotations

import hashlib
import json
import re
from datetime import timezone
from typing import Any, Iterable, Mapping

from .models import CellState, DataQualityIssue, EventKind, Fault, NormalizedEvent, ProgramState
from .time_utils import datetime_from_ns, iso_from_ns, timestamp_ns_from_event_time
from .alias_maps import EVENT_NAME_ALIASES, STATE_ALIASES, PROGRAM_STATE_ALIASES, PROGRAM_ID_ALIASES

# Logging setup
import logging
logger = logging.getLogger(__name__)


def normalize_token(value: Any) -> str:
    return str(value or "").strip().lower().replace(" ", "_")


def compact_token(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def normalize_event_kind(raw: Any, has_cell_status: bool) -> EventKind:
    if has_cell_status:
        return EventKind.STATE_CHANGED
    if raw is None:
        return EventKind.UNKNOWN
    token = normalize_token(raw)
    return EVENT_NAME_ALIASES.get(token, EVENT_NAME_ALIASES.get(compact_token(raw), EventKind.UNKNOWN))


def normalize_state(raw: Any) -> CellState:
    token = normalize_token(raw).replace("_", "-")
    return STATE_ALIASES.get(token, CellState.UNKNOWN)


def normalize_program_state(raw: Any) -> ProgramState:
    return PROGRAM_STATE_ALIASES.get(normalize_token(raw), ProgramState.UNKNOWN)


def normalize_program_id(raw: Any) -> str | None:
    if raw is None:
        return None
    raw_text = str(raw).strip()
    if not raw_text:
        return None
    token = normalize_token(raw_text)
    compact = compact_token(raw_text)
    return PROGRAM_ID_ALIASES.get(token) or PROGRAM_ID_ALIASES.get(compact) or raw_text


def canonical_event_hash(event: Mapping[str, Any]) -> str:
    canonical = json.dumps(event, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def issue(
    *,
    severity: str,
    code: str,
    cell_id: str | None,
    timestamp_ns: int | None,
    message: str,
    source_index: int | None,
    context: dict[str, Any] | None = None,
) -> DataQualityIssue:
    return DataQualityIssue(
        severity=severity,
        code=code,
        cell_id=cell_id,
        timestamp=iso_from_ns(timestamp_ns) if timestamp_ns is not None else None,
        message=message,
        source_index=source_index,
        context=context or {},
    )


def normalize_events(raw_events: Iterable[Mapping[str, Any]]) -> tuple[list[NormalizedEvent], list[DataQualityIssue]]:
    """Convert schema-drifting raw telemetry to a strict event model.

    The function is intentionally side-effect free, making it safe for both live ingestion and
    historical recomputation.
    """

    normalized: list[NormalizedEvent] = []
    issues: list[DataQualityIssue] = []
    seen_event_ids: set[str] = set()
    last_seen_ts_by_cell: dict[str, int] = {}

    for index, raw in enumerate(raw_events):
        event_id = canonical_event_hash(raw)
        if event_id in seen_event_ids:
            cell_id = str(raw.get("cell_id")) if raw.get("cell_id") is not None else None
            timestamp_ns = None
            if isinstance(raw.get("event_time"), Mapping):
                try:
                    timestamp_ns = timestamp_ns_from_event_time(raw["event_time"])
                except (ValueError, KeyError, TypeError):
                    timestamp_ns = None
            logger.warning(f"Dropped duplicate event: {event_id} (cell_id={cell_id}) at index {index}")
            issues.append(issue(
                severity="warning",
                code="duplicate_event",
                cell_id=cell_id,
                timestamp_ns=timestamp_ns,
                source_index=index,
                message="Dropped exact duplicate raw event.",
                context={"event_id": event_id},
            ))
            continue
        seen_event_ids.add(event_id)

        cell_id_raw = raw.get("cell_id")
        if not cell_id_raw:
            issues.append(issue(
                severity="error",
                code="missing_cell_id",
                cell_id=None,
                timestamp_ns=None,
                source_index=index,
                message="Event is missing required cell_id and cannot be processed.",
            ))
            continue
        cell_id = str(cell_id_raw).strip()

        event_time = raw.get("event_time")
        if not isinstance(event_time, Mapping):
            issues.append(issue(
                severity="error",
                code="missing_event_time",
                cell_id=cell_id,
                timestamp_ns=None,
                source_index=index,
                message="Event is missing required event_time and cannot be processed.",
            ))
            continue
        try:
            timestamp_ns = timestamp_ns_from_event_time(event_time)
        except Exception as exc:
            issues.append(issue(
                severity="error",
                code="invalid_event_time",
                cell_id=cell_id,
                timestamp_ns=None,
                source_index=index,
                message=str(exc),
            ))
            continue

        if cell_id in last_seen_ts_by_cell and timestamp_ns < last_seen_ts_by_cell[cell_id]:
            issues.append(issue(
                severity="warning",
                code="out_of_order_event",
                cell_id=cell_id,
                timestamp_ns=timestamp_ns,
                source_index=index,
                message="Event arrived earlier than a previously ingested event for the same cell; downstream processing sorts by event time.",
                context={"previous_timestamp": iso_from_ns(last_seen_ts_by_cell[cell_id])},
            ))
        last_seen_ts_by_cell[cell_id] = max(timestamp_ns, last_seen_ts_by_cell.get(cell_id, timestamp_ns))

        cell_status = raw.get("cell_status")
        has_cell_status = isinstance(cell_status, Mapping)
        kind = normalize_event_kind(raw.get("event_type"), has_cell_status)
        if kind == EventKind.UNKNOWN:
            issues.append(issue(
                severity="warning",
                code="unknown_event_type",
                cell_id=cell_id,
                timestamp_ns=timestamp_ns,
                source_index=index,
                message="Event type could not be mapped to a canonical event kind.",
                context={"raw_event_type": raw.get("event_type")},
            ))

        state = None
        raw_state = None
        program_state = None
        program_id = None
        faults: tuple[Fault, ...] = ()

        if has_cell_status:
            raw_state = str(cell_status.get("cell_state", "")).strip() or None
            state = normalize_state(raw_state)
            if state == CellState.UNKNOWN:
                issues.append(issue(
                    severity="warning",
                    code="unknown_cell_state",
                    cell_id=cell_id,
                    timestamp_ns=timestamp_ns,
                    source_index=index,
                    message="Cell state could not be mapped to a canonical state.",
                    context={"raw_state": raw_state},
                ))
            elif raw_state and state.value not in {raw_state, normalize_token(raw_state)}:
                issues.append(issue(
                    severity="info",
                    code="normalized_cell_state",
                    cell_id=cell_id,
                    timestamp_ns=timestamp_ns,
                    source_index=index,
                    message="Raw cell state was normalized to a canonical state.",
                    context={"raw_state": raw_state, "normalized_state": state.value},
                ))

            program_state = normalize_program_state(cell_status.get("program_state"))
            if program_state == ProgramState.UNKNOWN and cell_status.get("program_state"):
                issues.append(issue(
                    severity="warning",
                    code="unknown_program_state",
                    cell_id=cell_id,
                    timestamp_ns=timestamp_ns,
                    source_index=index,
                    message="Program state could not be mapped to a canonical value.",
                    context={"raw_program_state": cell_status.get("program_state")},
                ))

            raw_program_id = cell_status.get("program_id")
            program_id = normalize_program_id(raw_program_id)
            if raw_program_id and program_id != raw_program_id:
                issues.append(issue(
                    severity="info",
                    code="normalized_program_id",
                    cell_id=cell_id,
                    timestamp_ns=timestamp_ns,
                    source_index=index,
                    message="Program id was normalized to a canonical value.",
                    context={"raw_program_id": raw_program_id, "normalized_program_id": program_id},
                ))

            codes = list(cell_status.get("cell_error_codes") or [])
            messages = list(cell_status.get("cell_error_messages") or [])
            if len(codes) != len(messages):
                issues.append(issue(
                    severity="warning",
                    code="fault_code_message_mismatch",
                    cell_id=cell_id,
                    timestamp_ns=timestamp_ns,
                    source_index=index,
                    message="Fault code/message arrays have different lengths; missing values are padded.",
                    context={"codes": codes, "messages": messages},
                ))
            max_len = max(len(codes), len(messages))
            faults = tuple(
                Fault(code=str(codes[i]) if i < len(codes) else "UNKNOWN", message=str(messages[i]) if i < len(messages) else "")
                for i in range(max_len)
            )

        cycle_duration = raw.get("cycle_duration_seconds")
        if cycle_duration is not None:
            try:
                cycle_duration = float(cycle_duration)
            except (TypeError, ValueError):
                issues.append(issue(
                    severity="warning",
                    code="invalid_cycle_duration",
                    cell_id=cell_id,
                    timestamp_ns=timestamp_ns,
                    source_index=index,
                    message="cycle_duration_seconds was not numeric and was ignored.",
                    context={"raw_cycle_duration_seconds": raw.get("cycle_duration_seconds")},
                ))
                cycle_duration = None
        elif kind == EventKind.CYCLE_END:
            issues.append(issue(
                severity="info",
                code="missing_cycle_duration",
                cell_id=cell_id,
                timestamp_ns=timestamp_ns,
                source_index=index,
                message="cycle_end does not include cycle_duration_seconds; duration will be derived from the matched cycle_start when possible.",
            ))

        normalized.append(NormalizedEvent(
            event_id=event_id,
            source_index=index,
            cell_id=cell_id,
            timestamp=datetime_from_ns(timestamp_ns).astimezone(timezone.utc),
            timestamp_ns=timestamp_ns,
            kind=kind,
            state=state,
            raw_state=raw_state,
            program_state=program_state,
            program_id=program_id,
            cycle_duration_seconds=cycle_duration,
            faults=faults,
            raw_event=raw,
        ))

    normalized.sort(key=lambda event: (event.cell_id, event.timestamp_ns, event.source_index))
    return normalized, issues
