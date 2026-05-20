from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping


class EventKind(str, Enum):
    STATE_CHANGED = "state_changed"
    CYCLE_START = "cycle_start"
    CYCLE_END = "cycle_end"
    PRODUCTION_COUNT = "production_count"
    OPERATOR_ACTION = "operator_action"
    MAINTENANCE = "maintenance"
    UNKNOWN = "unknown"


class CellState(str, Enum):
    SLEEP = "sleep"
    WAITING_FOR_HUMAN = "waiting_for_human"
    RUNNING = "running"
    SLOWED = "slowed"
    PAUSED = "paused"
    STOPPED = "stopped"
    FAULT = "fault"
    MAINTENANCE = "maintenance"
    UNKNOWN = "unknown"


class ProgramState(str, Enum):
    PLAY = "play"
    PAUSE = "pause"
    STOP = "stop"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Fault:
    code: str
    message: str


@dataclass(frozen=True)
class NormalizedEvent:
    """Canonical event used by all downstream metric and UI logic."""

    event_id: str
    source_index: int
    cell_id: str
    timestamp: datetime
    timestamp_ns: int
    kind: EventKind
    state: CellState | None = None
    raw_state: str | None = None
    program_state: ProgramState | None = None
    program_id: str | None = None
    cycle_duration_seconds: float | None = None
    production_count: int | None = None
    faults: tuple[Fault, ...] = ()
    raw_event: Mapping[str, Any] = field(default_factory=dict, compare=False)

    @property
    def timestamp_iso(self) -> str:
        return self.timestamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class DataQualityIssue:
    severity: str
    code: str
    cell_id: str | None
    timestamp: str | None
    message: str
    source_index: int | None = None
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "code": self.code,
            "cell_id": self.cell_id,
            "timestamp": self.timestamp,
            "message": self.message,
            "source_index": self.source_index,
            "context": self.context,
        }
