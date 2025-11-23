from __future__ import annotations

import asyncio

import pytest

from syslog_sizing_tool.enumerators.syslog_capture import SyslogDatagramProtocol
from syslog_sizing_tool.utils.accumulator import initialize_state


@pytest.mark.asyncio
async def test_syslog_datagram_protocol_truncates_and_counts_drops() -> None:
    queue: asyncio.Queue = asyncio.Queue(maxsize=1)
    state = initialize_state()
    protocol = SyslogDatagramProtocol(queue, max_payload=4, state=state)

    protocol.datagram_received(b"abcdef", ("192.0.2.1", 5514))
    payload, source = await queue.get()
    assert payload == b"abcd"
    assert source == "192.0.2.1"

    await queue.put((b"full", "filled"))
    protocol.datagram_received(b"ignore", ("192.0.2.1", 5514))
    assert state.dropped_events == 1
