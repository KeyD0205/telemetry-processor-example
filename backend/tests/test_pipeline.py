import json
from pathlib import Path

from telemetry_processor.pipeline import process_file, process_raw_events

ROOT = Path(__file__).resolve().parents[2]
DATA_FILE = ROOT / "data" / "events.json"


def test_processes_assignment_dataset_with_expected_metrics() -> None:
    report = process_file(DATA_FILE)

    assert report["cell_count"] == 2
    assert report["normalized_event_count"] == 24  # one exact duplicate is dropped
    assert report["fleet"]["completed_cycles"] == 5
    assert report["fleet"]["cycle_time_seconds"]["avg"] == 80.0

    cell_a = next(cell for cell in report["cells"] if cell["cell_id"] == "cell-a")
    cell_b = next(cell for cell in report["cells"] if cell["cell_id"] == "cell-b")

    assert cell_a["current_state"] == "running"
    assert cell_a["completed_cycles"] == 3
    assert cell_a["uptime_seconds"] == 540.0
    assert cell_a["downtime_seconds"] == 240.0
    assert cell_a["cycle_time_seconds"]["avg"] == 90.0
    assert cell_a["unique_fault_codes"] == ["E-1001", "E-2003"]

    assert cell_b["current_state"] == "maintenance"
    assert cell_b["completed_cycles"] == 2
    assert cell_b["cycle_time_seconds"]["avg"] == 65.0
    assert cell_b["unique_fault_codes"] == ["A-500"]


def test_detects_duration_mismatch_missing_duration_and_bad_cycle_state() -> None:
    report = process_file(DATA_FILE)
    issue_codes = {issue["code"] for issue in report["data_quality"]["issues"]}

    assert "duplicate_event" in issue_codes
    assert "out_of_order_event" in issue_codes
    assert "cycle_duration_mismatch" in issue_codes
    assert "missing_cycle_duration" in issue_codes
    assert "normalized_program_id" in issue_codes
    assert "cycle_started_while_not_productive" in issue_codes


def test_cycle_end_without_start_is_reported() -> None:
    raw = [
        {"cell_id": "cell-x", "event_time": {"sec": 1, "nanosec": 0}, "event_type": "cycle_end"},
    ]

    report = process_raw_events(raw)

    assert report["fleet"]["completed_cycles"] == 0
    assert any(issue["code"] == "cycle_end_without_start" for issue in report["data_quality"]["issues"])


def test_availability_is_uptime_over_observed_seconds() -> None:
    # 120 s running, then 60 s fault -> observed = 180 s, uptime = 120 s, availability approximately 0.6667
    raw = [
        {
            "cell_id": "cell-x",
            "event_time": {"sec": 0, "nanosec": 0},
            "cell_status": {"cell_state": "op-program-running", "program_state": "play",
                            "program_id": "", "cell_error_codes": [], "cell_error_messages": []},
        },
        {
            "cell_id": "cell-x",
            "event_time": {"sec": 120, "nanosec": 0},
            "cell_status": {"cell_state": "error-system-status", "program_state": "stop",
                            "program_id": "", "cell_error_codes": ["E1"], "cell_error_messages": ["err"]},
        },
        {
            "cell_id": "cell-x",
            "event_time": {"sec": 180, "nanosec": 0},
            "cell_status": {"cell_state": "op-program-running", "program_state": "play",
                            "program_id": "", "cell_error_codes": [], "cell_error_messages": []},
        },
    ]

    report = process_raw_events(raw)
    cell = report["cells"][0]

    assert cell["uptime_seconds"] == 120.0
    assert cell["fault_seconds"] == 60.0
    assert abs(cell["availability"] - round(120 / 180, 4)) < 1e-6


def test_unexpected_state_transition_produces_quality_warning() -> None:
    from telemetry_processor.normalization import normalize_events
    from telemetry_processor.state_machine import validate_state_transitions

    # sleep -> fault is an allowed transition; sleep -> paused is not
    raw = [
        {
            "cell_id": "cell-x",
            "event_time": {"sec": 0, "nanosec": 0},
            "cell_status": {"cell_state": "sleep", "program_state": "stop",
                            "program_id": "", "cell_error_codes": [], "cell_error_messages": []},
        },
        {
            "cell_id": "cell-x",
            "event_time": {"sec": 10, "nanosec": 0},
            "cell_status": {"cell_state": "op-program-paused", "program_state": "pause",
                            "program_id": "", "cell_error_codes": [], "cell_error_messages": []},
        },
    ]

    events, _ = normalize_events(raw)
    issues = validate_state_transitions(events)

    assert any(issue.code == "unexpected_state_transition" for issue in issues)


def test_api_health_endpoint() -> None:
    from fastapi.testclient import TestClient
    from telemetry_processor.api import app

    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_production_counts_are_reported_separately_from_cycles() -> None:
    raw = [
        {"cell_id": "cell-a", "event_time": {"sec": 0, "nanosec": 0}, "event_type": "production_count", "production_count": 10},
        {"cell_id": "cell-a", "event_time": {"sec": 60, "nanosec": 0}, "event_type": "production_count", "production_count": 14},
        {"cell_id": "cell-a", "event_time": {"sec": 120, "nanosec": 0}, "event_type": "operator_action"},
        {"cell_id": "cell-a", "event_time": {"sec": 180, "nanosec": 0}, "event_type": "production_count", "production_count": 3},
        {"cell_id": "cell-a", "event_time": {"sec": 240, "nanosec": 0}, "event_type": "production_count", "production_count": 8},
    ]

    report = process_raw_events(raw)
    cell = report["cells"][0]
    issue_codes = {issue["code"] for issue in report["data_quality"]["issues"]}

    assert report["fleet"]["completed_cycles"] == 0
    assert report["fleet"]["production_count_events"] == 4
    assert report["fleet"]["latest_production_count_total"] == 8
    assert report["fleet"]["produced_units_delta"] == 9
    assert report["fleet"]["operator_action_count"] == 1
    assert cell["production_count_events"] == 4
    assert cell["latest_production_count"] == 8
    assert cell["produced_units_delta"] == 9
    assert cell["production_count_resets"] == 1
    assert cell["operator_action_count"] == 1
    assert "production_count_reset" in issue_codes


def test_api_process_endpoint_returns_metrics() -> None:
    from fastapi.testclient import TestClient
    from telemetry_processor.api import app

    client = TestClient(app)
    payload = {
        "events": [
            {"cell_id": "cell-a", "event_time": {"sec": 0, "nanosec": 0},
             "cell_status": {"cell_state": "op-program-running", "program_state": "play",
                             "program_id": "PCB_Testing", "cell_error_codes": [], "cell_error_messages": []}},
            {"cell_id": "cell-a", "event_time": {"sec": 60, "nanosec": 0}, "event_type": "cycle_start"},
            {"cell_id": "cell-a", "event_time": {"sec": 120, "nanosec": 0},
             "event_type": "cycle_end", "cycle_duration_seconds": 60},
        ]
    }

    response = client.post("/process", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["fleet"]["completed_cycles"] == 1
    assert data["cells"][0]["cycle_time_seconds"]["avg"] == 60.0
