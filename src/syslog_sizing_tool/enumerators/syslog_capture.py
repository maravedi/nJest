from __future__ import annotations

import asyncio
from asyncio import Queue, QueueFull
from datetime import datetime, timezone
from typing import Any, Dict, Tuple

from ..types.models import SizingResult, SyslogSizingConfig, SyslogSizingState
from ..utils.accumulator import initialize_state, record_event
from ..utils.analysis import finalize_state
from ..utils.logging_helpers import get_json_logger
from ..utils.syslog_parser import parse_syslog_payload

logger = get_json_logger("syslog_sizing_tool.capture")


class SyslogDatagramProtocol(asyncio.DatagramProtocol):
    def __init__(
        self,
        queue: Queue[Tuple[bytes, str]],
        max_payload: int,
        state: SyslogSizingState,
    ) -> None:
        self.queue = queue
        self.max_payload = max_payload
        self.state = state

    def datagram_received(self, data: bytes, addr: Tuple[str, int]) -> None:
        if not data:
            return
        source_ip = addr[0]
        if len(data) > self.max_payload:
            data = data[: self.max_payload]
        try:
            self.queue.put_nowait((data, source_ip))
        except QueueFull:
            logger.warning(
                "ingest_queue_full",
                extra={"module": "syslog_capture", "function": "datagram_received"},
            )
            self.state.dropped_events += 1


async def _handle_tcp_client(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    queue: Queue[Tuple[bytes, str]],
    max_payload: int,
    inactivity_grace: int,
    client_gate: asyncio.Semaphore,
    state: SyslogSizingState,
) -> None:
    async with client_gate:
        peer_info = writer.get_extra_info("peername")
        source_ip = peer_info[0] if isinstance(peer_info, tuple) else "unknown"
        idle_timer = inactivity_grace
        try:
            while not reader.at_eof():
                try:
                    data = await asyncio.wait_for(reader.readline(), timeout=idle_timer)
                except asyncio.TimeoutError:
                    break
                if not data:
                    break
                chunk = data.strip()
                if not chunk:
                    continue
                if len(chunk) > max_payload:
                    chunk = chunk[:max_payload]
                try:
                    queue.put_nowait((chunk, source_ip))
                except QueueFull:
                    logger.warning(
                        "ingest_queue_full",
                        extra={
                            "module": "syslog_capture",
                            "function": "handle_tcp_client",
                        },
                    )
                    state.dropped_events += 1
        finally:
            writer.close()
            await writer.wait_closed()


async def run_capture_session(request: Dict[str, Any]) -> Dict[str, Any]:
    config = SyslogSizingConfig(**request)
    state = initialize_state()
    queue: Queue[Tuple[bytes, str]] = asyncio.Queue(maxsize=65536)

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()
    client_gate = asyncio.Semaphore(config.max_tcp_clients)

    udp_transport, _ = await loop.create_datagram_endpoint(
        lambda: SyslogDatagramProtocol(queue, max_payload=8192, state=state),
        local_addr=(str(config.listen_host), config.udp_port),
    )

    tcp_server = await asyncio.start_server(
        lambda r, w: _handle_tcp_client(
            r,
            w,
            queue,
            max_payload=8192,
            inactivity_grace=config.inactivity_grace_seconds,
            client_gate=client_gate,
            state=state,
        ),
        host=str(config.listen_host),
        port=config.tcp_port,
        limit=8192,
    )

    async def _consumer() -> None:
        while not stop_event.is_set() or not queue.empty():
            try:
                payload, source_ip = await asyncio.wait_for(queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            try:
                parsed = parse_syslog_payload(payload)
                record_event(
                    state,
                    config=config,
                    source_ip=source_ip,
                    size_bytes=len(payload),
                    hostname=str(parsed.get("hostname", "unknown")),
                    app_name=str(parsed.get("app_name", "unknown")),
                    severity=str(parsed.get("severity", "info")),
                    message=str(parsed.get("message", "")),
                )
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "event_parse_failure",
                    extra={
                        "module": "syslog_capture",
                        "function": "consumer",
                        "error": str(exc),
                    },
                )

    consumer_task = asyncio.create_task(_consumer())

    try:
        await asyncio.sleep(config.duration_seconds)
    finally:
        stop_event.set()
        await consumer_task
        udp_transport.close()
        tcp_server.close()
        await tcp_server.wait_closed()
        state.stopped_at = datetime.now(timezone.utc)

    result: SizingResult = finalize_state(state, config)
    return result.model_dump()
