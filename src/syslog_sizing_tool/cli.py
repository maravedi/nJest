from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path
from typing import Any, Dict

from .enumerators.syslog_capture import run_capture_session
from .reporting.console import render_console_report
from .reporting.html import render_html_report
from .reporting.json import render_json_report
from .utils.integration_test_runner import run_integration_test


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="syslog-sizing-tool",
        description="Collect syslog traffic for a fixed window and estimate ingest sizing requirements.",
    )
    parser.add_argument(
        "--listen-host", default="0.0.0.0", help="Interface/IP to bind."
    )
    parser.add_argument(
        "--udp-port", type=int, default=5514, help="UDP port to listen on."
    )
    parser.add_argument(
        "--tcp-port", type=int, default=5614, help="TCP port to listen on."
    )
    parser.add_argument(
        "--duration-seconds",
        type=int,
        default=300,
        help="Duration of the measurement window in seconds.",
    )
    parser.add_argument(
        "--flush-interval-seconds",
        type=int,
        default=5,
        help="Interval for emitting intermediate stats (reserved for future use).",
    )
    parser.add_argument(
        "--sample-size-limit",
        type=int,
        default=4096,
        help="Number of message sizes retained for percentile estimates.",
    )
    parser.add_argument(
        "--high-value-keywords",
        nargs="*",
        default=["error", "fail", "panic", "critical"],
        help="Space separated keywords to track for high value events.",
    )
    parser.add_argument(
        "--noise-threshold-ratio",
        type=float,
        default=0.35,
        help="Talkers above this ratio are recommended for noise reduction.",
    )
    parser.add_argument(
        "--output-format",
        choices=["console", "json", "html"],
        default="console",
        help="Console table output, JSON blob, or interactive HTML report.",
    )
    parser.add_argument(
        "--json-path",
        type=Path,
        help="Optional file path to persist the JSON output.",
    )
    parser.add_argument(
        "--html-path",
        type=Path,
        help="Optional file path to persist the HTML output.",
    )
    parser.add_argument(
        "--max-tcp-clients",
        type=int,
        default=64,
        help="Maximum concurrent TCP clients to accept.",
    )
    parser.add_argument(
        "--inactivity-grace-seconds",
        type=int,
        default=3,
        help="Seconds before closing idle TCP clients.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level for runtime diagnostics.",
    )
    parser.add_argument(
        "--integration-test",
        action="store_true",
        help="Run an integration test with simulated traffic.",
    )
    return parser.parse_args(argv)


def _namespace_to_request(namespace: argparse.Namespace) -> Dict[str, Any]:
    payload = vars(namespace).copy()
    payload.pop("output_format")
    payload.pop("json_path")
    payload.pop("html_path")
    payload.pop("log_level")
    payload.pop("integration_test")
    return payload


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    request = _namespace_to_request(args)

    if args.integration_test:
        result: Dict[str, Any] = asyncio.run(run_integration_test(request))
    else:
        result: Dict[str, Any] = asyncio.run(run_capture_session(request))

    if args.output_format == "console":
        render_console_report(result)
    elif args.output_format == "json":
        json_blob = render_json_report(result)
        print(json_blob)
        if args.json_path:
            args.json_path.write_text(json_blob, encoding="utf-8")
    else:
        html_blob = render_html_report(result)
        if args.html_path:
            args.html_path.write_text(html_blob, encoding="utf-8")
            print(f"HTML report saved to {args.html_path}")
        else:
            print(html_blob)


if __name__ == "__main__":
    main()
