from __future__ import annotations

import json
from html import escape
from string import Template
from typing import Any, Dict, Iterable, List


def render_html_report(result: Dict[str, Any], *, title: str | None = None) -> str:
    """
    Build an interactive HTML report for a capture result.

    The page shows the baseline metrics plus a scaling playground that lets
    analysts project load increases by adjusting a multiplier.
    """
    if not isinstance(result, dict):
        raise ValueError("result must be a mapping of capture metrics")

    normalized_title = (title or "Syslog Sizing Report").strip() or "Syslog Sizing Report"
    serialized_payload = json.dumps(result, default=str)

    summary_cards = _render_summary_cards(result)
    rates_section = _render_rates_section(result)
    percentile_section = _render_percentile_section(result)
    talkers_section = _render_talkers_section(result)
    insights_section = _render_insights_section(result)

    baseline_totals = _collect_baseline_totals(result)

    template = Template(_HTML_DOCUMENT)
    return template.substitute(
        title=escape(normalized_title),
        summary_cards=summary_cards,
        rates_section=rates_section,
        percentile_section=percentile_section,
        talkers_section=talkers_section,
        insights_section=insights_section,
        baseline_total_messages=baseline_totals["total_messages"],
        baseline_total_bytes=baseline_totals["total_bytes"],
        baseline_avg_eps=baseline_totals["avg_eps"],
        baseline_avg_bps=baseline_totals["avg_bps"],
        baseline_projected_events=baseline_totals["projected_events"],
        baseline_projected_gb=baseline_totals["projected_gigabytes"],
        footer_label=escape(normalized_title),
        payload=serialized_payload,
    )


def _collect_baseline_totals(result: Dict[str, Any]) -> Dict[str, str]:
    rates = result.get("estimates", {}).get("rates", {})
    return {
        "total_messages": _format_int(result.get("total_messages")),
        "total_bytes": _format_int(result.get("total_bytes")),
        "avg_eps": _format_float(rates.get("avg_events_per_second"), precision=2),
        "avg_bps": _format_float(rates.get("avg_bytes_per_second"), precision=2),
        "projected_events": _format_int(rates.get("projected_events_per_day")),
        "projected_gigabytes": _format_float(
            rates.get("projected_gigabytes_per_day"), precision=3
        ),
    }


def _render_summary_cards(result: Dict[str, Any]) -> str:
    started = _safe_str(result.get("started_at"))
    stopped = _safe_str(result.get("stopped_at"))
    cards: List[str] = [
        _render_card("Capture Window", f"{started} \u2192 {stopped}"),
        _render_card("Total Messages", _format_int(result.get("total_messages"))),
        _render_card("Total Bytes", _format_int(result.get("total_bytes"), suffix=" B")),
        _render_card(
            "Dropped Events",
            _format_int(result.get("dropped_events")),
            f"Ratio {_format_percent(result.get('dropped_ratio'))}",
        ),
    ]
    talker_count = len(result.get("estimates", {}).get("talkers", []) or [])
    cards.append(_render_card("Observed Talkers", _format_int(talker_count)))
    return "\n".join(cards)


def _render_rates_section(result: Dict[str, Any]) -> str:
    rates = result.get("estimates", {}).get("rates", {})
    rows = [
        ("Avg events/sec", _format_float(rates.get("avg_events_per_second"), precision=2)),
        ("Avg bytes/sec", _format_float(rates.get("avg_bytes_per_second"), precision=2)),
        ("Projected events/day", _format_int(rates.get("projected_events_per_day"))),
        ("Projected GB/day", _format_float(rates.get("projected_gigabytes_per_day"), precision=3)),
    ]
    return _render_table_section("Estimated Rates", rows)


def _render_percentile_section(result: Dict[str, Any]) -> str:
    percentile = result.get("estimates", {}).get("message_size_bytes", {})
    rows = [
        ("P50", _format_int(percentile.get("p50"), suffix=" B")),
        ("P90", _format_int(percentile.get("p90"), suffix=" B")),
        ("P95", _format_int(percentile.get("p95"), suffix=" B")),
        ("P99", _format_int(percentile.get("p99"), suffix=" B")),
    ]
    return _render_table_section("Message Size Percentiles", rows)


