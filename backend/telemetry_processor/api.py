from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')

from .pipeline import process_raw_events
from .simulator import get_simulator

_DEFAULT_DATA_FILE = Path(__file__).parent.parent.parent / "data" / "events.json"
DATA_FILE = Path(os.environ.get("TELEMETRY_DATA_FILE", str(_DEFAULT_DATA_FILE)))

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel

    app = FastAPI(
        title="Robot Cell Telemetry Processor",
        version="1.0.0",
        description="Normalizes raw robot cell telemetry and computes operational metrics.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    class ProcessTelemetryRequest(BaseModel):
        events: list[dict[str, Any]]

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/metrics")
    def get_metrics() -> dict[str, Any]:
        if not DATA_FILE.exists():
            raise HTTPException(status_code=404, detail=f"Data file not found: {DATA_FILE}")
        try:
            events = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Failed to read data file: {exc}") from exc
        try:
            return process_raw_events(events)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/metrics/live")
    def get_live_metrics() -> dict[str, Any]:
        return process_raw_events(get_simulator().get_events())

    @app.post("/process")
    def process_telemetry(request: ProcessTelemetryRequest) -> dict[str, Any]:
        try:
            return process_raw_events(request.events)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

except ImportError:  # pragma: no cover - enables importing package without API dependencies installed
    app = None
