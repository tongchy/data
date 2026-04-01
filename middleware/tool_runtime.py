"""工具调用运行时包装器（仅作为同步 fallback 使用）

性能说明：
- 权限拦截：已由 ToolAuthMiddleware 处理，此处已移除
- 结果缓存：已由 ToolCacheMiddleware 处理，此处已移除
- 仅保留基本工具包装和失败统计

此模块已被新的中间件系统（middleware/base.py + *.py）部分替代。
仅当在同步上下文中直接调用工具时使用。对于异步调用（推荐），
请使用多层中间件链（ToolAuthMiddleware -> ToolCacheMiddleware -> ContextEditingMiddleware）。
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional
import json
import logging

from langchain_core.tools import StructuredTool

logger = logging.getLogger(__name__)


class ToolRuntimeMiddleware:
    """工具运行时中间件 - 已简化版本（仅支持 fallback 同步调用）。"""

    def __init__(self, max_cache_entries: int = 256):
        """初始化。注：max_cache_entries 保留以支持向后兼容，但缓存已由 ToolCacheMiddleware 处理。"""
        self.max_cache_entries = max_cache_entries

    def _call_original(self, original_tool: Any, kwargs: Dict[str, Any]) -> Any:
        if hasattr(original_tool, "invoke"):
            return original_tool.invoke(kwargs)
        if callable(original_tool):
            return original_tool(**kwargs)
        raise TypeError(f"Unsupported tool type: {type(original_tool)}")

    def _to_text(self, result: Any) -> str:
        if isinstance(result, str):
            return result
        if isinstance(result, (dict, list, tuple)):
            return json.dumps(result, ensure_ascii=False, default=str)
        return str(result)

    def wrap_tool(self, tool_obj: Any, state: Dict[str, Any], permissions: Optional[List[str]] = None) -> Any:
        """包装单个工具（简化版，仅基本的工具调用和失败统计）。
        
        权限检查和缓存由新的中间件系统处理。此方法只做：
        - 基本的工具调用和结果格式化
        - 失败计数（用于决策中止条件）
        
        Args:
            tool_obj: 原始工具对象
            state: 线程状态字典
            permissions: 已弃用（由 ToolAuthMiddleware 处理）
            
        Returns:
            包装后的 StructuredTool
        """
        tool_name = getattr(tool_obj, "name", getattr(tool_obj, "__name__", "unknown_tool"))
        description = getattr(tool_obj, "description", f"Wrapped tool: {tool_name}")
        args_schema = getattr(tool_obj, "args_schema", None)

        def wrapped_tool(**kwargs: Any) -> str:
            # 仅执行工具调用和失败统计
            state["total_tool_calls"] = state.get("total_tool_calls", 0) + 1
            usage = state.setdefault("tool_usage_stats", {})
            usage[tool_name] = usage.get(tool_name, 0) + 1

            try:
                result = self._call_original(tool_obj, kwargs)
                text_result = self._to_text(result)
                state["consecutive_failures"] = 0
                return text_result
            except Exception as exc:  # pragma: no cover
                failures = state.setdefault("tool_failures", {})
                failures[tool_name] = failures.get(tool_name, 0) + 1
                state["consecutive_failures"] = state.get("consecutive_failures", 0) + 1
                msg = f"工具调用失败 [{tool_name}]：{exc}"
                logger.exception(msg)
                return msg

        if args_schema is not None:
            return StructuredTool.from_function(
                func=wrapped_tool,
                name=tool_name,
                description=description,
                args_schema=args_schema,
            )

        return StructuredTool.from_function(
            func=wrapped_tool,
            name=tool_name,
            description=description,
        )

    def wrap_tools(self, tools: List[Any], state: Dict[str, Any], permissions: Optional[List[str]] = None) -> List[Any]:
        """批量包装工具（fallback 同步执行路径）。
        
        此方法仅用于 supervisor._wrap_tools_with_manager 中的同步 fallback。
        异步执行路径使用 MiddlewareManager（推荐）。
        权限检查应通过 ToolAuthMiddleware 处理，不再在此处进行。
        """
        wrapped = []
        for tool_obj in tools:
            wrapped.append(self.wrap_tool(tool_obj, state=state, permissions=permissions))
        return wrapped
