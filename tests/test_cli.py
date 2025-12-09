from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

from syslog_sizing_tool import cli
from syslog_sizing_tool.utils.integration_test_runner import (
    allocate_listen_ports,
    load_flog_samples,
    run_integration_test,
)


def test_parse_args_defaults() -> None:
    args = cli.parse_args([])
    assert args.listen_host == "0.0.0.0"
    assert args.udp_port == 5514
    assert args.tcp_port == 5614
    assert args.output_format == "console"
    assert args.sample_size_limit == 4096
    assert args.html_path is None


def test_namespace_to_request_strips_cli_only_fields(tmp_path: Path) -> None:
    args = cli.parse_args(
        [
            "--listen-host",
            "127.0.0.1",
            "--udp-port",
            "5515",
            "--tcp-port",
            "5616",
            "--json-path",
            str(tmp_path / "report.json"),
            "--html-path",
            str(tmp_path / "report.html"),
            "--output-format",
            "json",
            "--log-level",
            "DEBUG",
        ]
    )
    payload = cli._namespace_to_request(args)
    assert "output_format" not in payload
    assert "json_path" not in payload
    assert "html_path" not in payload
    assert "log_level" not in payload
    assert payload["listen_host"] == "127.0.0.1"
    assert payload["udp_port"] == 5515
    assert payload["tcp_port"] == 5616


def _cli_args_from_request(
    request: Dict[str, Any],
    *,
    output: str,
    json_path: Path | None = None,
    html_path: Path | None = None,
) -> list[str]:
    argv = [
        "--listen-host",
        str(request["listen_host"]),
        "--udp-port",
        str(request["udp_port"]),
        "--tcp-port",
        str(request["tcp_port"]),
        "--duration-seconds",
        str(request["duration_seconds"]),
        "--flush-interval-seconds",
        str(request["flush_interval_seconds"]),
        "--sample-size-limit",
        str(request["sample_size_limit"]),
        "--noise-threshold-ratio",
        str(request["noise_threshold_ratio"]),
        "--max-tcp-clients",
        str(request["max_tcp_clients"]),
        "--inactivity-grace-seconds",
        str(request["inactivity_grace_seconds"]),
        "--output-format",
        output,
    ]
    if request.get("high_value_keywords"):
        argv.extend(["--high-value-keywords", *request["high_value_keywords"]])
    if json_path:
        argv.extend(["--json-path", str(json_path)])
    if html_path:
        argv.extend(["--html-path", str(html_path)])
    return argv


def test_cli_json_output_from_flog_samples(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    base_request: Dict[str, Any] = {
        "listen_host": "127.0.0.1",
        "duration_seconds": 2,
        "flush_interval_seconds": 1,
        "sample_size_limit": 1024,
        "high_value_keywords": ["denied", "error", "fail"],
        "noise_threshold_ratio": 0.7,
        "max_tcp_clients": 4,
        "inactivity_grace_seconds": 1,
    }
    udp_port, tcp_port = allocate_listen_ports()
    base_request.update({"udp_port": udp_port, "tcp_port": tcp_port})

    async def flog_runner(request: Dict[str, Any]) -> Dict[str, Any]:
        request.update({"udp_port": udp_port, "tcp_port": tcp_port, "listen_host": "127.0.0.1"})
        return await run_integration_test(request)

    monkeypatch.setattr(cli, "run_capture_session", flog_runner)
    report_path = tmp_path / "flog_report.json"

    argv = _cli_args_from_request(base_request, output="json", json_path=report_path)
    cli.main(argv)
    captured = capsys.readouterr()
    data = json.loads(report_path.read_text(encoding="utf-8"))

    assert data["total_messages"] == len(load_flog_samples())
    assert data["dropped_events"] == 0
    assert '"avg_events_per_second"' in captured.out


def test_cli_console_output_from_flog_samples(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    base_request: Dict[str, Any] = {
        "listen_host": "127.0.0.1",
        "duration_seconds": 2,
        "flush_interval_seconds": 1,
        "sample_size_limit": 1024,
        "high_value_keywords": ["denied", "error", "fail"],
        "noise_threshold_ratio": 0.7,
        "max_tcp_clients": 4,
        "inactivity_grace_seconds": 1,
    }
    udp_port, tcp_port = allocate_listen_ports()
    base_request.update({"udp_port": udp_port, "tcp_port": tcp_port})

    async def flog_runner(request: Dict[str, Any]) -> Dict[str, Any]:
        request.update({"udp_port": udp_port, "tcp_port": tcp_port, "listen_host": "127.0.0.1"})
        return await run_integration_test(request)

    monkeypatch.setattr(cli, "run_capture_session", flog_runner)

    argv = _cli_args_from_request(base_request, output="console")
    cli.main(argv)
    captured = capsys.readouterr()

    assert "Syslog Sizing Summary" in captured.out
    assert "Top Talkers" in captured.out


def test_cli_html_output_writes_report(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    base_request: Dict[str, Any] = {
        "listen_host": "127.0.0.1",
        "duration_seconds": 2,
        "flush_interval_seconds": 1,
        "sample_size_limit": 1024,
        "high_value_keywords": ["denied", "error", "fail"],
        "noise_threshold_ratio": 0.7,
        "max_tcp_clients": 4,
        "inactivity_grace_seconds": 1,
    }
    udp_port, tcp_port = allocate_listen_ports()
    base_request.update({"udp_port": udp_port, "tcp_port": tcp_port})

    async def flog_runner(request: Dict[str, Any]) -> Dict[str, Any]:
        request.update({"udp_port": udp_port, "tcp_port": tcp_port, "listen_host": "127.0.0.1"})
        return await run_integration_test(request)

    monkeypatch.setattr(cli, "run_capture_session", flog_runner)
    html_path = tmp_path / "report.html"

    argv = _cli_args_from_request(base_request, output="html", html_path=html_path)
    cli.main(argv)

    html_blob = html_path.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in html_blob
    assert 'id="scale-input"' in html_blob
