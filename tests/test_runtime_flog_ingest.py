from __future__ import annotations

import pytest

from syslog_sizing_tool.utils.integration_test_runner import (
    load_flog_samples,
    run_integration_test,
)


@pytest.mark.asyncio
async def test_capture_session_handles_flog_samples_without_drops() -> None:
    samples = load_flog_samples()
    result = await run_integration_test()

    assert result["total_messages"] == len(samples)
    assert result["dropped_events"] == 0
    assert result["per_hostname"].get("edge-router-01", 0) > 0
    assert result["per_app_name"].get("firewalld", 0) > 0
    assert result["estimates"]["rates"]["avg_events_per_second"] > 0