def _render_talkers_section(result: Dict[str, Any]) -> str:
    talkers = result.get("estimates", {}).get("talkers", []) or []
    if not talkers:
        return (
            "<section class=\"panel\">"
            "<h2>Top Talkers</h2>"
            "<p class=\"muted\">No talker data captured.</p>"
            "</section>"
        )

    rows = []
    for talker in talkers:
        rows.append(
            "<tr>"
            f"<td>{escape(str(talker.get('source_ip', 'n/a')))}</td>"
            f"<td>{_format_int(talker.get('message_count'))}</td>"
            f"<td>{_format_int(talker.get('bytes_ingested'))}</td>"
            f"<td>{_format_percent(talker.get('ratio'))}</td>"
            f"<td>{escape(str(talker.get('suggested_action', 'n/a')))}</td>"
            "</tr>"
        )

    table = (
        "<table>"
        "<thead><tr>"
        "<th>Source</th><th>Messages</th><th>Bytes</th><th>Traffic share</th><th>Action</th>"
        "</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
    )

    pattern_rows = []
    for talker in talkers:
        patterns = talker.get("suggested_patterns", [])
        if patterns:
             # pattern is now a dict (from SuggestedPattern model)
             inner_rows = []
             for p in patterns:
                 p_str = p.get("pattern", "")
                 p_ex = p.get("example", "")
                 p_count = _format_int(p.get("match_count"))
                 p_pct = _format_percent(p.get("match_percent"))
                 p_eps = _format_float(p.get("match_eps"), precision=1)
                 p_mbps = _format_float(p.get("match_mbps"), precision=3)

                 inner_rows.append(
                     "<tr>"
                     f"<td><code>{escape(p_str)}</code><br><small class=\"muted\">Ex: {escape(p_ex)}</small></td>"
                     f"<td>{p_count}</td>"
                     f"<td>{p_pct}</td>"
                     f"<td>{p_eps}</td>"
                     f"<td>{p_mbps}</td>"
                     "</tr>"
                 )

             inner_table = (
                 "<table class=\"inner-table\">"
                 "<thead><tr><th>Pattern / Example</th><th>Est. Events</th><th>% Traffic</th><th>Est. EPS</th><th>Est. MB/s</th></tr></thead>"
                 f"<tbody>{''.join(inner_rows)}</tbody>"
                 "</table>"
             )

             pattern_rows.append(
                f"<tr><td><strong>{escape(talker.get('source_ip', 'n/a'))}</strong></td>"
                f"<td>{inner_table}</td></tr>"
             )

    if pattern_rows:
        table += (
            "<h3>Suggested Patterns for Noisy Talkers</h3>"
            "<table><thead><tr><th>Source</th><th>Analysis</th></tr></thead>"
            f"<tbody>{''.join(pattern_rows)}</tbody></table>"
        )
    return f"<section class=\"panel\"><h2>Top Talkers</h2>{table}</section>"


def _render_insights_section(result: Dict[str, Any]) -> str:
    insights = result.get("insights") or []
    if not insights:
        return (
            "<section class=\"panel\">"
            "<h2>Insights</h2>"
            "<p class=\"muted\">No insights were generated during this capture.</p>"
            "</section>"
        )

    cards = []
    for insight in insights:
        cards.append(
            "<article class=\"insight-card\">"
            f"<h3>{escape(str(insight.get('title', 'Untitled insight')))}</h3>"
            f"<p>{escape(str(insight.get('detail', '')))}</p>"
            f"<span class=\"badge\">Confidence {_format_percent(insight.get('confidence'))}</span>"
            "</article>"
        )
    return f"<section class=\"panel\"><h2>Insights</h2><div class=\"insight-grid\">{''.join(cards)}</div></section>"


