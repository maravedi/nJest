from __future__ import annotations

import re
from typing import List, Dict

from drain3 import TemplateMiner
from drain3.masking import RegexMaskingInstruction
from drain3.template_miner_config import TemplateMinerConfig

from ..types.models import SuggestedPattern


def generate_patterns(
    messages: List[str],
    total_messages: int,
    total_bytes: int,
    duration_seconds: float
) -> List[SuggestedPattern]:
    """
    Generate regex patterns from a list of log messages using Drain3.
    """
    if not messages:
        return []

    config = TemplateMinerConfig()
    config.masking_instructions = [
        RegexMaskingInstruction(r"((?<=[^A-Za-z0-9])|^)(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})((?=[^A-Za-z0-9])|$)", "IP"),
        RegexMaskingInstruction(r"((?<=[^A-Za-z0-9])|^)(0x[a-fA-F0-9]+)((?=[^A-Za-z0-9])|$)", "HEX"),
        RegexMaskingInstruction(r"((?<=[^A-Za-z0-9])|^)(\d+)((?=[^A-Za-z0-9])|$)", "NUM"),
    ]
    miner = TemplateMiner(persistence_handler=None, config=config)

    for message in messages:
        miner.add_log_message(message)

    # Find examples for each cluster
    examples: Dict[int, str] = {}
    for message in messages:
        cluster = miner.match(message)
        if cluster and cluster.cluster_id not in examples:
            examples[cluster.cluster_id] = message

    patterns = []
    # Sort clusters by size (descending) to prioritize common patterns
    sorted_clusters = sorted(
        miner.drain.clusters, key=lambda c: c.size, reverse=True
    )

    avg_msg_size = total_bytes / total_messages if total_messages > 0 else 0

    for cluster in sorted_clusters:
        # Drain3 template example: "User <*> logged in from <IP>"
        # We need to escape the static parts.

        # Calculate stats
        sample_ratio = cluster.size / len(messages)
        match_count = int(sample_ratio * total_messages)
        match_percent = sample_ratio
        match_eps = match_count / duration_seconds if duration_seconds > 0 else 0.0

        estimated_bytes = match_count * avg_msg_size
        match_mbps = (estimated_bytes / duration_seconds) / (1024 * 1024) if duration_seconds > 0 else 0.0

        example = examples.get(cluster.cluster_id, "")

        tokens = cluster.log_template_tokens
        regex_parts = []
        for token in tokens:
            # Escape the token first to handle special regex characters in the static text
            escaped = re.escape(token)

            # Replace the escaped placeholders with regex patterns
            # Note: re.escape('<*>') produces '\<\*\>' (depending on python version)
            # We use string replace for safety.

            # Handling <*> -> .*
            escaped = escaped.replace(re.escape("<*>"), ".*")

            # Handling <NUM> -> \d+
            escaped = escaped.replace(re.escape("<NUM>"), r"\d+")

            # Handling <IP> -> IP Regex
            escaped = escaped.replace(re.escape("<IP>"), r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}")

            # Handling <HEX> -> Hex Regex
            escaped = escaped.replace(re.escape("<HEX>"), r"0x[0-9a-fA-F]+")

            regex_parts.append(escaped)

        # Join with some flexible whitespace matching
        # Syslogs often have variable spaces.
        full_regex = r"\s+".join(regex_parts)
        pattern_str = f"^{full_regex}$"

        patterns.append(SuggestedPattern(
            pattern=pattern_str,
            example=example,
            match_count=match_count,
            match_percent=match_percent,
            match_eps=match_eps,
            match_mbps=match_mbps
        ))

    return patterns
