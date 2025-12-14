from __future__ import annotations

import asyncio
import uuid
from typing import Any, Dict

from fastapi import FastAPI, HTTPException

from ..enumerators.syslog_capture import run_capture_session
from ..types.models import SyslogSizingConfig
from ..utils.asyncio_compat import configure_event_loop_policy_for_platform

configure_event_loop_policy_for_platform()

app = FastAPI(title="Syslog Sizing API", version="0.1.0")
_sessions: Dict[str, Dict[str, Any]] = {}


@app.post("/capture/start")
async def start_capture(config: SyslogSizingConfig) -> Dict[str, Any]:
    session_id = str(uuid.uuid4())
    _sessions[session_id] = {"status": "running"}

    async def _runner() -> None:
        try:
            result = await run_capture_session(config.model_dump())
            _sessions[session_id] = {"status": "completed", "result": result}
        except Exception as exc:  # noqa: BLE001
            _sessions[session_id] = {"status": "failed", "error": str(exc)}

    asyncio.create_task(_runner())
    return {"session_id": session_id, "status": "running"}


@app.get("/capture/{session_id}")
async def get_capture(session_id: str) -> Dict[str, Any]:
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="unknown session id")
    return {"session_id": session_id, **_sessions[session_id]}
