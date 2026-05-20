# Robot Cell Telemetry Processing Assignment

This is a full-stack implementation of the telemetry assignment. It includes:

- a backend telemetry pipeline that ingests raw robot-cell events, normalizes them into a canonical model, computes metrics, and produces CLI/API/JSON output;
- tests for the most important normalization and metric logic;
- a frontend dashboard that presents current state, operational metrics, recent faults, throughput over time, cell comparison, loading states, empty states, and data-quality handling;
- a summary report and dashboard screenshot preview.

<img width="1276" height="851" alt="image" src="https://github.com/user-attachments/assets/545607cd-fe28-4e3f-a895-b85219970f41" />


## Repository structure

```text
.
|-- backend/
|   |-- telemetry_processor/
|   |   |-- api.py               # FastAPI endpoints
|   |   |-- cli.py               # CLI renderer
|   |   |-- metrics.py           # metric and cycle-pairing logic
|   |   |-- models.py            # canonical event model
|   |   |-- normalization.py     # schema drift and naming normalization
|   |   |-- pipeline.py          # ingestion orchestration
|   |   |-- simulator.py         # synthetic fleet simulator for live demo
|   |   `-- state_machine.py     # canonical states and transitions
|   |-- tests/
|   `-- pyproject.toml
|-- data/events.json             # assignment event stream for private submission
|-- frontend/
|   |-- src/
|   |   |-- components/          # dashboard components
|   |   |-- mock/                # processed metrics used by UI demo
|   |   `-- types.ts
|   `-- package.json
|-- reports/metrics.json         # generated backend report
|-- screenshots/dashboard-preview.png
|-- SUMMARY_REPORT.md
`-- Makefile
```

## Backend setup

From the repository root:

macOS/Linux:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

Windows PowerShell:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -m pytest -q
```

Expected test result:

```text
14 passed
```

## Run the processing pipeline

macOS/Linux:

```bash
PYTHONPATH=backend python -m telemetry_processor.cli data/events.json
```

Windows PowerShell:

```powershell
$env:PYTHONPATH = "backend"
python -m telemetry_processor.cli data/events.json
```

Write the full JSON report:

macOS/Linux:

```bash
PYTHONPATH=backend python -m telemetry_processor.cli data/events.json --format json --output reports/metrics.json
```

Windows PowerShell:

```powershell
$env:PYTHONPATH = "backend"
python -m telemetry_processor.cli data/events.json --format json --output reports/metrics.json
```

Or use the Makefile on systems with `make` available:

```bash
make test
make process
```

## Run the API

```bash
cd backend
uvicorn telemetry_processor.api:app --reload --host 0.0.0.0 --port 8000
```

The API exposes:

- `GET /health`
- `GET /metrics` - processes `data/events.json` and returns the full report
- `GET /metrics/live` - returns metrics from the in-memory fleet simulator (see below)
- `POST /process` - processes a caller-supplied event array

Example request body for `POST /process`:

```json
{
  "events": [
    {
      "cell_id": "cell-a",
      "event_time": { "sec": 1712480520, "nanosec": 0 },
      "event_type": "cycle_start"
    }
  ]
}
```

## Live simulator

`telemetry_processor/simulator.py` runs a synthetic two-cell fleet in a background thread. On startup it seeds three hours of simulated history, then appends new events every three real seconds (each tick advances the simulation clock by 30 seconds). The event log is capped at 1 000 entries; the oldest events are evicted as new ones arrive.

This simulator is demo-only. It is intentionally useful for showing a changing dashboard, but it is not production-like: it is random, singleton-backed, starts a thread implicitly when the live endpoint is first used, and does not currently have seed- or invariant-based tests. Production ingestion should use an explicit event source and deterministic state handling. Tests for simulator behavior should use a fixed seed and assert core invariants such as monotonic timestamps, valid transitions, bounded log size, and complete cycle pairs where expected.

Each cell follows a simple probabilistic state machine:

| From state | Possible transitions | Notes |
| --- | --- | --- |
| `running` | `running` -> fault (4 % / tick) | fault code drawn from E001-E101 |
| `running` | `running` -> paused (3 % / tick) | |
| `running` | cycle start (35 % / tick, if no active cycle) | |
| `running` | cycle end (45 % / tick, once cycle is >= 60 s old) | duration derived from timestamps |
| `fault` | `fault` -> running (55 % / tick) | |
| `paused` | `paused` -> running (65 % / tick) | |

