"""Validation helpers."""


def is_non_empty_text(value: object) -> bool:
    """Return True when value is a non-empty string."""
    return isinstance(value, str) and bool(value.strip())
