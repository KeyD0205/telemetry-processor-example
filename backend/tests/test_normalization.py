from telemetry_processor.models import CellState, EventKind
from telemetry_processor.normalization import normalize_events


def test_normalizes_state_event_and_program_alias() -> None:
    raw = [{
        "cell_id": "cell-b",
        "event_time": {"sec": 1712480830, "nanosec": 0},
        "cell_status": {
            "cell_state": "op-program-running",
            "program_state": "play",
            "program_id": "BoxInspection",
            "cell_error_codes": [],
            "cell_error_messages": [],
        },
    }]

    events, issues = normalize_events(raw)

    assert len(events) == 1
    assert events[0].kind == EventKind.STATE_CHANGED
    assert events[0].state == CellState.RUNNING
    assert events[0].program_id == "Box_Inspection"
    assert any(issue.code == "normalized_program_id" for issue in issues)


def test_drops_exact_duplicate_events() -> None:
    event = {
        "cell_id": "cell-a",
        "event_time": {"sec": 1712480940, "nanosec": 0},
        "cell_status": {
            "cell_state": "op-program-running",
            "program_state": "play",
            "program_id": "PCB_Testing",
            "cell_error_codes": [],
            "cell_error_messages": [],
        },
    }

    events, issues = normalize_events([event, event])

    assert len(events) == 1
    assert any(issue.code == "duplicate_event" for issue in issues)


def test_records_out_of_order_events_but_sorts_them() -> None:
    raw = [
        {"cell_id": "cell-a", "event_time": {"sec": 20, "nanosec": 0}, "event_type": "cycle_end"},
        {"cell_id": "cell-a", "event_time": {"sec": 10, "nanosec": 0}, "event_type": "cycle_start"},
    ]

    events, issues = normalize_events(raw)

    assert [event.kind for event in events] == [EventKind.CYCLE_START, EventKind.CYCLE_END]
    assert any(issue.code == "out_of_order_event" for issue in issues)


def test_parses_production_count_aliases() -> None:
    raw = [{
        "cell_id": "cell-a",
        "event_time": {"sec": 30, "nanosec": 0},
        "event_type": "units_produced",
        "production": {"total": "42"},
    }]

    events, issues = normalize_events(raw)

    assert len(events) == 1
    assert events[0].kind == EventKind.PRODUCTION_COUNT
    assert events[0].production_count == 42
    assert not any(issue.code == "invalid_production_count" for issue in issues)


def test_flags_invalid_production_count() -> None:
    raw = [
        {
            "cell_id": "cell-a",
            "event_time": {"sec": 30, "nanosec": 0},
            "event_type": "production_count",
            "production_count": "not-a-number",
        },
        {
            "cell_id": "cell-a",
            "event_time": {"sec": 31, "nanosec": 0},
            "event_type": "production_count",
            "production_count": 3.7,
        },
    ]

    events, issues = normalize_events(raw)

    assert [event.kind for event in events] == [EventKind.PRODUCTION_COUNT, EventKind.PRODUCTION_COUNT]
    assert [event.production_count for event in events] == [None, None]
    assert sum(1 for issue in issues if issue.code == "invalid_production_count") == 2


def test_normalizes_operator_action_payload() -> None:
    raw = [{
        "cell_id": "cell-a",
        "event_time": {"sec": 40, "nanosec": 0},
        "event_type": "operator-action",
        "operator": {"action": "ack_fault"},
    }]

    events, issues = normalize_events(raw)

    assert len(events) == 1
    assert events[0].kind == EventKind.OPERATOR_ACTION
    assert events[0].operator_action == "ack_fault"
    assert not any(issue.code == "missing_operator_action" for issue in issues)
