from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from statistics import mean, median
from typing import Any, Iterable

from .models import CellState, DataQualityIssue, EventKind, NormalizedEvent
from .state_machine import DOWNTIME_STATES, FAULT_STATES, MAINTENANCE_STATES, PRODUCTIVE_STATES, state_events_by_cell
from .time_utils import NANOSECONDS_PER_SECOND, datetime_from_ns, iso_from_ns

SECONDS_PER_HOUR = 3600.0
# Allows for clock-sync jitter between the robot controller and the data collector.
DURATION_MISMATCH_TOLERANCE_SECONDS = 2.0


def ns_to_seconds(delta_ns: int) -> float:
    return delta_ns / NANOSECONDS_PER_SECOND


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * p
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    weight = rank - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def event_state_at(timestamp_ns: int, state_events: list[NormalizedEvent]) -> CellState | None:
    current: CellState | None = None
    for event in state_events:
        if event.timestamp_ns > timestamp_ns:
            break
        current = event.state
    return current


def hour_bucket(timestamp_ns: int) -> str:
    dt = datetime_from_ns(timestamp_ns).astimezone(timezone.utc)
    return dt.replace(minute=0, second=0, microsecond=0).isoformat().replace("+00:00", "Z")


def compute_metrics(events: Iterable[NormalizedEvent]) -> tuple[dict[str, Any], list[DataQualityIssue]]:
    """Compute fleet and per-cell operational metrics from normalized events.

    Returns a (report_dict, issues) tuple. The report_dict has top-level keys:
    ``generated_at``, ``event_count``, ``cell_count``, ``window``, ``fleet``, and ``cells``.
    Each entry in ``cells`` contains availability, cycle times, state durations, transitions,
    throughput buckets, and fault events. ``issues`` lists any data-quality warnings raised
    during metric computation (e.g. unpaired cycle events, duration mismatches).
    """
    sorted_events = sorted(events, key=lambda event: (event.cell_id, event.timestamp_ns, event.source_index))
    issues: list[DataQualityIssue] = []
    events_by_cell: dict[str, list[NormalizedEvent]] = defaultdict(list)
    for event in sorted_events:
        events_by_cell[event.cell_id].append(event)

    states_by_cell = state_events_by_cell(sorted_events)
    cells: list[dict[str, Any]] = []
    fleet_completed_cycles = 0
    fleet_observed_seconds = 0.0
    fleet_uptime_seconds = 0.0
    fleet_downtime_seconds = 0.0
    fleet_maintenance_seconds = 0.0
    fleet_fault_seconds = 0.0
    fleet_cycle_durations: list[float] = []
    fleet_throughput_buckets: Counter[str] = Counter()
    fleet_faults: list[dict[str, Any]] = []
    fleet_production_count_events = 0
    fleet_produced_units_delta = 0
    fleet_latest_production_count = 0
    fleet_operator_action_count = 0

    for cell_id, cell_events in events_by_cell.items():
        first_ns = min(event.timestamp_ns for event in cell_events)
        last_ns = max(event.timestamp_ns for event in cell_events)
        observed_seconds = ns_to_seconds(max(0, last_ns - first_ns))
        fleet_observed_seconds += observed_seconds

        state_events = states_by_cell.get(cell_id, [])
        state_durations: dict[str, float] = {state.value: 0.0 for state in CellState}
        transitions: list[dict[str, Any]] = []

        for idx, state_event in enumerate(state_events):
            next_ns = state_events[idx + 1].timestamp_ns if idx + 1 < len(state_events) else last_ns
            duration = ns_to_seconds(max(0, next_ns - state_event.timestamp_ns))
            if state_event.state:
                state_durations[state_event.state.value] += duration
            if idx + 1 < len(state_events):
                transitions.append({
                    "from": state_event.state.value if state_event.state else None,
                    "to": state_events[idx + 1].state.value if state_events[idx + 1].state else None,
                    "at": state_events[idx + 1].timestamp_iso,
                })

        uptime_seconds = sum(state_durations[state.value] for state in PRODUCTIVE_STATES)
        downtime_seconds = sum(state_durations[state.value] for state in DOWNTIME_STATES)
        maintenance_seconds = sum(state_durations[state.value] for state in MAINTENANCE_STATES)
        fault_seconds = sum(state_durations[state.value] for state in FAULT_STATES)
        fleet_uptime_seconds += uptime_seconds
        fleet_downtime_seconds += downtime_seconds
        fleet_maintenance_seconds += maintenance_seconds
        fleet_fault_seconds += fault_seconds

        active_cycle_start: NormalizedEvent | None = None
        completed_cycles: list[dict[str, Any]] = []
        throughput_buckets: Counter[str] = Counter()

        for event in cell_events:
            if event.kind == EventKind.CYCLE_START:
                state_at_start = event_state_at(event.timestamp_ns, state_events)
                if state_at_start not in PRODUCTIVE_STATES:
                    issues.append(DataQualityIssue(
                        severity="warning",
                        code="cycle_started_while_not_productive",
                        cell_id=cell_id,
                        timestamp=event.timestamp_iso,
                        source_index=event.source_index,
                        message="cycle_start occurred while the cell was not in a productive state.",
                        context={"state_at_cycle_start": state_at_start.value if state_at_start else None},
                    ))
                if active_cycle_start is not None:
                    issues.append(DataQualityIssue(
                        severity="warning",
                        code="cycle_start_without_previous_end",
                        cell_id=cell_id,
                        timestamp=event.timestamp_iso,
                        source_index=event.source_index,
                        message="New cycle_start arrived before the previous cycle had a cycle_end; previous cycle was marked incomplete.",
                        context={"previous_cycle_start": active_cycle_start.timestamp_iso},
                    ))
                active_cycle_start = event

            elif event.kind == EventKind.CYCLE_END:
                if active_cycle_start is None:
                    issues.append(DataQualityIssue(
                        severity="warning",
                        code="cycle_end_without_start",
                        cell_id=cell_id,
                        timestamp=event.timestamp_iso,
                        source_index=event.source_index,
                        message="cycle_end could not be paired with a prior cycle_start.",
                    ))
                    continue

                derived_duration = ns_to_seconds(event.timestamp_ns - active_cycle_start.timestamp_ns)
                if derived_duration < 0:
                    issues.append(DataQualityIssue(
                        severity="warning",
                        code="negative_cycle_duration",
                        cell_id=cell_id,
                        timestamp=event.timestamp_iso,
                        source_index=event.source_index,
                        message="cycle_end timestamp is before cycle_start after sorting; cycle is ignored.",
                        context={"cycle_start": active_cycle_start.timestamp_iso},
                    ))
                    active_cycle_start = None
                    continue

                duration = derived_duration
                reported = event.cycle_duration_seconds
                if reported is not None and abs(reported - derived_duration) > DURATION_MISMATCH_TOLERANCE_SECONDS:
                    issues.append(DataQualityIssue(
                        severity="warning",
                        code="cycle_duration_mismatch",
                        cell_id=cell_id,
                        timestamp=event.timestamp_iso,
                        source_index=event.source_index,
                        message="Reported cycle_duration_seconds differs from timestamps; timestamp-derived duration is used.",
                        context={
                            "reported_seconds": reported,
                            "derived_seconds": derived_duration,
                            "cycle_start": active_cycle_start.timestamp_iso,
                        },
                    ))

                cycle = {
                    "cell_id": cell_id,
                    "start": active_cycle_start.timestamp_iso,
                    "end": event.timestamp_iso,
                    "duration_seconds": round(duration, 3),
                    "reported_duration_seconds": reported,
                    "derived_from_timestamps": True,
                }
                completed_cycles.append(cycle)
                throughput_buckets[hour_bucket(event.timestamp_ns)] += 1
                fleet_throughput_buckets[hour_bucket(event.timestamp_ns)] += 1
                active_cycle_start = None

        if active_cycle_start is not None:
            issues.append(DataQualityIssue(
                severity="warning",
                code="cycle_start_without_end",
                cell_id=cell_id,
                timestamp=active_cycle_start.timestamp_iso,
                source_index=active_cycle_start.source_index,
                message="cycle_start did not have a matching cycle_end within the processing window.",
            ))

        cycle_durations = [cycle["duration_seconds"] for cycle in completed_cycles]
        fleet_cycle_durations.extend(cycle_durations)
        completed_count = len(completed_cycles)
        fleet_completed_cycles += completed_count

        production_events = [
            event for event in cell_events
            if event.kind == EventKind.PRODUCTION_COUNT and event.production_count is not None
        ]
        production_count_events = len(production_events)
        operator_action_count = sum(1 for event in cell_events if event.kind == EventKind.OPERATOR_ACTION)
        produced_units_delta = 0
        production_count_resets = 0
        for previous, current in zip(production_events, production_events[1:]):
            previous_count = previous.production_count
            current_count = current.production_count
            if previous_count is None or current_count is None:
                continue
            delta = current_count - previous_count
            if delta >= 0:
                produced_units_delta += delta
            else:
                production_count_resets += 1
                issues.append(DataQualityIssue(
                    severity="warning",
                    code="production_count_reset",
                    cell_id=cell_id,
                    timestamp=current.timestamp_iso,
                    source_index=current.source_index,
                    message="production_count decreased; treated as a counter reset and not bridged across the drop.",
                    context={"previous_count": previous_count, "current_count": current_count},
                ))

        latest_production_count = production_events[-1].production_count if production_events else None
        fleet_production_count_events += production_count_events
        fleet_produced_units_delta += produced_units_delta
        fleet_latest_production_count += latest_production_count or 0
        fleet_operator_action_count += operator_action_count

        status_events = [event for event in cell_events if event.kind == EventKind.STATE_CHANGED]
        current_state_event = status_events[-1] if status_events else None
        current_state = current_state_event.state.value if current_state_event and current_state_event.state else CellState.UNKNOWN.value
        current_program_id = current_state_event.program_id if current_state_event else None

        fault_events: list[dict[str, Any]] = []
        for event in status_events:
            if event.state == CellState.FAULT or event.faults:
                fault = {
                    "cell_id": cell_id,
                    "timestamp": event.timestamp_iso,
                    "state": event.state.value if event.state else None,
                    "codes": [fault.code for fault in event.faults],
                    "messages": [fault.message for fault in event.faults],
                    "program_id": event.program_id,
                }
                fault_events.append(fault)
                fleet_faults.append(fault)

        program_ids = sorted({event.program_id for event in status_events if event.program_id})
        quality_counts = Counter(issue.code for issue in issues if issue.cell_id == cell_id)

        cells.append({
            "cell_id": cell_id,
            "window": {"start": iso_from_ns(first_ns), "end": iso_from_ns(last_ns), "observed_seconds": round(observed_seconds, 3)},
            "current_state": current_state,
            "current_program_id": current_program_id,
            "program_ids": program_ids,
            "uptime_seconds": round(uptime_seconds, 3),
            "downtime_seconds": round(downtime_seconds, 3),
            "maintenance_seconds": round(maintenance_seconds, 3),
            "fault_seconds": round(fault_seconds, 3),
            "availability": round(uptime_seconds / observed_seconds, 4) if observed_seconds else None,
            "productive_ratio_excluding_maintenance": round(uptime_seconds / (observed_seconds - maintenance_seconds), 4) if observed_seconds > maintenance_seconds else None,
            "throughput_cycles_per_hour": round(completed_count / (observed_seconds / SECONDS_PER_HOUR), 3) if observed_seconds else None,
            "completed_cycles": completed_count,
            "production_count_events": production_count_events,
            "latest_production_count": latest_production_count,
            "produced_units_delta": produced_units_delta,
            "production_count_resets": production_count_resets,
            "operator_action_count": operator_action_count,
            "cycle_time_seconds": {
                "avg": round(mean(cycle_durations), 3) if cycle_durations else None,
                "median": round(median(cycle_durations), 3) if cycle_durations else None,
                "p95": round(percentile(cycle_durations, 0.95), 3) if cycle_durations else None,
                "min": round(min(cycle_durations), 3) if cycle_durations else None,
                "max": round(max(cycle_durations), 3) if cycle_durations else None,
            },
            "state_durations_seconds": {state: round(seconds, 3) for state, seconds in state_durations.items() if seconds > 0},
            "transitions": transitions,
            "cycles": completed_cycles,
            "throughput_over_time": [
                {"bucket_start": bucket, "completed_cycles": count}
                for bucket, count in sorted(throughput_buckets.items())
            ],
            "fault_event_count": len(fault_events),
            "unique_fault_codes": sorted({code for fault in fault_events for code in fault["codes"]}),
            "recent_faults": sorted(fault_events, key=lambda fault: fault["timestamp"], reverse=True)[:10],
            "data_quality_issue_counts": dict(sorted(quality_counts.items())),
        })

    first_ns_all = min((event.timestamp_ns for event in sorted_events), default=None)
    last_ns_all = max((event.timestamp_ns for event in sorted_events), default=None)

    result = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "event_count": len(sorted_events),
        "cell_count": len(cells),
        "window": {
            "start": iso_from_ns(first_ns_all) if first_ns_all is not None else None,
            "end": iso_from_ns(last_ns_all) if last_ns_all is not None else None,
        },
        "fleet": {
            "completed_cycles": fleet_completed_cycles,
            "observed_cell_seconds": round(fleet_observed_seconds, 3),
            "uptime_seconds": round(fleet_uptime_seconds, 3),
            "downtime_seconds": round(fleet_downtime_seconds, 3),
            "maintenance_seconds": round(fleet_maintenance_seconds, 3),
            "fault_seconds": round(fleet_fault_seconds, 3),
            "availability": round(fleet_uptime_seconds / fleet_observed_seconds, 4) if fleet_observed_seconds else None,
            "throughput_cycles_per_hour": round(fleet_completed_cycles / (fleet_observed_seconds / SECONDS_PER_HOUR), 3) if fleet_observed_seconds else None,
            "production_count_events": fleet_production_count_events,
            "latest_production_count_total": fleet_latest_production_count if fleet_production_count_events else None,
            "produced_units_delta": fleet_produced_units_delta,
            "operator_action_count": fleet_operator_action_count,
            "cycle_time_seconds": {
                "avg": round(mean(fleet_cycle_durations), 3) if fleet_cycle_durations else None,
                "median": round(median(fleet_cycle_durations), 3) if fleet_cycle_durations else None,
                "p95": round(percentile(fleet_cycle_durations, 0.95), 3) if fleet_cycle_durations else None,
            },
            "throughput_over_time": [
                {"bucket_start": bucket, "completed_cycles": count}
                for bucket, count in sorted(fleet_throughput_buckets.items())
            ],
            "recent_faults": sorted(fleet_faults, key=lambda fault: fault["timestamp"], reverse=True)[:20],
        },
        "cells": sorted(cells, key=lambda cell: cell["cell_id"]),
    }
    return result, issues
