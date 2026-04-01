"""工具调用缓存后端

提供抽象接口 CacheBackend 与内存实现 InMemoryCacheBackend。
InMemoryCacheBackend 支持 TTL 过期和 FIFO 溢出淘汰。
"""
from __future__ import annotations

import hashlib
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class CacheEntry(BaseModel):
    """单条缓存条目"""

    key: str
    value: Any
    created_at: datetime = Field(default_factory=datetime.now)
    ttl: int                     # 存活时间（秒）
    hit_count: int = 0

    def is_expired(self) -> bool:
        return datetime.now() > self.created_at + timedelta(seconds=self.ttl)


class CacheBackend(ABC):
    """缓存后端抽象接口"""

    @abstractmethod
    def get(self, tool_name: str, args: Dict[str, Any]) -> Optional[Any]:
        ...

    @abstractmethod
    def set(
        self,
        tool_name: str,
        args: Dict[str, Any],
        value: Any,
        ttl: Optional[int] = None,
    ) -> None:
        ...

    @abstractmethod
    def clear(self) -> None:
        ...

    @abstractmethod
    def stats(self) -> Dict[str, Any]:
        ...


class InMemoryCacheBackend(CacheBackend):
    """基于内存的缓存后端（TTL 过期 + FIFO 溢出淘汰）

    Args:
        max_size:    最大缓存条目数，超出时淘汰最早写入的条目
        default_ttl: 默认 TTL（秒），可在 set() 时单独覆盖
    """

    def __init__(self, max_size: int = 1000, default_ttl: int = 3600) -> None:
        self._cache: Dict[str, CacheEntry] = {}
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._total_requests = 0
        self._cache_hits = 0

    # ------------------------------------------------------------------ internal

    @staticmethod
    def _build_key(tool_name: str, args: Dict[str, Any]) -> str:
        raw = f"{tool_name}:{json.dumps(args, sort_keys=True, default=str)}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def _evict_oldest(self) -> None:
        if not self._cache:
            return
        oldest_key = min(self._cache, key=lambda k: self._cache[k].created_at)
        del self._cache[oldest_key]

    # ------------------------------------------------------------------ public

    def get(self, tool_name: str, args: Dict[str, Any]) -> Optional[Any]:
        self._total_requests += 1
        key = self._build_key(tool_name, args)
        entry = self._cache.get(key)
        if entry is None:
            return None
        if entry.is_expired():
            del self._cache[key]
            logger.debug("Cache expired: %s", tool_name)
            return None
        entry.hit_count += 1
        self._cache_hits += 1
        logger.debug("Cache hit: %s (hits=%d)", tool_name, entry.hit_count)
        return entry.value

    def set(
        self,
        tool_name: str,
        args: Dict[str, Any],
        value: Any,
        ttl: Optional[int] = None,
    ) -> None:
        if len(self._cache) >= self.max_size:
            self._evict_oldest()
        key = self._build_key(tool_name, args)
        self._cache[key] = CacheEntry(
            key=key,
            value=value,
            ttl=ttl if ttl is not None else self.default_ttl,
        )

    def clear(self) -> None:
        self._cache.clear()
        self._total_requests = 0
        self._cache_hits = 0

    def stats(self) -> Dict[str, Any]:
        total = self._total_requests
        hits = self._cache_hits
        return {
            "total_requests": total,
            "cache_hits": hits,
            "cache_misses": total - hits,
            "hit_rate": round(hits / total * 100, 2) if total else 0.0,
            "cache_size": len(self._cache),
            "max_size": self.max_size,
        }
