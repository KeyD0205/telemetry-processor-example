# Alias maps for normalization logic
# This file centralizes all normalization alias dictionaries for easier maintenance and testing.

from .models import EventKind, CellState, ProgramState

EVENT_NAME_ALIASES: dict[str, EventKind] = {
    "cycle_start": EventKind.CYCLE_START,
    "cyclestart": EventKind.CYCLE_START,
    "cycle-start": EventKind.CYCLE_START,
    "cycle_begin": EventKind.CYCLE_START,
    "cycle_started": EventKind.CYCLE_START,
    "cycle_end": EventKind.CYCLE_END,
    "cycleend": EventKind.CYCLE_END,
    "cycle-finish": EventKind.CYCLE_END,
    "cycle_finished": EventKind.CYCLE_END,
    "production_count": EventKind.PRODUCTION_COUNT,
    "production-count": EventKind.PRODUCTION_COUNT,
    "productioncount": EventKind.PRODUCTION_COUNT,
    "produced_count": EventKind.PRODUCTION_COUNT,
    "units_produced": EventKind.PRODUCTION_COUNT,
    "operator_action": EventKind.OPERATOR_ACTION,
    "operator-action": EventKind.OPERATOR_ACTION,
    "operatoraction": EventKind.OPERATOR_ACTION,
    "maintenance": EventKind.MAINTENANCE,
}

STATE_ALIASES: dict[str, CellState] = {
    "sleep": CellState.SLEEP,
    "td-waiting-for-human": CellState.WAITING_FOR_HUMAN,
    "waiting-for-human": CellState.WAITING_FOR_HUMAN,
    "op-program-running": CellState.RUNNING,
    "program-running": CellState.RUNNING,
    "running": CellState.RUNNING,
    "op-human-in-slow-zone": CellState.SLOWED,
    "human-in-slow-zone": CellState.SLOWED,
    "slow-zone": CellState.SLOWED,
    "op-human-in-stop-zone": CellState.STOPPED,
    "human-in-stop-zone": CellState.STOPPED,
    "op-program-paused": CellState.PAUSED,
    "paused": CellState.PAUSED,
    "error-system-status": CellState.FAULT,
    "anomaly": CellState.FAULT,
    "fault": CellState.FAULT,
    "error": CellState.FAULT,
    "mt-human-in-stop-zone": CellState.MAINTENANCE,
    "maintenance": CellState.MAINTENANCE,
}

PROGRAM_STATE_ALIASES: dict[str, ProgramState] = {
    "play": ProgramState.PLAY,
    "running": ProgramState.PLAY,
    "pause": ProgramState.PAUSE,
    "paused": ProgramState.PAUSE,
    "stop": ProgramState.STOP,
    "stopped": ProgramState.STOP,
}

PROGRAM_ID_ALIASES: dict[str, str] = {
    "boxtesting": "Box_Testing",
    "boxinspection": "Box_Inspection",
    "box_inspection": "Box_Inspection",
    "pcbtesting": "PCB_Testing",
    "pcb_testing": "PCB_Testing",
}
