import { DataQualityIssue } from '../types';
import { formatDateTime } from '../lib/format';

export function DataQualityPanel({ issues }: { issues: DataQualityIssue[] }) {
  const warningsAndErrors = issues.filter((issue) => issue.severity !== 'info');
  const shown = warningsAndErrors.length ? warningsAndErrors : issues.slice(0, 6);

  return (
    <section className="card">
      <div className="section-title-row">
        <h2>Data quality</h2>
        <span className="muted">{issues.length} total findings</span>
      </div>
      {shown.length === 0 ? (
        <p className="empty-copy">No quality issues were detected.</p>
      ) : (
        <div className="quality-list">
          {shown.slice(0, 8).map((issue) => (
            <article className={`quality-item severity-${issue.severity}`} key={`${issue.code}-${issue.source_index}`}>
              <strong>{issue.code.replaceAll('_', ' ')}</strong>
              <p>{issue.message}</p>
              <span className="muted">{issue.cell_id ?? 'unknown cell'} · {formatDateTime(issue.timestamp)}</span>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
