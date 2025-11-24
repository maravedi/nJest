from __future__ import annotations

from typing import Any, Dict

import pytest

from syslog_sizing_tool.reporting.html import render_html_report


def _sample_result() -> Dict[str, Any]:
    return {
        "started_at": "2025-11-23T19:46:53Z",
        "stopped_at": "2025-11-23T19:46:55Z",
        "total_messages": 25,
        "total_bytes": 3644,
        "dropped_events": 0,
        "dropped_ratio": 0.0,
        "estimates": {
            "rates": {
                "avg_events_per_second": 12.16,
                "avg_bytes_per_second": 1772.11,
                "projected_events_per_day": 1050428,
                "projected_gigabytes_per_day": 0.143,
            },
            "message_size_bytes": {"p50": 146, "p90": 169, "p95": 170, "p99": 172},
            "talkers": [
                {
                    "source_ip": "127.0.0.1",
                    "message_count": 25,
                    "bytes_ingested": 3644,
                    "ratio": 1.0,
                    "suggested_action": "Deduplicate or downsample",
                }
            ],
        },
        "insights": [
            {
                "title": "Dominant noise source",
                "detail": "Investigate chatty services or enable sampling.",
                "confidence": 0.9,
            }
        ],
    }


def test_render_html_report_includes_interactive_controls() -> None:
    report = render_html_report(_sample_result(), title="Lab Window")
    assert "<!DOCTYPE html>" in report
    assert 'id="scale-input"' in report
    assert "Scaling Playground" in report
    assert "Lab Window" in report
    assert "Top Talkers" in report


def test_render_html_report_rejects_non_mapping() -> None:
    with pytest.raises(ValueError):
        render_html_report("invalid")  # type: ignore[arg-type]
