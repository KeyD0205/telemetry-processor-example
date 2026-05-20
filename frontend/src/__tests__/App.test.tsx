import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import type { ReactNode } from 'react';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { CellComparison } from '../components/CellComparison';
import { Dashboard } from '../components/Dashboard';
import { DataQualityPanel } from '../components/DataQualityPanel';
import { FaultList } from '../components/FaultList';
import { EmptyState, ErrorState, LoadingState } from '../components/LoadingState';
import { ThroughputChart } from '../components/ThroughputChart';
import processedReport from '../mock/processed_metrics.json';
import { DataQualityIssue, TelemetryReport } from '../types';

vi.mock('recharts', async () => {
  const actual = await vi.importActual<typeof import('recharts')>('recharts');
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: ReactNode }) => (
      <div data-testid="responsive-container">{children}</div>
    ),
  };
});

const report = processedReport as unknown as TelemetryReport;

beforeAll(() => {
  class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  }

  vi.stubGlobal('ResizeObserver', ResizeObserver);
  Object.defineProperty(HTMLElement.prototype, 'clientWidth', { configurable: true, value: 800 });
  Object.defineProperty(HTMLElement.prototype, 'clientHeight', { configurable: true, value: 300 });
});

afterEach(() => {
  cleanup();
});

describe('Loading states', () => {
  it('renders loading state initially', () => {
    render(<LoadingState />);
    expect(screen.getByText(/Loading telemetry/i)).toBeInTheDocument();
  });

  it('renders empty state', () => {
    render(<EmptyState />);
    expect(screen.getByText(/No telemetry available/i)).toBeInTheDocument();
  });

  it('renders error state and retry button', () => {
    const onRetry = vi.fn();
    render(<ErrorState message="Test error" onRetry={onRetry} />);
    expect(screen.getByText(/Could not load telemetry/i)).toBeInTheDocument();
    fireEvent.click(screen.getByText(/Retry/i));
    expect(onRetry).toHaveBeenCalled();
  });
});

describe('Dashboard', () => {
  it('renders dashboard with metrics and sections', () => {
    render(<Dashboard report={report} fetchedAt={new Date('2026-05-20T10:00:00Z')} />);
    expect(screen.getByText(/Telemetry health dashboard/i)).toBeInTheDocument();
    expect(screen.getByText(/Fleet availability/i)).toBeInTheDocument();
    expect(screen.getByText('Completed cycles')).toBeInTheDocument();
    expect(screen.getByText(/Average cycle time/i)).toBeInTheDocument();
    expect(screen.getByText(/Fault \+ maintenance time/i)).toBeInTheDocument();
    expect(screen.getByText(/Cell comparison/i)).toBeInTheDocument();
    expect(screen.getByText(/Throughput over time/i)).toBeInTheDocument();
    expect(screen.getByText(/Recent faults and alerts/i)).toBeInTheDocument();
    expect(screen.getByText(/Data quality/i)).toBeInTheDocument();
  });
});

describe('CellComparison', () => {
  it('renders cell comparison table', () => {
    render(<CellComparison cells={report.cells} />);
    expect(screen.getByText(/Cell comparison/i)).toBeInTheDocument();
    expect(screen.getByText(/Operational view/i)).toBeInTheDocument();
    report.cells.forEach((cell) => {
      expect(screen.getByText(cell.cell_id)).toBeInTheDocument();
    });
  });
});

describe('DataQualityPanel', () => {
  it('renders data quality issues', () => {
    render(<DataQualityPanel issues={report.data_quality.issues} />);
    expect(screen.getByText(/Data quality/i)).toBeInTheDocument();

    const shownIssue = report.data_quality.issues.find((issue) => issue.severity !== 'info')
      ?? report.data_quality.issues[0] as DataQualityIssue | undefined;

    if (shownIssue) {
      expect(screen.getByText(shownIssue.code.replace(/_/g, ' '))).toBeInTheDocument();
    }
  });
});

describe('FaultList', () => {
  it('renders fault list', () => {
    render(<FaultList faults={report.fleet.recent_faults} />);
    expect(screen.getByText(/Recent faults and alerts/i)).toBeInTheDocument();
  });
});

describe('ThroughputChart', () => {
  it('renders throughput chart section', () => {
    render(<ThroughputChart buckets={report.fleet.throughput_over_time} />);
    expect(screen.getByText(/Throughput over time/i)).toBeInTheDocument();
  });
});
