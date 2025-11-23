from __future__ import annotations

from pathlib import Path

from syslog_sizing_tool import cli


def test_parse_args_defaults() -> None:
    args = cli.parse_args([])
    assert args.listen_host == "0.0.0.0"
    assert args.udp_port == 5514
    assert args.tcp_port == 5614
    assert args.output_format == "console"
    assert args.sample_size_limit == 4096


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
            "--output-format",
            "json",
            "--log-level",
            "DEBUG",
        ]
    )
    payload = cli._namespace_to_request(args)
    assert "output_format" not in payload
    assert "json_path" not in payload
    assert "log_level" not in payload
    assert payload["listen_host"] == "127.0.0.1"
    assert payload["udp_port"] == 5515
    assert payload["tcp_port"] == 5616
