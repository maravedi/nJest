from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Dict

from ..types.models import SeverityLevel

PRI_PATTERN = re.compile(r"^<(?P<pri>\d{1,3})>")
RFC5424_PATTERN = re.compile(
    r"^<(?P<pri>\d{1,3})>(?P<version>\d)\s+(?P<ts>\S+)\s+(?P<host>\S+)\s+(?P<app>\S+)\s+(?P<proc>\S+)\s+(?P<msgid>\S+)\s+(?P<body>.*)$"
)
RFC3164_PATTERN = re.compile(
    r"^<(?P<pri>\d{1,3})>(?P<ts>[A-Za-z]{3}\s+\d{1,2}\s+[0-9:]{8})\s+(?P<host>\S+)\s+(?P<app>[^:]+):\s*(?P<body>.*)$"
)

SEVERITY_NAMES = {
    0: SeverityLevel.emergency,
    1: SeverityLevel.alert,
    2: SeverityLevel.critical,
    3: SeverityLevel.error,
    4: SeverityLevel.warning,
    5: SeverityLevel.notice,
    6: SeverityLevel.info,
    7: SeverityLevel.debug,
}


def _severity_from_pri(pri: int) -> SeverityLevel:
    severity_index = pri % 8
    return SEVERITY_NAMES.get(severity_index, SeverityLevel.info)


def _parse_timestamp(raw_ts: str) -> datetime:
    if raw_ts == "-":
        return datetime.now(timezone.utc)
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%b %d %H:%M:%S"):
        try:
            parsed = datetime.strptime(raw_ts, fmt)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            continue
    return datetime.now(timezone.utc)


def parse_syslog_payload(payload: bytes) -> Dict[str, str | int | datetime]:
    decoded = payload.decode("utf-8", errors="ignore").strip()
    if not decoded:
        return {
            "severity": SeverityLevel.info.value,
            "facility": 0,
            "hostname": "unknown",
            "app_name": "unknown",
            "message": "",
            "timestamp": datetime.now(timezone.utc),
        }

    match = RFC5424_PATTERN.match(decoded)
    if match:
        pri = int(match.group("pri"))
        return {
            "severity": _severity_from_pri(pri).value,
            "facility": pri // 8,
            "hostname": match.group("host"),
            "app_name": match.group("app"),
            "message": match.group("body").strip(),
            "timestamp": _parse_timestamp(match.group("ts")),
        }

    match = RFC3164_PATTERN.match(decoded)
    if match:
        pri = int(match.group("pri"))
        return {
            "severity": _severity_from_pri(pri).value,
            "facility": pri // 8,
            "hostname": match.group("host"),
            "app_name": match.group("app"),
            "message": match.group("body").strip(),
            "timestamp": _parse_timestamp(match.group("ts")),
        }

    pri_match = PRI_PATTERN.match(decoded)
    if pri_match:
        pri = int(pri_match.group("pri"))
        remainder = PRI_PATTERN.sub("", decoded, count=1).strip()
        return {
            "severity": _severity_from_pri(pri).value,
            "facility": pri // 8,
            "hostname": "unknown",
            "app_name": "unknown",
            "message": remainder,
            "timestamp": datetime.now(timezone.utc),
        }

    return {
        "severity": SeverityLevel.info.value,
        "facility": 1,
        "hostname": "unknown",
        "app_name": "unknown",
        "message": decoded,
        "timestamp": datetime.now(timezone.utc),
    }
