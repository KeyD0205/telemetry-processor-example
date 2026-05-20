from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')

from .pipeline import process_file, write_json_report


def format_seconds(seconds: float | None) -> str:
    if seconds is None:
        return "n/a"
    return f"{seconds:.0f}s"


def format_pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.1f}%"


def render_table(report: dict[str, Any]) -> str:
    lines = []
    lines.append("Telemetry metrics summary")
    lines.append(f"Window: {report['window']['start']} → {report['window']['end']}")
    lines.append(f"Cells: {report['cell_count']} | Events processed: {report['normalized_event_count']} | Data quality issues: {report['data_quality']['issue_count']}")
    lines.append("")
    cells = report["cells"]
    cell_w = max((len(str(c["cell_id"])) for c in cells), default=0)
    cell_w = max(cell_w, 4)  # min: len("Cell")
    state_w = max((len(str(c["current_state"])) for c in cells), default=0)
    state_w = max(state_w, 5)  # min: len("State")
    header = f"{'Cell':<{cell_w}} {'State':<{state_w}} {'Avail.':>8} {'Uptime':>8} {'Downtime':>9} {'Cycles':>7} {'TPH':>8} {'Avg cycle':>10} {'Faults':>7}"
    lines.append(header)
    lines.append("-" * len(header))
    for cell in cells:
        lines.append(
            f"{cell['cell_id']:<{cell_w}} "
            f"{cell['current_state']:<{state_w}} "
            f"{format_pct(cell['availability']):>8} "
            f"{format_seconds(cell['uptime_seconds']):>8} "
            f"{format_seconds(cell['downtime_seconds']):>9} "
            f"{cell['completed_cycles']:>7} "
            f"{cell['throughput_cycles_per_hour']:>8.3f} "
            f"{format_seconds(cell['cycle_time_seconds']['avg']):>10} "
            f"{cell['fault_event_count']:>7}"
        )
    lines.append("")
    if report["fleet"]["recent_faults"]:
        lines.append("Recent faults")
        for fault in report["fleet"]["recent_faults"][:5]:
            codes = ", ".join(fault["codes"]) or "UNKNOWN"
            message = "; ".join(fault["messages"])
            lines.append(f"- {fault['timestamp']} {fault['cell_id']} [{codes}] {message}")
        lines.append("")
    if report["data_quality"]["issues"]:
        lines.append("Top data-quality findings")
        for issue in report["data_quality"]["issues"][:8]:
            lines.append(f"- {issue['severity'].upper()} {issue['code']} {issue.get('cell_id') or ''}: {issue['message']}")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Process robot-cell telemetry JSON into operational metrics.")
    parser.add_argument("input", type=Path, help="Path to raw telemetry JSON array")
    parser.add_argument("--format", choices=("table", "json"), default="table", help="Output format for stdout")
    parser.add_argument("--output", type=Path, help="Optional path to write a full JSON report")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = process_file(args.input)
    if args.output:
        write_json_report(report, args.output)
    if args.format == "json":
        print(json.dumps(report, indent=2))
    else:
        print(render_table(report))


if __name__ == "__main__":
    main()
