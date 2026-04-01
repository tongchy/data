"""
中间件层

提供 Deep Agents 所需的各种中间件：
"""

from .filesystem import FilesystemMiddleware, create_filesystem_tools
from .subagent import SubAgentMiddleware, SubAgent
from .state_driven import StateDrivenRuntime
from .tool_runtime import ToolRuntimeMiddleware

__all__ = [
    "FilesystemMiddleware",
    "create_filesystem_tools",
    "SubAgentMiddleware",
    "SubAgent",
    "StateDrivenRuntime",
    "ToolRuntimeMiddleware",
]
# ── 基础类型与钩子体系 ──────────────────────────────────────────────────────────
from .types import MiddlewareHookType, MiddlewareCommand
from .base import BaseMiddleware, MiddlewareManager

# ── RBAC 权限 ────────────────────────────────────────────────────────────────────
from .permissions import PermissionLevel, Role, ToolPermission, PermissionManager
from .tool_auth import ToolAuthMiddleware

# ── 工具缓存 ─────────────────────────────────────────────────────────────────────
from .cache_backend import CacheEntry, CacheBackend, InMemoryCacheBackend
from .tool_cache import ToolCacheMiddleware

# ── 上下文编辑 ───────────────────────────────────────────────────────────────────
from .context_editor import ContextEdit, ContextEditor
from .context_edit import ContextEditingMiddleware

__all__ += [
    # 基础类型
    "MiddlewareHookType",
    "MiddlewareCommand",
    "BaseMiddleware",
    "MiddlewareManager",
    # RBAC
    "PermissionLevel",
    "Role",
    "ToolPermission",
    "PermissionManager",
    "ToolAuthMiddleware",
    # 缓存
    "CacheEntry",
    "CacheBackend",
    "InMemoryCacheBackend",
    "ToolCacheMiddleware",
    # 上下文编辑
    "ContextEdit",
    "ContextEditor",
    "ContextEditingMiddleware",
]
