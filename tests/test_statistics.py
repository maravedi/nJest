from __future__ import annotations

from collections import deque

from syslog_sizing_tool.utils.statistics import bounded_append, percentile, percentile_breakdown


def test_bounded_append_maintains_sample_limit() -> None:
    samples = deque(maxlen=3)
    for value in (1, 2, 3, 4):
        bounded_append(samples, value, limit=3)
    assert list(samples) == [2, 3, 4]


def test_percentile_interpolates_expected_value() -> None:
    data = [10, 20, 30, 40]
    assert percentile(data, 0.5) == 25
    assert percentile(data, 0.25) == 17


def test_percentile_breakdown_returns_all_targets() -> None:
    data = [10, 20, 30, 40, 50]
    breakdown = percentile_breakdown(data)
    assert breakdown == {"p50": 30, "p90": 46, "p95": 48, "p99": 49}
