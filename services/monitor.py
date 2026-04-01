"""Monitoring service."""

from typing import Any, Dict, List, Optional


class MonitorService:
    """Collects lightweight runtime events."""

    def __init__(self):
        self._events: List[Dict[str, Any]] = []

    def record(self, event_type: str, payload: Dict[str, Any]) -> None:
        self._events.append({"type": event_type, "payload": payload})

    def latest(self) -> Optional[Dict[str, Any]]:
        return self._events[-1] if self._events else None
