from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Deque, Dict, List, Optional

from pydantic import BaseModel, Field, IPvAnyAddress, PositiveInt, model_validator


class SeverityLevel(str, Enum):
    emergency = "emergency"
    alert = "alert"
    critical = "critical"
    error = "error"
    warning = "warning"
    notice = "notice"
    info = "info"
    debug = "debug"


class SyslogSizingConfig(BaseModel):
    listen_host: IPvAnyAddress | str = Field(
        default="0.0.0.0", description="Interface to bind for syslog ingestion."
    )
    udp_port: PositiveInt = Field(
        default=5514, le=65535, description="UDP port for syslog datagrams."
    )
    tcp_port: PositiveInt = Field(
        default=5614, le=65535, description="TCP port for syslog streams."
    )
    duration_seconds: PositiveInt = Field(
        default=300, le=86400, description="Measurement window in seconds."
    )
    flush_interval_seconds: PositiveInt = Field(
        default=5,
        ge=1,
        le=60,
        description="Interval for publishing intermediate metrics.",
    )
    sample_size_limit: PositiveInt = Field(
        default=4096,
        le=100_000,
        description="Max number of message sizes to retain for percentile estimation.",
    )
    high_value_keywords: List[str] = Field(
        default_factory=lambda: ["error", "fail", "panic", "critical"],
        description="Keywords that mark messages as high value.",
    )
    noise_threshold_ratio: float = Field(
        default=0.35,
        ge=0.05,
        le=0.95,
        description="Ratio for declaring a talker as noisy.",
    )
    max_tcp_clients: PositiveInt = Field(
        default=64, le=1024, description="Maximum concurrent TCP clients accepted."
    )
    inactivity_grace_seconds: PositiveInt = Field(
        default=3, le=30, description="Grace period before closing idle TCP clients."
    )

    @model_validator(mode="after")
    def ensure_distinct_ports(self) -> "SyslogSizingConfig":
        if self.udp_port == self.tcp_port:
            raise ValueError(
                "UDP and TCP ports must be distinct to avoid binding collisions."
            )
        return self


class AggregatedRate(BaseModel):
    avg_events_per_second: float = Field(default=0.0)
    avg_bytes_per_second: float = Field(default=0.0)
    projected_events_per_day: int = Field(default=0)
    projected_gigabytes_per_day: float = Field(default=0.0)


class PercentileBreakdown(BaseModel):
    p50: int = Field(default=0)
    p90: int = Field(default=0)
    p95: int = Field(default=0)
    p99: int = Field(default=0)


class SuggestedPattern(BaseModel):
    pattern: str
    example: str
    match_count: int
    match_percent: float
    match_eps: float
    match_mbps: float


class TalkerBreakdown(BaseModel):
    source_ip: str
    message_count: int
    bytes_ingested: int
    ratio: float
    suggested_action: str
    suggested_patterns: List[SuggestedPattern] = Field(default_factory=list)


class Insight(BaseModel):
    title: str
    detail: str
    confidence: float = Field(ge=0.0, le=1.0)


class IngestEstimates(BaseModel):
    rates: AggregatedRate
    message_size_bytes: PercentileBreakdown
    talkers: List[TalkerBreakdown]


class SizingResult(BaseModel):
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    stopped_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    total_messages: int
    total_bytes: int
    dropped_events: int = Field(default=0, ge=0)
    dropped_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    per_severity: Dict[str, int]
    per_hostname: Dict[str, int]
    per_app_name: Dict[str, int]
    estimates: IngestEstimates
    insights: List[Insight]


@dataclass(slots=True)
class TalkerStats:
    message_count: int = 0
    total_bytes: int = 0
    samples: List[str] = field(default_factory=list)


@dataclass(slots=True)
class SyslogSizingState:
    started_at: datetime
    stopped_at: Optional[datetime] = None
    total_messages: int = 0
    total_bytes: int = 0
    dropped_events: int = 0
    per_severity: Dict[str, int] = field(default_factory=dict)
    per_hostname: Dict[str, int] = field(default_factory=dict)
    per_app_name: Dict[str, int] = field(default_factory=dict)
    per_source: Dict[str, TalkerStats] = field(default_factory=dict)
    high_value_events: int = 0
    stored_sizes: Deque[int] = field(default_factory=deque)