def _render_card(label: str, primary: str, secondary: str | None = None) -> str:
    segments = [
        "<article class=\"card\">",
        f"<p class=\"card-label\">{escape(label)}</p>",
        f"<p class=\"card-value\">{escape(primary)}</p>",
    ]
    if secondary:
        segments.append(f"<p class=\"card-sub\">{escape(secondary)}</p>")
    segments.append("</article>")
    return "".join(segments)


def _render_table_section(title: str, rows: Iterable[tuple[str, str]]) -> str:
    body_rows = "".join(
        f"<tr><td>{escape(label)}</td><td>{escape(value)}</td></tr>"
        for label, value in rows
    )
    return f"<section class=\"panel\"><h2>{escape(title)}</h2><table><tbody>{body_rows}</tbody></table></section>"


def _format_int(value: Any, *, suffix: str | None = None) -> str:
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return "n/a"
    suffix_text = f" {suffix}" if suffix else ""
    return f"{number:,}{suffix_text}"


def _format_float(value: Any, *, precision: int = 2, suffix: str | None = None) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "n/a"
    suffix_text = f" {suffix}" if suffix else ""
    return f"{number:,.{precision}f}{suffix_text}"


def _format_percent(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "n/a"
    return f"{number:.2%}"


def _safe_str(value: Any) -> str:
    if value is None:
        return "n/a"
    return str(value)


_HTML_DOCUMENT = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>$title</title>
  <style>
    :root {
      color-scheme: light dark;
      font-family: "Inter", "Segoe UI", system-ui, -apple-system, sans-serif;
      --panel-bg: rgba(255, 255, 255, 0.9);
      --panel-border: rgba(0, 0, 0, 0.08);
      --accent: #2563eb;
      --muted: rgba(0, 0, 0, 0.65);
    }
    body {
      margin: 0;
      padding: 0 1rem 3rem;
      background: #f4f6fb;
      color: #0f172a;
    }
    header {
      padding: 2rem 0 1rem;
    }
    .summary-grid {
      display: grid;
      gap: 1rem;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    }
    .card {
      background: var(--panel-bg);
      border: 1px solid var(--panel-border);
      border-radius: 12px;
      padding: 1rem;
      box-shadow: 0 10px 25px rgba(15, 23, 42, 0.08);
    }
    .card-label {
      margin: 0;
      font-size: 0.9rem;
      color: var(--muted);
    }
    .card-value {
      margin: 0.35rem 0 0;
      font-size: 1.6rem;
      font-weight: 600;
    }
    .card-sub {
      margin: 0.3rem 0 0;
      color: var(--muted);
      font-size: 0.85rem;
    }
    .panel {
      background: var(--panel-bg);
      border: 1px solid var(--panel-border);
      border-radius: 16px;
      padding: 1.5rem;
      margin-top: 2rem;
      box-shadow: 0 18px 45px rgba(15, 23, 42, 0.12);
    }
    .panel h2 {
      margin-top: 0;
      font-size: 1.25rem;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      margin-top: 1rem;
    }
    .inner-table {
      margin-top: 0;
      border: none;
      background: rgba(0,0,0,0.02);
      border-radius: 8px;
    }
    .inner-table th {
        font-size: 0.75rem;
        padding: 0.4rem;
    }
    .inner-table td {
        font-size: 0.9rem;
        padding: 0.4rem;
        border-bottom: 1px solid rgba(0,0,0,0.05);
    }
    th, td {
      padding: 0.6rem;
      text-align: left;
      border-bottom: 1px solid rgba(15, 23, 42, 0.08);
    }
    th {
      font-size: 0.85rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--muted);
    }
    .muted {
      color: var(--muted);
    }
    .scaling-controls {
      display: flex;
      flex-wrap: wrap;
      gap: 1rem;
      align-items: center;
      margin-bottom: 1.5rem;
    }
    .scaling-controls label {
      font-weight: 600;
    }
    .scaling-controls input[type="number"] {
      width: 110px;
      padding: 0.4rem;
      border: 1px solid var(--panel-border);
      border-radius: 8px;
      font-size: 1rem;
    }
    .scaling-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 1rem;
    }
    .scaled-card {
      border-radius: 12px;
      border: 1px solid rgba(37, 99, 235, 0.15);
      padding: 1rem;
      background: rgba(37, 99, 235, 0.08);
    }
    .scaled-card .label {
      margin: 0;
      color: rgba(15, 23, 42, 0.7);
      font-size: 0.9rem;
    }
    .scaled-card .value {
      margin: 0.35rem 0 0;
      font-size: 1.5rem;
      font-weight: 600;
      color: #1d4ed8;
    }
    .scaled-card .hint {
      margin: 0.2rem 0 0;
      font-size: 0.8rem;
      color: rgba(15, 23, 42, 0.7);
    }
    .insight-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 1rem;
    }
    .insight-card {
      border: 1px solid var(--panel-border);
      border-radius: 12px;
      padding: 1rem;
      background: rgba(15, 23, 42, 0.02);
    }
    .insight-card h3 {
      margin-top: 0;
    }
    .badge {
      display: inline-flex;
      padding: 0.2rem 0.6rem;
      border-radius: 999px;
      background: rgba(34, 197, 94, 0.1);
      color: #15803d;
      font-weight: 600;
      font-size: 0.8rem;
    }
    footer {
      text-align: center;
      margin-top: 2rem;
      color: var(--muted);
      font-size: 0.85rem;
    }
    @media (prefers-color-scheme: dark) {
      body {
        background: #0f172a;
        color: #f8fafc;
      }
      .card, .panel, .insight-card {
        background: rgba(15, 23, 42, 0.6);
        border-color: rgba(148, 163, 184, 0.2);
        box-shadow: none;
      }
      table th, table td {
        border-bottom-color: rgba(148, 163, 184, 0.2);
      }
      .scaled-card {
        background: rgba(37, 99, 235, 0.2);
      }
    }
  </style>
