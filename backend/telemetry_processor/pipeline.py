from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping


import logging
logger = logging.getLogger(__name__)

from .metrics import compute_metrics
from .models import DataQualityIssue, NormalizedEvent
from .normalization import normalize_events
from .state_machine import validate_state_transitions


def load_raw_events(path: str | Path) -> list[Mapping[str, Any]]:
    logger.info(f"Loading raw events from {path}")
    with Path(path).open("r", encoding="utf-8") as file:
        try:
            payload = json.load(file)
        except json.JSONDecodeError as exc:
            logger.error(f"Telemetry input is not valid JSON: {exc}")
            raise ValueError(f"Telemetry input is not valid JSON: {exc}") from exc
    if not isinstance(payload, list):
        logger.error("Telemetry input must be a JSON array of event objects.")
        raise ValueError("Telemetry input must be a JSON array of event objects.")
    if not all(isinstance(item, dict) for item in payload):
        logger.error("Every telemetry event must be a JSON object.")
        raise ValueError("Every telemetry event must be a JSON object.")
    logger.info(f"Loaded {len(payload)} raw events from {path}")
    return payload


def process_raw_events(raw_events: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    logger.info("Normalizing events...")
    normalized_events, normalization_issues = normalize_events(raw_events)
    logger.info(f"Normalized {len(normalized_events)} events, {len(normalization_issues)} normalization issues found.")
    logger.info("Validating state transitions...")
    transition_issues = validate_state_transitions(normalized_events)
    logger.info(f"State transition validation complete, {len(transition_issues)} issues found.")
    logger.info("Computing metrics...")
    metrics, metric_issues = compute_metrics(normalized_events)
    logger.info(f"Metrics computed, {len(metric_issues)} metric issues found.")
    all_issues = normalization_issues + transition_issues + metric_issues
    metrics["data_quality"] = {
        "issue_count": len(all_issues),
        "issues": [issue.to_dict() for issue in all_issues],
    }
    metrics["normalized_event_count"] = len(normalized_events)
    metrics["dropped_event_count"] = sum(1 for issue in all_issues if issue.code in {"duplicate_event", "missing_cell_id", "missing_event_time", "invalid_event_time"})
    logger.info("Processing complete.")
    return metrics


def process_file(input_path: str | Path) -> dict[str, Any]:
    return process_raw_events(load_raw_events(input_path))


def write_json_report(report: Mapping[str, Any], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=2, sort_keys=False)
        file.write("\n")
