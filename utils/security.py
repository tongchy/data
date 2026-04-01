"""Security helpers."""

import hashlib


def stable_hash(text: str) -> str:
    """Return a stable SHA256 hash for the input text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
