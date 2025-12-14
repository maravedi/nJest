from __future__ import annotations

import asyncio
import sys


def configure_event_loop_policy_for_platform() -> None:
    """
    Ensure asyncio uses a UDP/TCP-friendly policy on Windows.

    Notes:
    - Must be called before creating the event loop (i.e., before asyncio.run()).
    - No-op on non-Windows platforms.
    """
    if sys.platform != "win32":
        return

    # Prefer the selector loop on Windows for broad transport compatibility.
    # This attribute only exists on Windows builds of CPython.
    policy_factory = getattr(asyncio, "WindowsSelectorEventLoopPolicy", None)
    if policy_factory is None:
        return

    asyncio.set_event_loop_policy(policy_factory())
