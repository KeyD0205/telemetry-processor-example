from __future__ import annotations

import random
import threading
import time
from collections import deque
from typing import Any

CELLS = ["cell-a", "cell-b"]
PROGRAMS = ["PCB_Testing", "Box_Inspection", "Welding_Arm", "Quality_Check"]
FAULT_SPECS = [
    ("E001", "Sensor timeout"),
    ("E002", "Arm position error"),
    ("E003", "Conveyor jam"),
    ("E101", "Emergency stop triggered"),
]

TICK_REAL_SECONDS = 3.0
SIM_SECONDS_PER_TICK = 30
HISTORY_SIM_SECONDS = 3 * 3600
MAX_EVENTS = 1000


class CellSim:
    def __init__(self, cell_id: str) -> None:
        self.cell_id = cell_id
        self.state = "running"
        self.program_id = random.choice(PROGRAMS)
        self.in_cycle = False
        self.cycle_start_ns: int | None = None

    def tick(self, sim_ns: int, dt_ns: int) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        sec = sim_ns // 1_000_000_000

        if self.state == "running":
            if not self.in_cycle and random.random() < 0.35:
                events.append(self._cycle_event(sec, "cycle_start"))
                self.in_cycle = True
                self.cycle_start_ns = sim_ns

            if self.in_cycle and self.cycle_start_ns is not None:
                if sim_ns - self.cycle_start_ns >= 60_000_000_000 and random.random() < 0.45:
                    duration = round((sim_ns - self.cycle_start_ns) / 1_000_000_000)
                    events.append(self._cycle_event(sec, "cycle_end", cycle_duration_seconds=duration))
                    self.in_cycle = False
                    self.cycle_start_ns = None

            if random.random() < 0.04:
                fault = random.choice(FAULT_SPECS)
                events.append(self._state_event(sec, "error-system-status", "stop", fault))
                self.state = "fault"
                self.in_cycle = False
                self.cycle_start_ns = None
            elif random.random() < 0.03:
                events.append(self._state_event(sec, "op-program-paused", "pause"))
                self.state = "paused"

        elif self.state == "fault":
            if random.random() < 0.55:
                events.append(self._state_event(sec, "op-program-running", "play"))
                self.state = "running"

        elif self.state == "paused":
            if random.random() < 0.65:
                events.append(self._state_event(sec, "op-program-running", "play"))
                self.state = "running"

        return events

    def _state_event(
        self,
        sec: int,
        cell_state: str,
        program_state: str,
        fault: tuple[str, str] | None = None,
    ) -> dict[str, Any]:
        return {
            "cell_id": self.cell_id,
            "event_time": {"sec": sec, "nanosec": 0},
            "cell_status": {
                "cell_state": cell_state,
                "program_state": program_state,
                "program_id": self.program_id,
                "cell_error_codes": [fault[0]] if fault else [],
                "cell_error_messages": [fault[1]] if fault else [],
            },
        }

    def _cycle_event(self, sec: int, event_type: str, **kwargs: Any) -> dict[str, Any]:
        event: dict[str, Any] = {
            "cell_id": self.cell_id,
            "event_time": {"sec": sec, "nanosec": 0},
            "event_type": event_type,
        }
        event.update(kwargs)
        return event


class FleetSimulator:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events: deque[dict[str, Any]] = deque()
        self._cells = {cell_id: CellSim(cell_id) for cell_id in CELLS}

        now_ns = int(time.time() * 1_000_000_000)
        self._sim_ns = now_ns - HISTORY_SIM_SECONDS * 1_000_000_000

        for cell in self._cells.values():
            self._events.append(
                cell._state_event(self._sim_ns // 1_000_000_000, "op-program-running", "play")
            )

        dt_ns = SIM_SECONDS_PER_TICK * 1_000_000_000
        for _ in range(HISTORY_SIM_SECONDS // SIM_SECONDS_PER_TICK):
            self._sim_ns += dt_ns
            for cell in self._cells.values():
                self._events.extend(cell.tick(self._sim_ns, dt_ns))

        self._trim()

        thread = threading.Thread(target=self._run, daemon=True)
        thread.start()

    def _trim(self) -> None:
        while len(self._events) > MAX_EVENTS:
            self._events.popleft()

    def _run(self) -> None:
        dt_ns = SIM_SECONDS_PER_TICK * 1_000_000_000
        while True:
            time.sleep(TICK_REAL_SECONDS)
            with self._lock:
                self._sim_ns += dt_ns
                for cell in self._cells.values():
                    self._events.extend(cell.tick(self._sim_ns, dt_ns))
                self._trim()

    def get_events(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._events)


_simulator: FleetSimulator | None = None
_init_lock = threading.Lock()


def get_simulator() -> FleetSimulator:
    global _simulator
    if _simulator is None:
        with _init_lock:
            if _simulator is None:
                _simulator = FleetSimulator()
    return _simulator
