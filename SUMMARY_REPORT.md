# Summary Report

## Approach

I implemented the solution as a small full-stack telemetry product rather than a single script. The central design choice is a canonical event model: raw events are ingested once, normalized into a stable representation, and all metrics and UI views depend on that model.

This keeps the solution easy to reason about during an interview because the event flow is explicit:

```text
raw JSON events
  → validation and normalization
  → duplicate/out-of-order/schema-drift detection
  → canonical event stream sorted by cell and time
  → state-duration and cycle-pairing logic
  → JSON metrics report
  → CLI / API / dashboard
```

The implementation is intentionally deterministic and side-effect free in the core pipeline. The same functions can be used for command-line processing, API requests, tests, stream processing, or historical recomputation.

## What was built

### Universal section

- Ingests the JSON telemetry stream.
- Defines a canonical `NormalizedEvent` model.
- Normalizes inconsistent states, event names, program ids, timestamps, and fault fields.
- Defines canonical cell states and transition validation.
- Handles duplicate events, missing events, out-of-order events, inconsistent naming, schema drift, and missing fields.
- Calculates uptime, downtime, throughput, cycle time, fault time, maintenance time, availability, state durations, recent faults, and data-quality issue counts.
- Includes tests for normalization, duplicate removal, out-of-order sorting, metric output, cycle-pairing edge cases, and issue detection.
- Includes an architecture note for production evolution.

### Backend section

- Python package under `backend/telemetry_processor`.
- CLI output via `python -m telemetry_processor.cli`.
- JSON report generation to `reports/metrics.json`.
- FastAPI endpoint at `POST /process`.
- Clear separation between normalization, state-machine logic, metric calculation, and delivery interfaces.

### Frontend section

- React/Vite dashboard under `frontend`.
- Shows current cell state, fleet metrics, cell comparison, throughput over time, recent faults, loading/empty/error states, and data quality findings.
- Uses backend-generated processed data as the mocked UI data source, keeping calculations centralized in the backend.

## Key results from the provided telemetry stream

| Result | Value |
| --- | ---: |
| Raw events | 25 |
| Normalized events after duplicate removal | 24 |
| Dropped exact duplicates | 1 |
| Cells detected | 2 |
| Completed cycles | 5 |
| Fleet availability | 65.5% |
| Fleet average cycle time | 80s |
| Fleet p95 cycle time | 114s |
| Fleet fault time | 180s |
| Cell A completed cycles | 3 |
| Cell B completed cycles | 2 |

## Data-quality challenges and handling

### Duplicate events

One exact duplicate status event was detected for `cell-a`. It is dropped using a stable canonical payload hash and recorded as a warning.

### Out-of-order timestamps

A `cell-a` `cycle_start` arrived after later events in the input array. The pipeline records the out-of-order arrival and sorts events by event time before computing metrics.

### Missing cycle duration

One `cell-b` `cycle_end` does not include `cycle_duration_seconds`. Because it has a matching `cycle_start`, the pipeline derives duration from timestamps.

### Inconsistent cycle duration

One `cell-a` cycle reports 110 seconds, while event timestamps imply 120 seconds. The report keeps the raw value for audit but uses timestamp-derived duration as the metric source of truth.

### Inconsistent naming

`BoxInspection` is normalized to `Box_Inspection`. Vendor-style cell states such as `op-program-running`, `op-human-in-stop-zone`, and `mt-human-in-stop-zone` are normalized into canonical operational states.

### Missing state transitions

A `cycle_start` occurs while the last known state is fault. This is marked as a data-quality warning rather than rejected, because the stream may be missing a running-state event.

## Architecture note

For a production system, I would evolve this into an event-driven architecture:

```text
robot cell telemetry
  → edge collector / gateway
  → durable event log partitioned by cell_id
  → normalization service with schema adapters
  → immutable raw event store
  → normalized event store
  → stream metrics processor
  → real-time read model for dashboards
  → historical warehouse for recomputation and analytics
```

### Near real-time ingestion

Use a durable log such as Kafka, Redpanda, Kinesis, or Pub/Sub. Partition by `cell_id` so each cell's ordering can be handled independently. Maintain per-cell state in a stream processor and update a low-latency read model for the dashboard.

### Larger volumes

Scale horizontally by partitioning on `cell_id`, batching writes, and separating hot operational metrics from cold historical data. Store immutable raw events in object storage for replay and auditing. Aggregate metrics can be materialized at several granularities, for example minute, hour, shift, day, and program.

### Historical recomputation

Version schema adapters and normalization rules. Recompute by replaying raw events through a selected version into a new metrics table. This allows safe backfills and reproducibility when definitions change.

### Multiple robot types

Add robot-specific adapters that map vendor events into the same canonical event model. The metric logic and dashboard do not need to know the source robot type once events are normalized.

## Recommendations for further automation and scalability

- Add source event ids or monotonic device sequence numbers to improve deduplication and ordering.
- Add explicit cycle ids to avoid ambiguous cycle pairing.
- Add event-watermark handling for late events in real-time mode.
- Add severity levels and lifecycle tracking for fault open/resolved intervals.
- Add shift calendars and planned-maintenance windows so OEE-style metrics can separate scheduled and unscheduled downtime.
- Add configurable robot-type adapters loaded from schema registry metadata.
- Add dashboard filters for site, robot type, program, time range, and alert severity.
- Add operator-oriented alert thresholds, for example cycle-time p95 regression or repeated stop-zone entries.
- Add engineering views for raw event trace, state-transition timeline, and normalization audit trail.

## Tradeoffs

- Exact duplicate detection is implemented now; fuzzy duplicate detection would require stronger source identifiers to avoid dropping legitimate repeated status events.
- Timestamp-derived cycle time is used as the metric source of truth, even when reported duration exists. This is more consistent but assumes event timestamps are reliable.
- The final known state is carried only until the last event timestamp in the cell's window. The system does not infer time beyond observed data.
- The frontend uses processed mock data. This is appropriate for the assignment because the backend owns the metric logic, but production should fetch from a metrics API or subscribe to live updates.