`GET /metrics/live` runs the accumulated event log through the same normalization and metric pipeline as the static endpoint, so availability, cycle times, fault counts, and the throughput chart all update on each frontend poll.

The frontend connects to this endpoint when `VITE_USE_MOCK=false` is set in `frontend/.env.local`. The dashboard polls every five seconds; each poll produces genuinely different numbers as new events accumulate.

## Run the frontend dashboard

```bash
cd frontend
npm install
npm run dev
```

The dashboard connects to `GET /metrics/live` and polls every five seconds. Start the API first (see above), then start the frontend. No additional configuration is needed - the Vite dev server proxies `/api/*` to `http://localhost:8000`.

To use static mock data instead (no backend required), set `VITE_USE_MOCK=true` in `frontend/.env.local`. The mock frontend report mirrors the backend JSON contract and is used only in this mock mode.

### Frontend tests

```bash
cd frontend
npm test
```

Expected result:

```text
8 passed
```

A preview screenshot is available at:

```text
screenshots/dashboard-preview.png
```

## Canonical event model

Raw events are normalized into `NormalizedEvent`:

| Field | Purpose |
| --- | --- |
| `event_id` | Stable hash of canonical raw payload, used for duplicate detection |
| `source_index` | Input order for traceability and deterministic sorting ties |
| `cell_id` | Robot cell identity |
| `timestamp` / `timestamp_ns` | UTC event time, nanosecond-aware |
| `kind` | `state_changed`, `cycle_start`, `cycle_end`, `production_count`, `operator_action`, `maintenance`, `unknown` |
| `state` | Canonical state for status events |
| `program_state` | `play`, `pause`, `stop`, `unknown` |
| `program_id` | Normalized program id, for example `BoxInspection` -> `Box_Inspection` |
| `cycle_duration_seconds` | Optional reported duration on cycle end |
| `production_count` | Optional count from `production_count` events, treated separately from cycle-derived throughput |
| `operator_action` | Optional normalized action label from operator-action events |
| `faults` | Structured fault code/message pairs |
| `raw_event` | Original event for auditability |

## Canonical cell states and transitions

The pipeline maps vendor- or robot-specific state names into operational states:

| Raw examples | Canonical state | Metric treatment |
| --- | --- | --- |
| `sleep` | `sleep` | downtime |
| `td-waiting-for-human` | `waiting_for_human` | downtime |
| `op-program-running` | `running` | uptime |
| `op-human-in-slow-zone` | `slowed` | uptime, but visible as degraded state |
| `op-program-paused` | `paused` | downtime |
| `op-human-in-stop-zone` | `stopped` | downtime |
| `error-system-status`, `anomaly` | `fault` | downtime and fault time |
| `mt-human-in-stop-zone` | `maintenance` | maintenance time |

The state machine is intentionally permissive because real telemetry can skip intermediate states. Unexpected transitions are captured as quality warnings rather than hard failures.

## Handling imperfect data

### Duplicate events

Exact duplicate raw payloads are identified using a stable SHA-256 hash of the canonical JSON payload. Duplicates are dropped and recorded as `duplicate_event` quality findings.

### Out-of-order events

Events are checked against ingestion order per cell. If a later-arriving event has an earlier timestamp, the pipeline records `out_of_order_event`. Downstream processing sorts by `(cell_id, timestamp_ns, source_index)` so metrics are deterministic.

### Missing events

Cycle metrics are derived by pairing `cycle_start` with the next `cycle_end` for the same cell. The pipeline records:

- `cycle_end_without_start`
- `cycle_start_without_end`
- `cycle_start_without_previous_end`

If `cycle_duration_seconds` is missing on `cycle_end`, the backend derives duration from timestamps and records `missing_cycle_duration`.

### Inconsistent event naming and schema drift

The normalizer maps aliases such as `cycle-start`, `cycle_begin`, and `cycleStart` into `cycle_start`, and state aliases into canonical states. Program ids are canonicalized where known, for example `BoxInspection` -> `Box_Inspection`. Unknown names do not crash the job; they become `unknown_*` findings.

Production-count aliases such as `production_count`, `produced_count`, and `units_produced` are parsed into `NormalizedEvent.production_count` when an integer count is present. Fractional, invalid, missing, or negative count values are kept out of metrics and reported as data-quality findings. Operator-action aliases are normalized into `NormalizedEvent.operator_action` when an action payload such as `action`, `action_type`, or `operator.action` is present; events without an action payload are still counted for auditability.

## Metrics calculated

At cell and fleet level:

