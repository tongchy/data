"""工具调用缓存中间件（带 TTL，跳过写操作工具）

在 wrap_tool_call 钩子中：
  1. 若工具属于 skip_tools（写操作），直接放行
  2. 检查缓存 - 命中则返回缓存内容（附 [缓存] 标记）
  3. 未命中则调用真实 handler，并将结果写入缓存
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional, Set

from langchain_core.messages import ToolMessage

from middleware.base import BaseMiddleware
from middleware.cache_backend import CacheBackend, InMemoryCacheBackend

logger = logging.getLogger(__name__)

# 默认不缓存的写操作工具
_DEFAULT_SKIP_TOOLS: Set[str] = {"write_file", "edit_file", "delete_file"}


class ToolCacheMiddleware(BaseMiddleware):
    """工具调用结果缓存中间件

    优先级 50，在权限中间件（80）之后执行，只对已通过权限检查的调用缓存。

    Args:
        backend:    缓存后端实例，默认使用 InMemoryCacheBackend
        ttl:        默认缓存存活时间（秒），默认 3600
        skip_tools: 不参与缓存的工具名集合（写操作），默认见 _DEFAULT_SKIP_TOOLS

    state 约定：
        state["cache_hits"]   → 缓存命中次数（自动累加）
        state["cache_misses"] → 缓存未命中次数（自动累加）
    """

    name: str = "ToolCacheMiddleware"
    priority: int = 50

    def __init__(
        self,
        backend: Optional[CacheBackend] = None,
        ttl: int = 3600,
        skip_tools: Optional[Set[str]] = None,
    ) -> None:
        self._backend = backend or InMemoryCacheBackend(default_ttl=ttl)
        self._skip_tools = skip_tools if skip_tools is not None else set(_DEFAULT_SKIP_TOOLS)

    # ------------------------------------------------------------------ hooks

    async def wrap_tool_call(
        self,
        state: Dict[str, Any],
        tool_call: Any,
        handler: Callable,
    ) -> Any:
        tool_name: str = getattr(tool_call, "name", str(tool_call))
        tool_call_id: str = getattr(tool_call, "id", "unknown")
        args: Dict[str, Any] = getattr(tool_call, "args", {}) or {}

        # 写操作工具直接放行，不进行缓存
        if tool_name in self._skip_tools:
            return await handler(tool_call)

        cached = self._backend.get(tool_name, args)
        if cached is not None:
            state["cache_hits"] = state.get("cache_hits", 0) + 1
            logger.debug("Cache HIT for tool=%s", tool_name)
            return ToolMessage(
                content=f"{cached} [缓存]",
                tool_call_id=tool_call_id,
            )

        state["cache_misses"] = state.get("cache_misses", 0) + 1
        result = await handler(tool_call)

        # 提取文本内容写缓存（None 或空串不缓存）
        content: Optional[str] = None
        if isinstance(result, str):
            content = result
        else:
            maybe_content = getattr(result, "content", None)
            if isinstance(maybe_content, str):
                content = maybe_content

        if isinstance(content, str) and content:
            self._backend.set(tool_name, args, content)

        return result

    # ------------------------------------------------------------------ utils

    def get_stats(self) -> Dict[str, Any]:
        return self._backend.stats()
