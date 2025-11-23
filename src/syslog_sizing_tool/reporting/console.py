from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from rich.console import Console
from rich.table import Table

console = Console()


def render_console_report(result: Dict[str, Any]) -> None:
    summary = Table(title="Syslog Sizing Summary", show_header=False)
    summary.add_row("Started", _fmt_ts(result.get("started_at")))
    summary.add_row("Stopped", _fmt_ts(result.get("stopped_at")))
    summary.add_row("Total Messages", f"{result.get('total_messages', 0):,}")
    summary.add_row("Total Bytes", f"{result.get('total_bytes', 0):,}")

    estimates = result.get("estimates", {})
    rates = estimates.get("rates", {})

    rate_table = Table(title="Estimated Rates")
    rate_table.add_column("Metric")
    rate_table.add_column("Value")
    rate_table.add_row("Avg EPS", str(rates.get("avg_events_per_second", 0.0)))
    rate_table.add_row("Avg Bps", str(rates.get("avg_bytes_per_second", 0.0)))
    rate_table.add_row(
        "Projected EPS/day", str(rates.get("projected_events_per_day", 0))
    )
    rate_table.add_row(
        "Projected GB/day", str(rates.get("projected_gigabytes_per_day", 0.0))
    )

    percentile = estimates.get("message_size_bytes", {})
    percentile_table = Table(title="Message Size Bytes")
    percentile_table.add_column("Percentile")
    percentile_table.add_column("Bytes")
    for key in ("p50", "p90", "p95", "p99"):
        percentile_table.add_row(key.upper(), str(percentile.get(key, 0)))

    talkers_table = Table(title="Top Talkers")
    talkers_table.add_column("Source")
    talkers_table.add_column("Messages")
    talkers_table.add_column("Bytes")
    talkers_table.add_column("Ratio")
    talkers_table.add_column("Action")
    for talker in estimates.get("talkers", []):
        talkers_table.add_row(
            str(talker.get("source_ip")),
            f"{talker.get('message_count', 0):,}",
            f"{talker.get('bytes_ingested', 0):,}",
            f"{talker.get('ratio', 0.0):.2%}",
            str(talker.get("suggested_action")),
        )

    insight_table = Table(title="Insights")
    insight_table.add_column("Title")
    insight_table.add_column("Detail")
    insight_table.add_column("Confidence")
    for insight in result.get("insights", []):
        insight_table.add_row(
            insight.get("title", ""),
            insight.get("detail", ""),
            f"{float(insight.get('confidence', 0.0)):.0%}",
        )

    console.print(summary)
    console.print(rate_table)
    console.print(percentile_table)
    console.print(talkers_table)
    console.print(insight_table)


def _fmt_ts(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    return "n/a"
