from __future__ import annotations

import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from syslog_sizing_tool.reporting import api as api_module  # noqa: E402


@pytest.fixture(autouse=True)
def reset_api_sessions() -> None:
    """Ensure API session registry is clean before and after each test."""
    api_module._sessions.clear()
    yield
    api_module._sessions.clear()
