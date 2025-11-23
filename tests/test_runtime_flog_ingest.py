from __future__ import annotations

import asyncio
import socket
from pathlib import Path
from typing import Iterable

import pytest

from syslog_sizing_tool.enumerators.syslog_capture import run_capture_session


DATA_PATH = Path(__file__).parent / "data" / "flog_syslog_sample.txt"


def _load_flog_samples() -> list[str]:
    if not DATA_PATH.exists():
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


def _allocate_listen_ports() -> tuple[int, int]:
    udp_port = _reserve_port(family=socket.AF_INET, sock_type=socket.SOCK_DGRAM)
    tcp_port = _reserve_port(family=socket.AF_INET, sock_type=socket.SOCK_STREAM)
    if udp_port == tcp_port:
        return _allocate_listen_ports()
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


@pytest.mark.asyncio
async def test_capture_session_handles_flog_samples_without_drops() -> None:
    samples = _load_flog_samples()
    udp_payloads = samples[: len(samples) // 2]
    tcp_payloads = samples[len(samples) // 2 :]
    udp_port, tcp_port = _allocate_listen_ports()

    request = {
        "listen_host": "127.0.0.1",
        "udp_port": udp_port,
        "tcp_port": tcp_port,
        "duration_seconds": 2,
        "flush_interval_seconds": 1,
        "sample_size_limit": 1024,
        "high_value_keywords": ["denied", "error", "fail"],
        "noise_threshold_ratio": 0.7,
        "max_tcp_clients": 4,
        "inactivity_grace_seconds": 1,
    }

    capture_task = asyncio.create_task(run_capture_session(request))
    await asyncio.sleep(0.05)
    await asyncio.gather(
        _stream_udp(udp_payloads, "127.0.0.1", udp_port),
        _stream_tcp(tcp_payloads, "127.0.0.1", tcp_port),
    )
    result = await capture_task

    assert result["total_messages"] == len(samples)
    assert result["dropped_events"] == 0
    assert result["per_hostname"].get("edge-router-01", 0) > 0
    assert result["per_app_name"].get("firewalld", 0) > 0
    assert result["estimates"]["rates"]["avg_events_per_second"] > 0
