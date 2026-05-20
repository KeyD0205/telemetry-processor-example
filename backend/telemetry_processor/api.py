from __future__ import annotations

from typing import Any


import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')

from .pipeline import process_raw_events

try:
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel

    app = FastAPI(
        title="Robot Cell Telemetry Processor",
        version="1.0.0",
        description="Normalizes raw robot cell telemetry and computes operational metrics.",
    )

    class ProcessTelemetryRequest(BaseModel):
        events: list[dict[str, Any]]

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/process")
    def process_telemetry(request: ProcessTelemetryRequest) -> dict[str, Any]:
        try:
            return process_raw_events(request.events)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

except ImportError:  # pragma: no cover - enables importing package without API dependencies installed
    app = None
