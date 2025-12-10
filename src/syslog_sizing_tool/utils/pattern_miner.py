from __future__ import annotations

import re
from typing import List

from drain3 import TemplateMiner
from drain3.masking import RegexMaskingInstruction
from drain3.template_miner_config import TemplateMinerConfig


def generate_patterns(messages: List[str]) -> List[str]:
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

    patterns = []
    # Sort clusters by size (descending) to prioritize common patterns
    sorted_clusters = sorted(
        miner.drain.clusters, key=lambda c: c.size, reverse=True
    )

    for cluster in sorted_clusters:
        template = cluster.get_template()
        # Convert Drain3 template to a regex-like string
        # Drain3 uses <*> or <NUM> etc.
        # We can make it slightly more regex-y or just keep the template which is quite readable.
        # The user asked for regex patterns, so let's try to make it look like a regex.

        # Simple heuristic replacement:
        regex_pattern = template.replace("<*>", ".*")
        regex_pattern = regex_pattern.replace("<NUM>", r"\d+")
        regex_pattern = regex_pattern.replace("<IP>", r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}")
        regex_pattern = regex_pattern.replace("<HEX>", r"0x[0-9a-fA-F]+")

        # Escape special regex characters that might be in the static parts of the template
        # This is tricky because we just introduced regex chars.
        # A safer way might be to rely on the template as a "suggestion"
        # but let's try to return the template itself as well if regex conversion is too risky.
        # However, drain3 templates are quite clean.

        # For now, let's return the template as is, but maybe refined.
        # actually, the requirement is "regex patterns".
        # Let's do a best effort conversion.

        # Drain3 template example: "User <*> logged in from <IP>"

        # We need to escape the static parts.
        # But we don't know easily which parts are static vs wildcards unless we parse the template.
        # Drain3 template is a string.

        # Let's inspect the tokens.
        # But cluster.get_template() returns a string joined by spaces.
        # We can access cluster.log_template_tokens

        tokens = cluster.log_template_tokens
        regex_parts = []
        for token in tokens:
            if token == "<*>":
                regex_parts.append(".*")
            elif token == "<NUM>":
                regex_parts.append(r"\d+")
            elif token == "<IP>":
                regex_parts.append(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}")
            elif token == "<HEX>":
                regex_parts.append(r"0x[0-9a-fA-F]+")
            else:
                # Escape the token
                regex_parts.append(re.escape(token))

        # Join with some flexible whitespace matching
        # Syslogs often have variable spaces.
        full_regex = r"\s+".join(regex_parts)
        patterns.append(f"^{full_regex}$")

    return patterns
