"""Metrics service."""

from typing import Dict


class MetricsService:
    """Minimal counter-based metrics collector."""

    def __init__(self):
        self._counters: Dict[str, int] = {}

    def increment(self, name: str, value: int = 1) -> None:
        self._counters[name] = self._counters.get(name, 0) + value

    def snapshot(self) -> Dict[str, int]:
        return dict(self._counters)