- current cell state;
- uptime seconds;
- downtime seconds;
- maintenance seconds;
- fault seconds;
- availability;
- productive ratio excluding maintenance;
- completed cycles;
- throughput in cycles per observed cell-hour;
- production-count events, latest production count, produced-unit delta, and counter resets when production-count events are present;
- operator-action event count, currently used as an audit/annotation signal rather than an operational metric;
- cycle-time average, median, p95, min, max;
- throughput over time;
- recent faults and unique fault codes;
- state-duration breakdown;
- data-quality issue counts.

For the provided stream, the backend produces these headline results:

| Metric | Value |
| --- | ---: |
| Normalized events | 24 |
| Dropped exact duplicates | 1 |
| Cells | 2 |
| Fleet completed cycles | 5 |
| Fleet availability | 65.5% |
| Fleet average cycle time | 80s |
| Fleet p95 cycle time | 114s |
| Fleet fault time | 180s |

## Data-quality issues found in the provided stream

Notable findings include:

- one exact duplicate status event for `cell-a`;
- one out-of-order `cycle_start` for `cell-a`;
- a reported cycle duration mismatch for `cell-a` where timestamps imply 120s but payload reports 110s;
- one `cycle_end` missing `cycle_duration_seconds` for `cell-b`; duration was derived as 60s;
- program id drift: `BoxInspection` normalized to `Box_Inspection`;
- several raw cell states normalized into canonical states;
- one cycle start observed while the last known state was non-productive, which is kept as a warning because the raw stream may be missing an intervening running state.

## Assumptions and tradeoffs

- The timestamp is the source of truth for ordering and duration calculations.
- Reported `cycle_duration_seconds` is retained for audit, but timestamp-derived duration is used for metrics when a complete start/end pair exists.
- Uptime includes `running` and `slowed`; slowed is still productive but visible to operators as degraded.
- Fault and non-fault downtime are separated so operations can distinguish safety stops, waiting, pauses, and faults.
- Cycle-derived throughput and production-count metrics are intentionally separate. Cycle pairs describe process completion and cycle time; production-count events describe produced units or cumulative counters when the source stream provides them.
- Production counters are treated as cumulative per cell. Positive deltas are counted as observed produced units; counter drops are reported as resets and are not bridged.
- Operator actions are normalized and counted, but the current source stream does not define action payload semantics, so they are not used to change cell state or availability.
- Maintenance time is measured from canonical maintenance states such as `mt-human-in-stop-zone`. Standalone `maintenance` events are normalized, but they would need explicit start/end semantics or a state mapping before they could change maintenance-duration metrics.
- The final known state is carried forward until the last event timestamp for that cell. No duration is inferred beyond the processing window.
- Duplicate detection currently drops exact raw duplicates only. Near-duplicates are better handled with source event ids or device sequence numbers in production.
- The frontend uses generated processed data rather than recalculating in the browser. This avoids metric drift between backend and UI.

## Production architecture note

A production-ready system would split ingestion, normalization, metric derivation, serving, and UI into independently scalable parts:

```text
Robot cells
  -> gateway / collector
  -> durable log such as Kafka, Redpanda, Kinesis, or Pub/Sub
  -> schema validation + normalization service
  -> append-only normalized event store
  -> stream processor for live metrics
  -> warehouse/lakehouse for recomputation
  -> metrics read models and dashboard API
  -> operator dashboard + engineering analysis tools
```

### Near real-time ingestion

Use a durable event log partitioned by `cell_id`. Consumers normalize events, deduplicate by source id or canonical hash, and update a per-cell state store. The dashboard can receive updates through WebSockets, Server-Sent Events, or polling a low-latency read model.

### Larger event volumes

Partition by `cell_id`, use batch writes to object storage or a warehouse, keep hot state in Redis/RocksDB, and compute aggregates incrementally. The core functions in this repository are pure and deterministic, which makes them suitable for both stream processors and batch recomputation.

### Historical recomputation

Keep raw immutable events and version the normalization rules. For recomputation, replay raw events through a selected ruleset version into a new metrics table. This prevents accidental changes to historical numbers without an explicit backfill.

### Multiple robot types

Introduce schema adapters per robot type. Each adapter converts raw vendor events into the same `NormalizedEvent` contract. Metrics and UI remain mostly unchanged because they depend on the canonical model.

## Public duplicate note

The included `data/events.json` is part of the private assignment submission. If publishing a public duplicate of this project, remove the provided dataset and generated metrics based on it. Use synthetic data generated from scratch instead.
