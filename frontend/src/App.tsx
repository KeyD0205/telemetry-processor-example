import { useCallback, useEffect, useState } from 'react';
import processedReport from './mock/processed_metrics.json';
import { Dashboard } from './components/Dashboard';
import { EmptyState, ErrorState, LoadingState } from './components/LoadingState';
import { TelemetryReport } from './types';
import './styles/app.css';

const MOCK_LATENCY_MS = 500;

type LoadState =
  | { status: 'loading' }
  | { status: 'loaded'; report: TelemetryReport }
  | { status: 'empty' }
  | { status: 'error'; message: string };

async function loadReport(): Promise<TelemetryReport> {
  if (import.meta.env['VITE_USE_MOCK'] !== 'false') {
    // Mock path: set VITE_USE_MOCK=false in .env to hit the real API instead.
    await new Promise((resolve) => window.setTimeout(resolve, MOCK_LATENCY_MS));
    return processedReport as unknown as TelemetryReport;
  }
  const response = await fetch('/api/process', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ events: [] }),
  });
  if (!response.ok) {
    throw new Error(`API responded with ${response.status}`);
  }
  return response.json() as Promise<TelemetryReport>;
}

export default function App() {
  const [state, setState] = useState<LoadState>({ status: 'loading' });

  const refresh = useCallback(() => {
    setState({ status: 'loading' });
    loadReport()
      .then((report) => {
        if (!report.cells.length) {
          setState({ status: 'empty' });
          return;
        }
        setState({ status: 'loaded', report });
      })
      .catch((error: unknown) => {
        setState({
          status: 'error',
          message: error instanceof Error ? error.message : 'Unexpected error while loading telemetry.',
        });
      });
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  if (state.status === 'loading') return <LoadingState />;
  if (state.status === 'empty') return <EmptyState />;
  if (state.status === 'error') return <ErrorState message={state.message} onRetry={refresh} />;
  return <Dashboard report={state.report} />;
}
