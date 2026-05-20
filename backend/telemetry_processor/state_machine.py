from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from .models import CellState, DataQualityIssue, EventKind, NormalizedEvent

# Canonical transitions. The model is intentionally permissive: telemetry can skip intermediate
# states, but transitions that are almost certainly impossible still become data-quality warnings.
ALLOWED_TRANSITIONS: dict[CellState, set[CellState]] = {
    CellState.SLEEP: {CellState.WAITING_FOR_HUMAN, CellState.RUNNING, CellState.MAINTENANCE, CellState.FAULT, CellState.SLEEP},
    CellState.WAITING_FOR_HUMAN: {CellState.RUNNING, CellState.MAINTENANCE, CellState.STOPPED, CellState.FAULT, CellState.WAITING_FOR_HUMAN},
    CellState.RUNNING: {CellState.SLOWED, CellState.PAUSED, CellState.STOPPED, CellState.FAULT, CellState.MAINTENANCE, CellState.SLEEP, CellState.RUNNING},
    CellState.SLOWED: {CellState.RUNNING, CellState.PAUSED, CellState.STOPPED, CellState.FAULT, CellState.SLOWED},
    CellState.PAUSED: {CellState.RUNNING, CellState.STOPPED, CellState.FAULT, CellState.MAINTENANCE, CellState.PAUSED},
    CellState.STOPPED: {CellState.RUNNING, CellState.PAUSED, CellState.FAULT, CellState.MAINTENANCE, CellState.SLEEP, CellState.STOPPED},
    CellState.FAULT: {CellState.RUNNING, CellState.PAUSED, CellState.STOPPED, CellState.MAINTENANCE, CellState.FAULT},
    CellState.MAINTENANCE: {CellState.RUNNING, CellState.STOPPED, CellState.WAITING_FOR_HUMAN, CellState.SLEEP, CellState.MAINTENANCE},
    CellState.UNKNOWN: set(CellState),
}

PRODUCTIVE_STATES = {CellState.RUNNING, CellState.SLOWED}
DOWNTIME_STATES = {CellState.SLEEP, CellState.WAITING_FOR_HUMAN, CellState.PAUSED, CellState.STOPPED, CellState.FAULT}
MAINTENANCE_STATES = {CellState.MAINTENANCE}
FAULT_STATES = {CellState.FAULT}


def validate_state_transitions(events: Iterable[NormalizedEvent]) -> list[DataQualityIssue]:
    issues: list[DataQualityIssue] = []
    previous_by_cell: dict[str, NormalizedEvent] = {}

    for event in events:
        if event.kind != EventKind.STATE_CHANGED or event.state is None:
            continue
        previous = previous_by_cell.get(event.cell_id)
        if previous and previous.state is not None:
            allowed = ALLOWED_TRANSITIONS.get(previous.state, set(CellState))
            if event.state not in allowed:
                issues.append(DataQualityIssue(
                    severity="warning",
                    code="unexpected_state_transition",
                    cell_id=event.cell_id,
                    timestamp=event.timestamp_iso,
                    source_index=event.source_index,
                    message="Observed state transition is not in the expected transition map.",
                    context={
                        "from": previous.state.value,
                        "to": event.state.value,
                        "previous_timestamp": previous.timestamp_iso,
                    },
                ))
        previous_by_cell[event.cell_id] = event
    return issues


def state_events_by_cell(events: Iterable[NormalizedEvent]) -> dict[str, list[NormalizedEvent]]:
    by_cell: dict[str, list[NormalizedEvent]] = defaultdict(list)
    for event in events:
        if event.kind == EventKind.STATE_CHANGED and event.state is not None:
            by_cell[event.cell_id].append(event)
    return dict(by_cell)
