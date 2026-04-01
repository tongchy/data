"""Formatting helpers."""

import json
from typing import Any


def compact_json(value: Any) -> str:
    """Serialize JSON in a compact deterministic format."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
