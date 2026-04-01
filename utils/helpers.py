"""General helpers."""

from typing import Optional


def safe_int(value: object, default: int = 0) -> int:
    """Convert to int with fallback."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
