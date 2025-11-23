from __future__ import annotations

import asyncio
from typing import Any, Coroutine, Dict

import pytest
from fastapi import HTTPException

from syslog_sizing_tool.reporting import api
from syslog_sizing_tool.types.models import SyslogSizingConfig
from tests.utils.flog_workload import (
    allocate_listen_ports,
    load_flog_samples,
    replay_flog_workload,
)


@pytest.mark.asyncio
async def test_start_capture_runs_background_and_updates_session(monkeypatch: pytest.MonkeyPatch) -> None:
    recorded_payload: dict[str, object] = {}

    async def fake_run_capture_session(payload: dict[str, object]) -> dict[str, object]:
        recorded_payload.update(payload)
        return {"status": "done"}

    monkeypatch.setattr(api, "run_capture_session", fake_run_capture_session)

    original_create_task = asyncio.create_task
    spawned_tasks: list[asyncio.Task] = []

    def tracking_create_task(coro: Coroutine[Any, Any, Any]) -> asyncio.Task:
        task = original_create_task(coro)
        spawned_tasks.append(task)
        return task

    monkeypatch.setattr(asyncio, "create_task", tracking_create_task)

    config = SyslogSizingConfig()
    response = await api.start_capture(config)
    assert response["status"] == "running"
    session_id = response["session_id"]
    assert session_id in api._sessions

    await asyncio.gather(*spawned_tasks)
    session_entry = api._sessions[session_id]
    assert session_entry["status"] == "completed"
    assert session_entry["result"] == {"status": "done"}
    assert recorded_payload["udp_port"] == config.udp_port


@pytest.mark.asyncio
async def test_start_capture_failure_path_records_error(monkeypatch: pytest.MonkeyPatch) -> None:

    async def failing_run_capture_session(_: dict[str, object]) -> dict[str, object]:
        raise RuntimeError("boom")

    monkeypatch.setattr(api, "run_capture_session", failing_run_capture_session)

    original_create_task = asyncio.create_task
    spawned_tasks: list[asyncio.Task] = []

    def tracking_create_task(coro: Coroutine[Any, Any, Any]) -> asyncio.Task:
        task = original_create_task(coro)
        spawned_tasks.append(task)
        return task

    monkeypatch.setattr(asyncio, "create_task", tracking_create_task)

    config = SyslogSizingConfig()
    response = await api.start_capture(config)
    session_id = response["session_id"]

    await asyncio.gather(*spawned_tasks)
    session_entry = api._sessions[session_id]
    assert session_entry["status"] == "failed"
    assert "error" in session_entry


@pytest.mark.asyncio
async def test_get_capture_unknown_session_raises() -> None:
    with pytest.raises(HTTPException) as excinfo:
        await api.get_capture("missing")
    assert excinfo.value.status_code == 404


@pytest.mark.asyncio
async def test_start_capture_generates_flog_sample_report(monkeypatch: pytest.MonkeyPatch) -> None:
    udp_port, tcp_port = allocate_listen_ports()

    async def flog_runner(request: Dict[str, Any]) -> Dict[str, Any]:
        request.update({"udp_port": udp_port, "tcp_port": tcp_port, "listen_host": "127.0.0.1"})
        request["duration_seconds"] = 2
        return await replay_flog_workload(request)

    monkeypatch.setattr(api, "run_capture_session", flog_runner)

    original_create_task = asyncio.create_task
    spawned_tasks: list[asyncio.Task] = []

    def tracking_create_task(coro: Coroutine[Any, Any, Any]) -> asyncio.Task:
        task = original_create_task(coro)
        spawned_tasks.append(task)
        return task

    monkeypatch.setattr(asyncio, "create_task", tracking_create_task)

    config = SyslogSizingConfig(
        listen_host="127.0.0.1",
        udp_port=udp_port,
        tcp_port=tcp_port,
        duration_seconds=2,
        flush_interval_seconds=1,
        sample_size_limit=1024,
        high_value_keywords=["denied", "error", "fail"],
        noise_threshold_ratio=0.7,
        max_tcp_clients=4,
        inactivity_grace_seconds=1,
    )
    response = await api.start_capture(config)
    session_id = response["session_id"]

    await asyncio.gather(*spawned_tasks)
    session_entry = api._sessions[session_id]
    assert session_entry["status"] == "completed"
    result = session_entry["result"]
    assert result["total_messages"] == len(load_flog_samples())
    assert result["dropped_events"] == 0
