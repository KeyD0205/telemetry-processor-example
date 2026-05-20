import { render, screen, fireEvent } from '@testing-library/react';
import App from '../App';
import { Dashboard } from '../components/Dashboard';
import { CellComparison } from '../components/CellComparison';
import { DataQualityPanel } from '../components/DataQualityPanel';
import { FaultList } from '../components/FaultList';
import { ThroughputChart } from '../components/ThroughputChart';
import { LoadingState, EmptyState, ErrorState } from '../components/LoadingState';
import processedReport from '../mock/processed_metrics.json';

describe('App', () => {
  it('renders loading state initially', () => {
    render(<LoadingState />);
    expect(screen.getByText(/Loading telemetry/i)).toBeInTheDocument();
  });

  it('renders empty state', () => {
    render(<EmptyState />);
    expect(screen.getByText(/No telemetry available/i)).toBeInTheDocument();
  });

  it('renders error state and retry button', () => {
    const onRetry = jest.fn();
    render(<ErrorState message="Test error" onRetry={onRetry} />);
    expect(screen.getByText(/Could not load telemetry/i)).toBeInTheDocument();
    fireEvent.click(screen.getByText(/Retry/i));
    expect(onRetry).toHaveBeenCalled();
  });
});

describe('Dashboard', () => {
  it('renders dashboard with metrics and sections', () => {
    render(<Dashboard report={processedReport as any} />);
    expect(screen.getByText(/Telemetry health dashboard/i)).toBeInTheDocument();
    expect(screen.getByText(/Fleet availability/i)).toBeInTheDocument();
    expect(screen.getByText(/Completed cycles/i)).toBeInTheDocument();
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
    render(<CellComparison cells={processedReport.cells} />);
    expect(screen.getByText(/Cell comparison/i)).toBeInTheDocument();
    expect(screen.getByText(/Operational view/i)).toBeInTheDocument();
    processedReport.cells.forEach(cell => {
      expect(screen.getByText(cell.cell_id)).toBeInTheDocument();
    });
  });
});

describe('DataQualityPanel', () => {
  it('renders data quality issues', () => {
    render(<DataQualityPanel issues={processedReport.data_quality.issues} />);
    expect(screen.getByText(/Data quality/i)).toBeInTheDocument();
    if (processedReport.data_quality.issues.length > 0) {
      expect(screen.getByText(processedReport.data_quality.issues[0].code.replaceAll('_', ' '))).toBeInTheDocument();
    }
  });
});

describe('FaultList', () => {
  it('renders fault list', () => {
    render(<FaultList faults={processedReport.fleet.recent_faults} />);
    expect(screen.getByText(/Recent faults and alerts/i)).toBeInTheDocument();
  });
});

describe('ThroughputChart', () => {
  it('renders throughput chart section', () => {
    render(<ThroughputChart buckets={processedReport.fleet.throughput_over_time} />);
    expect(screen.getByText(/Throughput over time/i)).toBeInTheDocument();
  });
});
