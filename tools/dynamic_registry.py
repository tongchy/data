"""动态工具注册器（运行时发现）

与 tools/registry.py（全局静态单例）互补：
  - ToolRegistry:        启动时注册已知工具，全局单例
  - DynamicToolRegistry: 运行时动态注册/注销（MCP 服务、插件、远程工具等）

每个实例独立维护自己的工具表，支持元数据存储。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DynamicToolRegistry:
    """运行时动态工具注册器

    特性：
    - 重复注册同名工具时静默跳过（返回 False），保证幂等
    - 支持为每个工具附带任意 metadata 字典（版本、来源、描述等）
    - __contains__ / __len__ 支持方便的成员检查

    示例::

        registry = DynamicToolRegistry()
        registry.register(my_tool, metadata={"source": "mcp", "version": "1.0"})
        if "my_tool" in registry:
            tool = registry.get("my_tool")
    """

    def __init__(self) -> None:
        self._registry: Dict[str, Any] = {}
        self._metadata: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------ CRUD

    def register(self, tool: Any, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """注册工具

        Args:
            tool:     工具对象，必须有 .name 属性（或 .__name__）
            metadata: 任意附加元数据字典

        Returns:
            True  → 注册成功
            False → 工具名已存在，跳过
        """
        name: str = (
            getattr(tool, "name", None)
            or getattr(tool, "__name__", None)
            or str(tool)
        )
        if name in self._registry:
            logger.debug("Tool %s already registered, skipping", name)
            return False
        self._registry[name] = tool
        self._metadata[name] = metadata or {}
        logger.info("Dynamically registered tool: %s", name)
        return True

    def unregister(self, tool_name: str) -> bool:
        """注销工具

        Returns:
            True  → 注销成功
            False → 工具名不存在
        """
        if tool_name not in self._registry:
            return False
        del self._registry[tool_name]
        del self._metadata[tool_name]
        logger.info("Unregistered tool: %s", tool_name)
        return True

    def get(self, tool_name: str) -> Optional[Any]:
        """按名称获取工具对象"""
        return self._registry.get(tool_name)

    def get_metadata(self, tool_name: str) -> Dict[str, Any]:
        """获取工具的元数据字典（不存在则返回空字典）"""
        return dict(self._metadata.get(tool_name, {}))

    def list_tools(self) -> List[str]:
        """返回已注册的工具名列表"""
        return list(self._registry.keys())

    def get_all(self) -> List[Any]:
        """返回所有工具对象列表"""
        return list(self._registry.values())

    # ------------------------------------------------------------------ dunder

    def __contains__(self, tool_name: str) -> bool:
        return tool_name in self._registry

    def __len__(self) -> int:
        return len(self._registry)

    def __repr__(self) -> str:
        return f"DynamicToolRegistry(tools={self.list_tools()})"
