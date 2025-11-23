from __future__ import annotations

import pytest

from tests.utils.flog_workload import load_flog_samples, replay_flog_workload


@pytest.mark.asyncio
async def test_capture_session_handles_flog_samples_without_drops() -> None:
    samples = load_flog_samples()
    result = await replay_flog_workload()

    assert result["total_messages"] == len(samples)
    assert result["dropped_events"] == 0
    assert result["per_hostname"].get("edge-router-01", 0) > 0
    assert result["per_app_name"].get("firewalld", 0) > 0
    assert result["estimates"]["rates"]["avg_events_per_second"] > 0
