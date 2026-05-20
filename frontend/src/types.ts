export type CellState =
  | 'sleep'
  | 'waiting_for_human'
  | 'running'
  | 'slowed'
  | 'paused'
  | 'stopped'
  | 'fault'
  | 'maintenance'
  | 'unknown';

export interface CycleTimeStats {
  avg: number | null;
  median?: number | null;
  p95: number | null;
  min?: number | null;
  max?: number | null;
}

export interface ThroughputBucket {
  bucket_start: string;
  completed_cycles: number;
}

export interface FaultEvent {
  cell_id: string;
  timestamp: string;
  state: CellState | null;
  codes: string[];
  messages: string[];
  program_id: string | null;
}

export interface CellMetrics {
  cell_id: string;
  window: {
    start: string;
    end: string;
    observed_seconds: number;
  };
  current_state: CellState;
  current_program_id: string | null;
  program_ids: string[];
  uptime_seconds: number;
  downtime_seconds: number;
  maintenance_seconds: number;
  fault_seconds: number;
  availability: number | null;
  productive_ratio_excluding_maintenance: number | null;
  throughput_cycles_per_hour: number | null;
  completed_cycles: number;
  cycle_time_seconds: CycleTimeStats;
  state_durations_seconds: Record<string, number>;
  throughput_over_time: ThroughputBucket[];
  fault_event_count: number;
  unique_fault_codes: string[];
  recent_faults: FaultEvent[];
  data_quality_issue_counts: Record<string, number>;
}

export interface DataQualityIssue {
  severity: 'info' | 'warning' | 'error';
  code: string;
  cell_id: string | null;
  timestamp: string | null;
  message: string;
  source_index: number | null;
  context: Record<string, unknown>;
}

export interface TelemetryReport {
  generated_at: string;
  event_count: number;
  normalized_event_count: number;
  dropped_event_count: number;
  cell_count: number;
  window: {
    start: string | null;
    end: string | null;
  };
  fleet: {
    completed_cycles: number;
    observed_cell_seconds: number;
    uptime_seconds: number;
    downtime_seconds: number;
    maintenance_seconds: number;
    fault_seconds: number;
    availability: number | null;
    throughput_cycles_per_hour: number | null;
    cycle_time_seconds: CycleTimeStats;
    throughput_over_time: ThroughputBucket[];
    recent_faults: FaultEvent[];
  };
  cells: CellMetrics[];
  data_quality: {
    issue_count: number;
    issues: DataQualityIssue[];
  };
}
