"""RBAC 权限模型与管理器

定义角色（Role）、权限级别（PermissionLevel）、工具权限（ToolPermission），
以及检查和查询接口（PermissionManager）。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Set

logger = logging.getLogger(__name__)


class PermissionLevel(str, Enum):
    """权限级别（由低到高）"""

    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    ADMIN = "admin"


class Role(str, Enum):
    """用户角色"""

    GUEST = "guest"       # 访客：只读
    USER = "user"         # 普通用户：读写
    ANALYST = "analyst"   # 分析师：读写执行
    ADMIN = "admin"       # 管理员：全部权限


@dataclass
class ToolPermission:
    """单个工具的访问控制规则"""

    tool_name: str
    required_level: PermissionLevel
    allowed_roles: Set[Role]
    description: str = ""


class PermissionManager:
    """基于角色的工具访问控制管理器（RBAC）

    职责：
    - 维护工具 → 允许角色 的映射表
    - 提供 check(role, tool_name) -> bool 接口
    - 预置合理的默认规则，支持运行时 register() 扩展
    """

    #: 每个角色拥有的权限级别集合
    _ROLE_LEVELS: Dict[Role, Set[PermissionLevel]] = {
        Role.GUEST:   {PermissionLevel.READ},
        Role.USER:    {PermissionLevel.READ, PermissionLevel.WRITE},
        Role.ANALYST: {PermissionLevel.READ, PermissionLevel.WRITE, PermissionLevel.EXECUTE},
        Role.ADMIN:   {
            PermissionLevel.READ,
            PermissionLevel.WRITE,
            PermissionLevel.EXECUTE,
            PermissionLevel.ADMIN,
        },
    }

    def __init__(self) -> None:
        self._tool_permissions: Dict[str, ToolPermission] = {}
        self._init_defaults()

    # ------------------------------------------------------------------ setup

    def _init_defaults(self) -> None:
        _all  = {Role.GUEST, Role.USER, Role.ANALYST, Role.ADMIN}
        _write = {Role.USER, Role.ANALYST, Role.ADMIN}
        _exec  = {Role.ANALYST, Role.ADMIN}

        # 只读工具（所有角色可用）
        for tool in (
            "ls", "read_file", "schema_loader", "table_metadata",
            "sql_inter", "extract_data",
            "list_todos", "get_todo", "get_conversation_context",
        ):
            self.register(ToolPermission(tool, PermissionLevel.READ, _all))

        # 写入工具
        for tool in ("write_file", "edit_file", "delete_file", "create_todo", "update_todo"):
            self.register(ToolPermission(tool, PermissionLevel.WRITE, _write))

        # 执行工具
        for tool in (
            "python_inter", "fig_inter", "summarize_conversation",
            "delegate_to_sql_specialist",
            "delegate_to_data_analyst",
            "delegate_to_visualization_specialist",
        ):
            self.register(ToolPermission(tool, PermissionLevel.EXECUTE, _exec))

    def register(self, permission: ToolPermission) -> None:
        """注册或覆盖一条工具权限规则"""
        self._tool_permissions[permission.tool_name] = permission

    # ------------------------------------------------------------------ queries

    def check(self, role: Role, tool_name: str) -> bool:
        """检查指定角色是否有权使用工具

        - ADMIN 始终通过
        - 未注册工具默认拒绝（fail-closed）
        """
        if role == Role.ADMIN:
            return True
        perm = self._tool_permissions.get(tool_name)
        if perm is None:
            logger.debug("Tool %s not registered in PermissionManager → denied", tool_name)
            return False
        return role in perm.allowed_roles

    def allowed_tools(self, role: Role) -> Set[str]:
        """返回角色可使用的所有工具名集合"""
        return {
            name
            for name, p in self._tool_permissions.items()
            if role in p.allowed_roles
        }

    def get_permission(self, tool_name: str) -> ToolPermission | None:
        return self._tool_permissions.get(tool_name)
