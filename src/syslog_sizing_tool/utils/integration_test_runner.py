from __future__ import annotations

import asyncio
import socket
from pathlib import Path
from typing import Any, Iterable, Tuple

from ..enumerators.syslog_capture import (
    run_capture_session as capture_impl,
)

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "flog_syslog_sample.txt"
DEFAULT_REQUEST = {
    "listen_host": "127.0.0.1",
    "duration_seconds": 2,
    "flush_interval_seconds": 1,
    "sample_size_limit": 1024,
    "high_value_keywords": ["denied", "error", "fail"],
    "noise_threshold_ratio": 0.7,
    "max_tcp_clients": 4,
    "inactivity_grace_seconds": 1,
}


def load_flog_samples() -> list[str]:
    has_file = DATA_PATH.exists()
    if not has_file:
        raise FileNotFoundError(f"missing flog dataset at {DATA_PATH}")
    return [
        line.strip()
        for line in DATA_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]


def _reserve_port(*, family: int, sock_type: int) -> int:
    with socket.socket(family, sock_type) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def allocate_listen_ports() -> Tuple[int, int]:
    udp_port = _reserve_port(family=socket.AF_INET, sock_type=socket.SOCK_DGRAM)
    tcp_port = _reserve_port(family=socket.AF_INET, sock_type=socket.SOCK_STREAM)
    if udp_port == tcp_port:
        return allocate_listen_ports()
    return udp_port, tcp_port


async def _stream_udp(payloads: Iterable[str], host: str, port: int) -> None:
    loop = asyncio.get_running_loop()
    transport, _ = await loop.create_datagram_endpoint(
        lambda: asyncio.DatagramProtocol(), remote_addr=(host, port)
    )
    try:
        for payload in payloads:
            transport.sendto(payload.encode("utf-8"))
            await asyncio.sleep(0)
    finally:
        transport.close()


async def _stream_tcp(payloads: Iterable[str], host: str, port: int) -> None:
    _reader, writer = await asyncio.open_connection(host, port)
    try:
        for payload in payloads:
            writer.write(payload.encode("utf-8") + b"\n")
            await writer.drain()
            await asyncio.sleep(0)
    finally:
        writer.close()
        await writer.wait_closed()


def build_request(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    udp_port, tcp_port = allocate_listen_ports()
    payload: dict[str, Any] = DEFAULT_REQUEST | {
        "udp_port": udp_port,
        "tcp_port": tcp_port,
    }
    if overrides:
        payload.update(overrides)
    return payload


async def run_integration_test(request: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Runs an integration test by starting the capture session and replaying simulated
    workload against it.
    """
    payload = build_request(request)
    samples = load_flog_samples()
    midpoint = len(samples) // 2 or len(samples)
    udp_payloads = samples[:midpoint]
    tcp_payloads = samples[midpoint:]

    runner = asyncio.create_task(capture_impl(payload))
    await asyncio.sleep(0.05)
    await asyncio.gather(
        _stream_udp(udp_payloads, payload["listen_host"], payload["udp_port"]),
        _stream_tcp(tcp_payloads or udp_payloads, payload["listen_host"], payload["tcp_port"]),
    )
    return await runner
