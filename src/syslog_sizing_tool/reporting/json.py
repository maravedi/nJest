from __future__ import annotations

import json
from typing import Any, Dict


def render_json_report(result: Dict[str, Any]) -> str:
    return json.dumps(result, default=str, indent=2, sort_keys=True)
