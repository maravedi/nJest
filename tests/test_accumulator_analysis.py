from __future__ import annotations

from datetime import timedelta

from syslog_sizing_tool.types.models import SyslogSizingConfig
from syslog_sizing_tool.utils.accumulator import initialize_state, record_event
from syslog_sizing_tool.utils.analysis import finalize_state


def test_record_event_and_finalize_state_generate_insights() -> None:
    config = SyslogSizingConfig(
        listen_host="0.0.0.0",
        udp_port=5514,
        tcp_port=5614,
        duration_seconds=60,
        noise_threshold_ratio=0.3,
    )
    state = initialize_state()
    for _ in range(9):
        record_event(
            state,
            config=config,
            source_ip="10.0.0.1",
            size_bytes=3_000_000,
            hostname="alpha",
            app_name="collector",
            severity="info",
            message="routine heartbeat",
        )
    record_event(
        state,
        config=config,
        source_ip="10.0.0.2",
        size_bytes=3_000_000,
        hostname="beta",
        app_name="collector",
        severity="info",
        message="routine heartbeat",
    )
    state.dropped_events = 2
    state.stopped_at = state.started_at + timedelta(seconds=1)

    result = finalize_state(state, config)

    assert result.total_messages == 10
    assert result.total_bytes == 30_000_000
    assert result.dropped_ratio == round(2 / 12, 4)
    talker = result.estimates.talkers[0]
    assert talker.source_ip == "10.0.0.1"
    assert talker.suggested_action == "Deduplicate or downsample"

    insight_titles = {insight.title for insight in result.insights}
    assert {
        "Potential sampling bias",
        "Signal-to-noise imbalance",
        "High daily ingest",
        "Dominant noise source",
    }.issubset(insight_titles)


def test_finalize_state_with_balanced_data_returns_healthy_insight() -> None:
    config = SyslogSizingConfig(
        listen_host="0.0.0.0",
        udp_port=5514,
        tcp_port=5614,
        duration_seconds=60,
        noise_threshold_ratio=0.8,
    )
    state = initialize_state()
    record_event(
        state,
        config=config,
        source_ip="10.0.0.3",
        size_bytes=500,
        hostname="node",
        app_name="daemon",
        severity="info",
        message="error counter reset",
    )
    record_event(
        state,
        config=config,
        source_ip="10.0.0.4",
        size_bytes=500,
        hostname="node2",
        app_name="daemon",
        severity="info",
        message="routine status update",
    )
    state.stopped_at = state.started_at + timedelta(seconds=10)

    result = finalize_state(state, config)
    assert result.total_messages == 2
    assert all(talker.ratio == 0.5 for talker in result.estimates.talkers)
    assert any(insight.title == "Healthy distribution" for insight in result.insights)
