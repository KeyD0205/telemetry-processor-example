import { useCallback, useEffect, useState } from 'react';
import processedReport from './mock/processed_metrics.json';
import { Dashboard } from './components/Dashboard';
import { EmptyState, ErrorState, LoadingState } from './components/LoadingState';
import { TelemetryReport } from './types';
import './styles/app.css';

const MOCK_LATENCY_MS = 500;
const POLL_INTERVAL_MS = 5000;
const USE_MOCK = import.meta.env['VITE_USE_MOCK'] !== 'false';

type LoadState =
  | { status: 'loading' }
  | { status: 'loaded'; report: TelemetryReport; fetchedAt: Date }
  | { status: 'empty' }
  | { status: 'error'; message: string };

async function loadReport(): Promise<TelemetryReport> {
  if (USE_MOCK) {
    // Mock path: set VITE_USE_MOCK=false in .env.local to hit the real API instead.
    await new Promise((resolve) => window.setTimeout(resolve, MOCK_LATENCY_MS));
    return processedReport as unknown as TelemetryReport;
  }
  const response = await fetch('/api/metrics/live');
  if (!response.ok) {
    throw new Error(`API responded with ${response.status}`);
  }
  return response.json() as Promise<TelemetryReport>;
}

export default function App() {
  const [state, setState] = useState<LoadState>({ status: 'loading' });

  const refresh = useCallback((showLoadingSpinner = false) => {
    if (showLoadingSpinner) setState({ status: 'loading' });
    loadReport()
      .then((report) => {
        if (!report.cells.length) {
          setState({ status: 'empty' });
          return;
        }
        setState({ status: 'loaded', report, fetchedAt: new Date() });
      })
      .catch((error: unknown) => {
        setState({
          status: 'error',
          message: error instanceof Error ? error.message : 'Unexpected error while loading telemetry.',
        });
      });
  }, []);

  useEffect(() => {
    refresh(true);
    if (USE_MOCK) return;
    const id = window.setInterval(() => refresh(false), POLL_INTERVAL_MS);
    return () => window.clearInterval(id);
  }, [refresh]);

  if (state.status === 'loading') return <LoadingState />;
  if (state.status === 'empty') return <EmptyState />;
  if (state.status === 'error') return <ErrorState message={state.message} onRetry={() => refresh(true)} />;
  return <Dashboard report={state.report} fetchedAt={state.fetchedAt} />;
}
