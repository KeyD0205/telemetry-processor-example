import { CellMetrics } from '../types';
import { formatNumber, formatPercent, formatSeconds } from '../lib/format';
import { StateBadge } from './StateBadge';

export function CellComparison({ cells }: { cells: CellMetrics[] }) {
  return (
    <section className="card wide-card">
      <div className="section-title-row">
        <h2>Cell comparison</h2>
        <span className="muted">Operational view</span>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Cell</th>
              <th>Current state</th>
              <th>Program</th>
              <th>Availability</th>
              <th>Throughput/hr</th>
              <th>Avg cycle</th>
              <th>Fault time</th>
              <th>Data issues</th>
            </tr>
          </thead>
          <tbody>
            {cells.map((cell) => (
              <tr key={cell.cell_id}>
                <td><strong>{cell.cell_id}</strong></td>
                <td><StateBadge state={cell.current_state} /></td>
                <td>{cell.current_program_id ?? '—'}</td>
                <td>{formatPercent(cell.availability)}</td>
                <td>{formatNumber(cell.throughput_cycles_per_hour, 2)}</td>
                <td>{formatSeconds(cell.cycle_time_seconds.avg)}</td>
                <td>{formatSeconds(cell.fault_seconds)}</td>
                <td>{Object.values(cell.data_quality_issue_counts).reduce((sum, count) => sum + count, 0)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
