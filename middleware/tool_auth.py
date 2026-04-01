"""RBAC 工具权限中间件

在 wrap_tool_call 钩子中拦截每次工具调用，根据 PermissionManager
检查当前角色是否有权使用该工具。若无权限，直接返回 ToolMessage
错误响应，并递增 state["auth_denials"] 计数器。
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional

from langchain_core.messages import ToolMessage

from middleware.base import BaseMiddleware
from middleware.permissions import PermissionManager, Role
from middleware.types import MiddlewareCommand

logger = logging.getLogger(__name__)


class ToolAuthMiddleware(BaseMiddleware):
    """基于 RBAC 的工具调用权限中间件

    优先级 80（高于缓存中间件 50），确保权限检查在缓存查找之前执行。

    用法：
        manager = MiddlewareManager()
        manager.add(ToolAuthMiddleware())
        # 或注入自定义 PermissionManager
        manager.add(ToolAuthMiddleware(permission_manager=custom_pm))

    state 约定：
        state["context"]["role"] → 当前用户角色字符串（默认 "guest"）
        state["auth_denials"]   → 被拒绝的调用次数（自动累加）
    """

    name: str = "ToolAuthMiddleware"
    priority: int = 80

    def __init__(
        self,
        permission_manager: Optional[PermissionManager] = None,
    ) -> None:
        self._pm = permission_manager or PermissionManager()
        # 会话内角色 → 工具名 的权限缓存，after_agent 时清除
        self._cache: Dict[str, bool] = {}

    # ------------------------------------------------------------------ hooks

    async def wrap_tool_call(
        self,
        state: Dict[str, Any],
        tool_call: Any,
        handler: Callable,
    ) -> Any:
        tool_name: str = getattr(tool_call, "name", str(tool_call))
        tool_call_id: str = getattr(tool_call, "id", "unknown")

        ctx = state.get("context") or {}
        role_str: str = ctx.get("role", "guest") if isinstance(ctx, dict) else "guest"

        try:
            role = Role(role_str)
        except ValueError:
            role = Role.GUEST

        cache_key = f"{role_str}:{tool_name}"
        if cache_key not in self._cache:
            self._cache[cache_key] = self._pm.check(role, tool_name)

        if not self._cache[cache_key]:
            state["auth_denials"] = state.get("auth_denials", 0) + 1
            logger.warning(
                "Permission denied: role=%s tool=%s (auth_denials=%d)",
                role_str,
                tool_name,
                state["auth_denials"],
            )
            return ToolMessage(
                content=f"❌ 权限拒绝：角色 `{role_str}` 无权使用工具 `{tool_name}`",
                tool_call_id=tool_call_id,
            )

        return await handler(tool_call)

    async def after_agent(
        self,
        state: Dict[str, Any],
        final_result: Any,
    ) -> Optional[MiddlewareCommand]:
        """会话结束后清除权限缓存，避免角色变更时误命中"""
        self._cache.clear()
        return None
