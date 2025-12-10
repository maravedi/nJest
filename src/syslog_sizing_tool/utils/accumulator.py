from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict

from .statistics import bounded_append
from ..types.models import SyslogSizingConfig, SyslogSizingState, TalkerStats


def initialize_state() -> SyslogSizingState:
    return SyslogSizingState(started_at=datetime.now(timezone.utc))


def _bump(counter: Dict[str, int], key: str) -> None:
    counter[key] = counter.get(key, 0) + 1


def record_event(
    state: SyslogSizingState,
    *,
    config: SyslogSizingConfig,
    source_ip: str,
    size_bytes: int,
    hostname: str,
    app_name: str,
    severity: str,
    message: str,
) -> None:
    if size_bytes <= 0:
        return

    state.total_messages += 1
    state.total_bytes += size_bytes

    _bump(state.per_severity, severity)
    _bump(state.per_hostname, hostname or "unknown")
    _bump(state.per_app_name, app_name or "unknown")

    talker = state.per_source.get(source_ip)
    if not talker:
        talker = TalkerStats()
        state.per_source[source_ip] = talker
    talker.message_count += 1
    talker.total_bytes += size_bytes
    if len(talker.samples) < 100:
        talker.samples.append(message)

    lowered = message.lower()
    for keyword in config.high_value_keywords:
        if keyword in lowered:
            state.high_value_events += 1
            break

    bounded_append(state.stored_sizes, size_bytes, config.sample_size_limit)
