import { useEffect, useState } from 'react';
import { Activity, Gauge, TimerReset, Wrench } from 'lucide-react';
import { TelemetryReport } from '../types';
import { formatDateTime, formatNumber, formatPercent, formatSeconds } from '../lib/format';
import { CellComparison } from './CellComparison';
import { DataQualityPanel } from './DataQualityPanel';
import { FaultList } from './FaultList';
import { MetricCard } from './MetricCard';
import { ThroughputChart } from './ThroughputChart';

const timeFormatter = new Intl.DateTimeFormat(undefined, {
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
});

function useNow(): Date {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(id);
  }, []);
  return now;
}

export function Dashboard({ report, fetchedAt }: { report: TelemetryReport; fetchedAt: Date }) {
  const now = useNow();
  const age = Math.floor((now.getTime() - fetchedAt.getTime()) / 1000);
  const ageLabel = age < 5 ? 'just now' : `${age}s ago`;

  return (
    <main className="dashboard-shell">
      <header className="hero">
        <div>
          <p className="eyebrow">Robot cell operations</p>
          <h1>Telemetry health dashboard</h1>
          <p className="hero-copy">
            Observed period {formatDateTime(report.window.start)} {'->'} {formatDateTime(report.window.end)} | {report.cell_count} cells | {report.normalized_event_count} normalized events
          </p>
        </div>
        <div className="hero-pill">
          <strong className="hero-pill-clock">{timeFormatter.format(now)}</strong>
          <span>updated {ageLabel}</span>
        </div>
      </header>

      <section className="metrics-grid">
        <MetricCard
          label="Fleet availability"
          value={<><Gauge size={24} /> {formatPercent(report.fleet.availability)}</>}
          helper={`${formatSeconds(report.fleet.uptime_seconds)} productive time`}
          intent={report.fleet.availability && report.fleet.availability >= 0.75 ? 'success' : 'warning'}
        />
        <MetricCard
          label="Completed cycles"
          value={<><Activity size={24} /> {report.fleet.completed_cycles}</>}
          helper={`${formatNumber(report.fleet.throughput_cycles_per_hour, 2)} cycles / cell-hour`}
        />
        <MetricCard
          label="Average cycle time"
          value={<><TimerReset size={24} /> {formatSeconds(report.fleet.cycle_time_seconds.avg)}</>}
          helper={`P95 ${formatSeconds(report.fleet.cycle_time_seconds.p95)}`}
        />
        <MetricCard
          label="Fault + maintenance time"
          value={<><Wrench size={24} /> {formatSeconds(report.fleet.fault_seconds + report.fleet.maintenance_seconds)}</>}
          helper={`${report.fleet.recent_faults.length} recent alerts`}
          intent={report.fleet.fault_seconds > 0 ? 'danger' : 'default'}
        />
      </section>

      <section className="content-grid">
        <CellComparison cells={report.cells} />
        <ThroughputChart buckets={report.fleet.throughput_over_time} />
        <FaultList faults={report.fleet.recent_faults} />
        <DataQualityPanel issues={report.data_quality.issues} />
      </section>
    </main>
  );
}
