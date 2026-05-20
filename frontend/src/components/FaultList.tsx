import { AlertTriangle } from 'lucide-react';
import { FaultEvent } from '../types';
import { formatDateTime } from '../lib/format';

export function FaultList({ faults }: { faults: FaultEvent[] }) {
  if (faults.length === 0) {
    return (
      <section className="card">
        <div className="section-title-row">
          <h2>Recent faults and alerts</h2>
        </div>
        <p className="empty-copy">No faults were detected in the current processing window.</p>
      </section>
    );
  }

  return (
    <section className="card fault-card">
      <div className="section-title-row">
        <h2>Recent faults and alerts</h2>
        <span className="muted">{faults.length} shown</span>
      </div>
      <div className="fault-list">
        {faults.map((fault) => (
          <article className="fault-item" key={`${fault.cell_id}-${fault.timestamp}-${fault.codes.join('-')}`}>
            <AlertTriangle size={18} />
            <div>
              <strong>{fault.cell_id} · {fault.codes.length ? fault.codes.join(', ') : 'Unknown code'}</strong>
              <p>{fault.messages.join(' ') || 'No fault message was provided.'}</p>
              <span className="muted">{formatDateTime(fault.timestamp)} · {fault.program_id ?? 'No program'}</span>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
