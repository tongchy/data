"""工具模块

提供 Agent 可调用的各种工具，包括 SQL 查询、数据提取、Python 执行和可视化等。
"""
from tools.base import BaseCustomTool, ToolResult
from tools.registry import ToolRegistry, registry, register_tool
from tools.dynamic_registry import DynamicToolRegistry

# 导入所有工具以完成自动注册
from tools.sql.query_tool import SQLQueryTool
from tools.data.extract_tool import DataExtractTool
from tools.code.python_executor import PythonExecutorTool
from tools.visualization.plot_tool import PlotTool
from tools.loader.table_metadata import TableMetadataTool

__all__ = [
    "BaseCustomTool",
    "ToolResult",
    "ToolRegistry",
    "DynamicToolRegistry",
    "registry",
    "register_tool",
    "get_all_tools"
]


def get_all_tools():
    """获取所有已注册的工具
    
    Returns:
        List[BaseTool]: 所有已注册的工具列表
    """
    return registry.get_all()
