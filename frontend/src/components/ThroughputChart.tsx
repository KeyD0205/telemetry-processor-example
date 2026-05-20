import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { ThroughputBucket } from '../types';
import { formatChartTime } from '../lib/format';

export function ThroughputChart({ buckets }: { buckets: ThroughputBucket[] }) {
  if (buckets.length === 0) {
    return (
      <section className="card">
        <h2>Throughput over time</h2>
        <p className="empty-copy">No completed cycles were found for this window.</p>
      </section>
    );
  }

  const data = buckets.map((bucket) => ({
    label: formatChartTime(bucket.bucket_start),
    completedCycles: bucket.completed_cycles,
  }));

  return (
    <section className="card chart-card">
      <div className="section-title-row">
        <h2>Throughput over time</h2>
        <span className="muted">Completed cycles per hour bucket</span>
      </div>
      <div className="chart-fill">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 12, right: 16, left: 0, bottom: 12 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="label" tick={{ fontSize: 12 }} />
            <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
            <Tooltip />
            <Bar dataKey="completedCycles" fill="#2563eb" maxBarSize={40} radius={[8, 8, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
