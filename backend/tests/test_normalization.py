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
