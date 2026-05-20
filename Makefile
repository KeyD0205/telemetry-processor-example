.PHONY: test process api frontend

test:
	cd backend && pytest -q

process:
	PYTHONPATH=backend python -m telemetry_processor.cli data/events.json --output reports/metrics.json

api:
	cd backend && uvicorn telemetry_processor.api:app --reload --host 0.0.0.0 --port 8000

frontend:
	cd frontend && npm install && npm run dev