</head>
<body>
  <header>
    <h1>$title</h1>
    <p class="muted">Interactive report generated by syslog-sizing-tool</p>
  </header>

  <section class="summary-grid">
    $summary_cards
  </section>

  $rates_section
  $percentile_section
  $talkers_section
  $insights_section

  <section class="panel" id="scaling-panel">
    <h2>Scaling Playground</h2>
    <p class="muted">Use the slider to experiment with device counts or log volume multipliers.</p>
    <div class="scaling-controls">
      <label for="scale-input">Device multiplier (<span id="scale-label">1.0x</span>)</label>
      <input id="scale-input" type="range" min="0.1" max="10" step="0.1" value="1">
      <input id="scale-number" type="number" min="0.1" step="0.1" value="1.0" aria-label="Multiplier input">
    </div>
    <div class="scaling-grid">
      <article class="scaled-card">
        <p class="label">Projected total messages</p>
        <p class="value" id="scaled-total-messages">$baseline_total_messages</p>
        <p class="hint">Baseline $baseline_total_messages</p>
      </article>
      <article class="scaled-card">
        <p class="label">Projected total bytes</p>
        <p class="value" id="scaled-total-bytes">$baseline_total_bytes</p>
        <p class="hint">Baseline $baseline_total_bytes</p>
      </article>
      <article class="scaled-card">
        <p class="label">Avg events per second</p>
        <p class="value" id="scaled-avg-eps">$baseline_avg_eps</p>
        <p class="hint">Baseline $baseline_avg_eps</p>
      </article>
      <article class="scaled-card">
        <p class="label">Avg bytes per second</p>
        <p class="value" id="scaled-avg-bps">$baseline_avg_bps</p>
        <p class="hint">Baseline $baseline_avg_bps</p>
      </article>
      <article class="scaled-card">
        <p class="label">Projected events per day</p>
        <p class="value" id="scaled-projectedevents">$baseline_projected_events</p>
        <p class="hint">Baseline $baseline_projected_events</p>
      </article>
      <article class="scaled-card">
        <p class="label">Projected GB per day</p>
        <p class="value" id="scaled-projectedgb">$baseline_projected_gb</p>
        <p class="hint">Baseline $baseline_projected_gb</p>
      </article>
    </div>

    <h3>Scaled talker load</h3>
    <table>
      <thead>
        <tr>
          <th>Source</th>
          <th>Baseline messages</th>
          <th>Scaled messages</th>
          <th>Baseline bytes</th>
          <th>Scaled bytes</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody id="scaled-talkers-body">
        <tr><td colspan="6" class="muted">Populated when talker data exists.</td></tr>
      </tbody>
    </table>
  </section>

  <footer>
    Generated from $footer_label
  </footer>

  <script id="report-data" type="application/json">$payload</script>
  <script>
    (function () {
      const dataElement = document.getElementById("report-data");
      if (!dataElement) {
        return;
      }
      const baseline = JSON.parse(dataElement.textContent);
      const slider = document.getElementById("scale-input");
      const numberInput = document.getElementById("scale-number");
      const label = document.getElementById("scale-label");

      const targets = [
        { id: "scaled-total-messages", path: ["total_messages"], decimals: 0 },
        { id: "scaled-total-bytes", path: ["total_bytes"], decimals: 0 },
        { id: "scaled-avg-eps", path: ["estimates", "rates", "avg_events_per_second"], decimals: 2 },
        { id: "scaled-avg-bps", path: ["estimates", "rates", "avg_bytes_per_second"], decimals: 2 },
        { id: "scaled-projectedevents", path: ["estimates", "rates", "projected_events_per_day"], decimals: 0 },
        { id: "scaled-projectedgb", path: ["estimates", "rates", "projected_gigabytes_per_day"], decimals: 3 }
      ];

      function getValue(path) {
        return path.reduce((acc, key) => (acc && acc[key] != null ? acc[key] : 0), baseline);
      }

      function formatNumber(value, decimals) {
        const formatter = new Intl.NumberFormat(undefined, {
          minimumFractionDigits: decimals,
          maximumFractionDigits: decimals,
        });
        return formatter.format(value);
      }

      function updateTalkers(multiplier) {
        const body = document.getElementById("scaled-talkers-body");
        if (!body) {
          return;
        }
        const talkers = (baseline?.estimates?.talkers) || [];
        if (!talkers.length) {
          body.innerHTML = '<tr><td colspan="6" class="muted">No talker data available for scaling.</td></tr>';
          return;
        }
        body.innerHTML = "";
        talkers.forEach((talker) => {
          const baselineMessages = Number(talker.message_count || 0);
          const baselineBytes = Number(talker.bytes_ingested || 0);
          const scaledMessages = Math.round(baselineMessages * multiplier);
          const scaledBytes = Math.round(baselineBytes * multiplier);
          const row = document.createElement("tr");
          row.innerHTML =
            "<td>" + (talker.source_ip ?? "n/a") + "</td>" +
            "<td>" + formatNumber(baselineMessages, 0) + "</td>" +
            "<td>" + formatNumber(scaledMessages, 0) + "</td>" +
            "<td>" + formatNumber(baselineBytes, 0) + "</td>" +
            "<td>" + formatNumber(scaledBytes, 0) + "</td>" +
            "<td>" + (talker.suggested_action ?? "n/a") + "</td>";
          body.appendChild(row);
        });
      }

      function applyScale(multiplier) {
        label.textContent = multiplier.toFixed(1) + "x";
        targets.forEach(({ id, path, decimals }) => {
          const node = document.getElementById(id);
          if (!node) {
            return;
          }
          const baseValue = Number(getValue(path)) || 0;
          const scaledValue = baseValue * multiplier;
          node.textContent = formatNumber(scaledValue, decimals);
        });
        updateTalkers(multiplier);
      }

      function syncInputs(source) {
        const multiplier = Number(source.value);
        if (Number.isNaN(multiplier) || multiplier <= 0) {
          return;
        }
        slider.value = multiplier;
        numberInput.value = multiplier;
        applyScale(multiplier);
      }

      slider.addEventListener("input", () => syncInputs(slider));
      numberInput.addEventListener("change", () => syncInputs(numberInput));

      applyScale(Number(slider.value));
    })();
  </script>
</body>
</html>
"""
