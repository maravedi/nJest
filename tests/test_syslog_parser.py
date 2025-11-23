from __future__ import annotations

from datetime import datetime

from syslog_sizing_tool.utils.syslog_parser import parse_syslog_payload


def test_parse_rfc5424_payload_extracts_fields() -> None:
    payload = (
        b"<14>1 2024-05-01T12:00:00Z host app proc msgid "
        b'[origin] test message with structured data'
    )
    parsed = parse_syslog_payload(payload)
    assert parsed["severity"] == "info"
    assert parsed["facility"] == 1
    assert parsed["hostname"] == "host"
    assert parsed["app_name"] == "app"
    assert "structured data" in parsed["message"]
    assert isinstance(parsed["timestamp"], datetime)


def test_parse_rfc3164_payload_extracts_body() -> None:
    payload = b"<46>Jan 12 09:12:33 fw01 sshd: Failed password for user"
    parsed = parse_syslog_payload(payload)
    assert parsed["severity"] == "info"
    assert parsed["hostname"] == "fw01"
    assert parsed["app_name"] == "sshd"
    assert parsed["message"] == "Failed password for user"


def test_parse_payload_without_pri_falls_back() -> None:
    parsed = parse_syslog_payload(b"plain syslog text")
    assert parsed["severity"] == "info"
    assert parsed["facility"] == 1
    assert parsed["message"] == "plain syslog text"
