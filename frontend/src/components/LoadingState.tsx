export function LoadingState() {
  return (
    <div className="state-panel" role="status" aria-live="polite">
      <div className="spinner" />
      <div>
        <h2>Loading telemetry</h2>
        <p>Preparing dashboard metrics from the processed event stream.</p>
      </div>
    </div>
  );
}

export function EmptyState() {
  return (
    <div className="state-panel">
      <h2>No telemetry available</h2>
      <p>Upload or ingest events to see cell states, throughput, faults, and quality findings.</p>
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="state-panel state-panel-error">
      <h2>Could not load telemetry</h2>
      <p>{message}</p>
      <button className="button" onClick={onRetry}>Retry</button>
    </div>
  );
}
