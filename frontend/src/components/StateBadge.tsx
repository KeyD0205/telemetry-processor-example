import { CellState } from '../types';
import { titleize } from '../lib/format';

const toneByState: Record<CellState, string> = {
  running: 'badge badge-success',
  slowed: 'badge badge-warning',
  paused: 'badge badge-warning',
  stopped: 'badge badge-danger',
  fault: 'badge badge-danger',
  maintenance: 'badge badge-info',
  waiting_for_human: 'badge badge-neutral',
  sleep: 'badge badge-neutral',
  unknown: 'badge badge-neutral',
};

export function StateBadge({ state }: { state: CellState }) {
  return <span className={toneByState[state] ?? toneByState.unknown}>{titleize(state)}</span>;
}
