"""In-memory cache service."""

from typing import Any, Dict, Optional


class CacheService:
    """Simple process-local cache."""

    def __init__(self):
        self._data: Dict[str, Any] = {}

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def clear(self) -> None:
        self._data.clear()
