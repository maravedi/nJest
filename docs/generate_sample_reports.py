from __future__ import annotations

import asyncio
import json
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from io import StringIO
from pathlib import Path
import sys
from typing import Any, Dict, Iterator

from rich.console import Console
from weasyprint import HTML

# Ensure repository modules (tests + src) are importable when this script runs from docs/
ROOT_DIR = Path(__file__).resolve().parents[1]
for candidate in (ROOT_DIR, ROOT_DIR / "src"):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from syslog_sizing_tool.reporting import console as console_module  # noqa: E402
from syslog_sizing_tool.reporting.console import render_console_report  # noqa: E402
from syslog_sizing_tool.reporting.html import render_html_report  # noqa: E402
from syslog_sizing_tool.types.models import SyslogSizingConfig  # noqa: E402
from syslog_sizing_tool.utils.accumulator import initialize_state, record_event  # noqa: E402
from syslog_sizing_tool.utils.analysis import finalize_state  # noqa: E402
from syslog_sizing_tool.utils.integration_test_runner import run_integration_test  # noqa: E402

ARTIFACT_DIR = Path(__file__).resolve().parent / "sample_reports"


def normalize_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: normalize_payload(v) for k, v in value.items()}
    if isinstance(value, list):
        return [normalize_payload(v) for v in value]
    if isinstance(value, datetime):
        return value.isoformat()
    return value


@contextmanager
def capture_console() -> Iterator[Console]:
    buffer = StringIO()
    recorder = Console(record=True, width=120, file=buffer)
    original_console = console_module.console
    console_module.console = recorder
    try:
        yield recorder
    finally:
        console_module.console = original_console


def export_artifacts(scenario: str, result: Dict[str, Any]) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    normalized = normalize_payload(result)
    json_path = ARTIFACT_DIR / f"{scenario}.json"
    json_path.write_text(json.dumps(normalized, indent=2), encoding="utf-8")

    with capture_console() as recorder:
        render_console_report(result)
        console_text = recorder.export_text(clear=False).strip() + "\n"
    (ARTIFACT_DIR / f"{scenario}.console.txt").write_text(console_text, encoding="utf-8")

    html_title = scenario.replace("_", " ").title()
    html_blob = render_html_report(result, title=html_title)
    (ARTIFACT_DIR / f"{scenario}.html").write_text(html_blob, encoding="utf-8")

    HTML(string=html_blob).write_pdf(ARTIFACT_DIR / f"{scenario}.pdf")


def pump_events(
    state,
    config: SyslogSizingConfig,
    *,
    source_ip: str,
    hostname: str,
    app_name: str,
    severity: str,
    message: str,
    size_bytes: int,
    count: int,
) -> None:
    for _ in range(count):
        record_event(
            state,
            config=config,
            source_ip=source_ip,
            size_bytes=size_bytes,
            hostname=hostname,
            app_name=app_name,
            severity=severity,
            message=message,
        )


async def build_baseline_result() -> Dict[str, Any]:
    return await run_integration_test()


def build_peak_result() -> Dict[str, Any]:
    duration_seconds = 15
    config = SyslogSizingConfig(
        listen_host="10.23.0.15",
        udp_port=15514,
        tcp_port=16514,
        duration_seconds=duration_seconds,
        flush_interval_seconds=3,
        sample_size_limit=4096,
        high_value_keywords=["dropped", "error", "timeout", "retry"],
        noise_threshold_ratio=0.5,
        max_tcp_clients=128,
        inactivity_grace_seconds=2,
    )
    state = initialize_state()
    state.started_at = datetime(2025, 11, 18, 1, 0, 0, tzinfo=timezone.utc)

    pump_events(
        state,
        config,
        source_ip="10.23.0.10",
        hostname="edge-fw-01",
        app_name="firewalld",
        severity="warning",
        message="dropped east-west packet burst error-rate=12%",
        size_bytes=14_000,
        count=1_200,
    )
    pump_events(
        state,
        config,
        source_ip="10.23.0.11",
        hostname="edge-fw-02",
        app_name="firewalld",
        severity="notice",
        message="accepted flow update rate stable",
        size_bytes=6_000,
        count=500,
    )
    pump_events(
        state,
        config,
        source_ip="10.23.2.45",
        hostname="mesh-router-07",
        app_name="sdwan-agent",
        severity="info",
        message="path telemetry update jitter=3ms",
        size_bytes=9_000,
        count=900,
    )
    pump_events(
        state,
        config,
        source_ip="10.23.4.18",
        hostname="auth-proxy-02",
        app_name="envoy",
        severity="error",
        message="timeout contacting upstream oauth cluster",
        size_bytes=18_000,
        count=400,
    )
    pump_events(
        state,
        config,
        source_ip="10.23.7.90",
        hostname="payments-core-03",
        app_name="uwsgi",
        severity="error",
        message="retry due to database timeout",
        size_bytes=15_000,
        count=300,
    )

    state.stopped_at = state.started_at + timedelta(seconds=duration_seconds)
    return finalize_state(state, config).model_dump()


def build_noisy_result() -> Dict[str, Any]:
    duration_seconds = 5
    config = SyslogSizingConfig(
        listen_host="192.0.2.55",
        udp_port=25214,
        tcp_port=26214,
        duration_seconds=duration_seconds,
        flush_interval_seconds=1,
        sample_size_limit=1024,
        high_value_keywords=["panic", "error", "fail"],
        noise_threshold_ratio=0.4,
        max_tcp_clients=32,
        inactivity_grace_seconds=1,
    )
    state = initialize_state()
    state.started_at = datetime(2025, 11, 19, 4, 0, 0, tzinfo=timezone.utc)

    pump_events(
        state,
        config,
        source_ip="10.9.8.7",
        hostname="lab-sensor-01",
        app_name="telemetryd",
        severity="info",
        message="sensor heartbeat ok",
        size_bytes=512,
        count=560,
    )
    pump_events(
        state,
        config,
        source_ip="10.9.8.8",
        hostname="lab-sensor-02",
        app_name="telemetryd",
        severity="info",
        message="sensor heartbeat ok",
        size_bytes=512,
        count=120,
    )
    pump_events(
        state,
        config,
        source_ip="10.9.10.5",
        hostname="lab-gateway-01",
        app_name="gatewayd",
        severity="warning",
        message="buffer watermark crossed channel=control",
        size_bytes=2_048,
        count=120,
    )

    state.dropped_events = 180
    state.stopped_at = state.started_at + timedelta(seconds=duration_seconds)
    return finalize_state(state, config).model_dump()


def main() -> None:
    baseline_result = asyncio.run(build_baseline_result())
    peak_result = build_peak_result()
    noisy_result = build_noisy_result()

    export_artifacts("baseline_branch_burst", baseline_result)
    export_artifacts("east_dc_peak_hour", peak_result)
    export_artifacts("noisy_lab_diagnostic", noisy_result)


if __name__ == "__main__":
    main()
