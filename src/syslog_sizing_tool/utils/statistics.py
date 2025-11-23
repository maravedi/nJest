from __future__ import annotations

from typing import Deque, Iterable, List


def bounded_append(samples: Deque[int], value: int, limit: int) -> None:
    if limit <= 0:
        return
    if len(samples) >= limit:
        samples.popleft()
    samples.append(value)


def percentile(values: Iterable[int], percentile_rank: float) -> int:
    data: List[int] = sorted(values)
    if not data:
        return 0
    k = (len(data) - 1) * percentile_rank
    f = int(k)
    c = min(f + 1, len(data) - 1)
    if f == c:
        return data[int(k)]
    d0 = data[f] * (c - k)
    d1 = data[c] * (k - f)
    return int(d0 + d1)


def percentile_breakdown(values: Iterable[int]) -> dict[str, int]:
    data = list(values)
    return {
        "p50": percentile(data, 0.50),
        "p90": percentile(data, 0.90),
        "p95": percentile(data, 0.95),
        "p99": percentile(data, 0.99),
    }
