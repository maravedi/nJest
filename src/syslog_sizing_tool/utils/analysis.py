from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from .statistics import percentile_breakdown
from ..types.models import (
    AggregatedRate,
    IngestEstimates,
    Insight,
    PercentileBreakdown,
    SizingResult,
    SyslogSizingConfig,
    SyslogSizingState,
    TalkerBreakdown,
)


def finalize_state(
    state: SyslogSizingState, config: SyslogSizingConfig
) -> SizingResult:
    if state.stopped_at is None:
        state.stopped_at = datetime.now(timezone.utc)
    measurement_seconds = max(
        1.0, (state.stopped_at - state.started_at).total_seconds()
    )

    avg_eps = state.total_messages / measurement_seconds
    avg_bps = state.total_bytes / measurement_seconds
    total_attempted = state.total_messages + state.dropped_events
    dropped_ratio = (
        state.dropped_events / total_attempted if total_attempted else 0.0
    )

    percentile_data = PercentileBreakdown(
        **percentile_breakdown(state.stored_sizes or [0])
    )

    talkers: List[TalkerBreakdown] = []
    for source, stats in sorted(
        state.per_source.items(), key=lambda item: item[1].message_count, reverse=True
    ):
        ratio = (
            stats.message_count / state.total_messages if state.total_messages else 0.0
        )
        suggested_action = (
            "Deduplicate or downsample"
            if ratio >= config.noise_threshold_ratio
            else "Retain"
        )
        talkers.append(
            TalkerBreakdown(
                source_ip=source,
                message_count=stats.message_count,
                bytes_ingested=stats.total_bytes,
                ratio=round(ratio, 4),
                suggested_action=suggested_action,
            )
        )

    estimates = IngestEstimates(
        rates=AggregatedRate(
            avg_events_per_second=round(avg_eps, 2),
            avg_bytes_per_second=round(avg_bps, 2),
            projected_events_per_day=int(avg_eps * 86_400),
            projected_gigabytes_per_day=round(avg_bps * 86_400 / (1024**3), 3),
        ),
        message_size_bytes=percentile_data,
        talkers=talkers[:12],
    )

    insights = _build_insights(
        state=state,
        config=config,
        estimates=estimates,
        dropped_ratio=dropped_ratio,
    )

    return SizingResult(
        started_at=state.started_at,
        stopped_at=state.stopped_at,
        total_messages=state.total_messages,
        total_bytes=state.total_bytes,
        dropped_events=state.dropped_events,
        dropped_ratio=round(dropped_ratio, 4),
        per_severity=state.per_severity,
        per_hostname=state.per_hostname,
        per_app_name=state.per_app_name,
        estimates=estimates,
        insights=insights,
    )


def _build_insights(
    *,
    state: SyslogSizingState,
    config: SyslogSizingConfig,
    estimates: IngestEstimates,
    dropped_ratio: float,
) -> List[Insight]:
    items: List[Insight] = []
    if dropped_ratio > 0.0:
        items.append(
            Insight(
                title="Potential sampling bias",
                detail=(
                    f"{state.dropped_events:,} events ({dropped_ratio:.2%}) were dropped "
                    "because the ingest queue was saturated; percentile and talker estimates "
                    "may under-report true volumes."
                ),
                confidence=0.92 if dropped_ratio >= 0.05 else 0.75,
            )
        )
    high_value_ratio = (
        state.high_value_events / state.total_messages if state.total_messages else 0.0
    )
    if high_value_ratio < 0.05 and state.total_messages:
        items.append(
            Insight(
                title="Signal-to-noise imbalance",
                detail=(
                    f"Only {high_value_ratio:.2%} of events matched the configured keywords; "
                    "consider refining collection rules."
                ),
                confidence=0.78,
            )
        )

    if estimates.rates.projected_gigabytes_per_day >= 200:
        items.append(
            Insight(
                title="High daily ingest",
                detail=(
                    "Projected ingest exceeds 200 GB/day. Ensure storage, indexers, and network paths "
                    "are sized accordingly."
                ),
                confidence=0.82,
            )
        )

    noisy_talkers = [
        talker
        for talker in estimates.talkers
        if talker.ratio >= config.noise_threshold_ratio
    ]
    if noisy_talkers:
        dominant = noisy_talkers[0]
        items.append(
            Insight(
                title="Dominant noise source",
                detail=(
                    f"{dominant.source_ip} produced {dominant.ratio:.1%} of traffic. "
                    "Investigate chatty services or enable sampling."
                ),
                confidence=0.9,
            )
        )

    if not items:
        items.append(
            Insight(
                title="Healthy distribution",
                detail="No immediate bottlenecks detected during the measurement window.",
                confidence=0.6,
            )
        )
    return items
