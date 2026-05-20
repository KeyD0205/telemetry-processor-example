import { ReactNode } from 'react';

interface MetricCardProps {
  label: string;
  value: ReactNode;
  helper?: ReactNode;
  intent?: 'default' | 'success' | 'warning' | 'danger';
}

export function MetricCard({ label, value, helper, intent = 'default' }: MetricCardProps) {
  return (
    <section className={`metric-card metric-card-${intent}`}>
      <span className="metric-label">{label}</span>
      <strong className="metric-value">{value}</strong>
      {helper ? <span className="metric-helper">{helper}</span> : null}
    </section>
  );
}
