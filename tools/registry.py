"""工具注册中心

提供工具的发现、注册和管理功能。
"""
from typing import Any, Dict, List, Type, Optional
from tools.base import BaseCustomTool
import logging

logger = logging.getLogger(__name__)


class ToolRegistry:
    """工具注册中心（单例模式）
    
    管理所有可用工具的注册和检索。
    
    Example:
        >>> registry = ToolRegistry()
        >>> registry.register(MyTool())
        >>> tool = registry.get("my_tool")
    """
    
    _instance: Optional['ToolRegistry'] = None
    _tools: Dict[str, Any] = {}
    
    def __new__(cls) -> 'ToolRegistry':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def register(self, tool: Any) -> None:
        """注册工具
        
        Args:
            tool: 要注册的工具实例
        """
        if tool.name in self._tools:
            logger.warning(f"Tool {tool.name} already registered, overwriting")
        self._tools[tool.name] = tool
        logger.info(f"Tool {tool.name} registered successfully")
    
    def get(self, name: str) -> Optional[Any]:
        """获取工具
        
        Args:
            name: 工具名称
            
        Returns:
            Optional[BaseCustomTool]: 工具实例，如果不存在则返回 None
        """
        return self._tools.get(name)
    
    def get_all(self) -> List[Any]:
        """获取所有工具
        
        Returns:
            List[BaseCustomTool]: 所有已注册的工具列表
        """
        return list(self._tools.values())
    
    def get_by_category(self, category: str) -> List[Any]:
        """按类别获取工具
        
        Args:
            category: 工具类别
            
        Returns:
            List[BaseCustomTool]: 该类别的所有工具
        """
        return [t for t in self._tools.values() if t.category == category]
    
    def unregister(self, name: str) -> bool:
        """注销工具
        
        Args:
            name: 工具名称
            
        Returns:
            bool: 是否成功注销
        """
        if name in self._tools:
            del self._tools[name]
            logger.info(f"Tool {name} unregistered")
            return True
        return False
    
    def clear(self) -> None:
        """清空所有工具"""
        self._tools.clear()
        logger.info("All tools cleared")
    
    def list_tools(self) -> List[Dict]:
        """列出所有工具信息
        
        Returns:
            List[Dict]: 工具信息列表
        """
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "category": tool.category,
                "version": tool.version,
                "execution_count": tool.execution_count
            }
            for tool in self._tools.values()
        ]


# 全局注册中心实例
registry = ToolRegistry()


def register_tool(tool_class: Type[BaseCustomTool]) -> Type[BaseCustomTool]:
    """工具注册装饰器
    
    用于快速注册工具类。
    
    Example:
        >>> @register_tool
        ... class MyTool(BaseCustomTool):
        ...     pass
    """
    tool_instance = tool_class()
    registry.register(tool_instance)
    return tool_class
