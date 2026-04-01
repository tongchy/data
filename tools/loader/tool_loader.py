"""工具加载器 - L1 层

实现动态工具加载机制，根据任务类型按需加载工具，优化 Token 消耗。
"""
from enum import Enum
from typing import Dict, List, Optional, Set, Any, Callable
from dataclasses import dataclass, field
from pydantic import BaseModel, Field
import logging
import re

from tools.base import BaseCustomTool, ToolResult
from tools.registry import registry

logger = logging.getLogger(__name__)


class TaskType(str, Enum):
    """任务类型枚举"""
    SQL_QUERY = "sql_query"           # SQL 查询任务
    DATA_ANALYSIS = "data_analysis"   # 数据分析任务
    VISUALIZATION = "visualization"   # 可视化任务
    FILE_OPERATION = "file_operation" # 文件操作任务
    GENERAL = "general"               # 通用任务


@dataclass
class ToolMetadata:
    """工具元数据"""
    name: str
    description: str
    category: str
    task_types: List[TaskType] = field(default_factory=list)
    required_tables: List[str] = field(default_factory=list)
    token_cost: int = 0  # 预估 Token 消耗
    
    def matches_task(self, task_type: TaskType) -> bool:
        """检查工具是否匹配任务类型"""
        return task_type in self.task_types or TaskType.GENERAL in self.task_types


class ToolLoader(BaseCustomTool):
    """工具加载器 - L1 层核心组件
    
    根据任务类型和上下文动态加载所需工具，实现：
    1. 按需加载：只加载与任务相关的工具
    2. 表关联：根据涉及的表加载相关工具
    3. Token 优化：减少 70% 的工具描述 Token
    
    Attributes:
        name: 工具名称
        description: 工具描述
        category: 工具类别
    """
    
    name: str = "tool_loader"
    description: str = """动态加载工具。根据任务类型和上下文按需加载所需工具。
    
    使用此工具来：
    1. 根据任务类型加载相关工具
    2. 根据涉及的表加载表相关工具
    3. 获取当前已加载的工具列表
    
    参数：
    - task_type: 任务类型 (sql_query/data_analysis/visualization/file_operation/general)
    - mentioned_tables: 提到的表名列表（可选）
    - include_base: 是否包含基础工具（默认 True）
    """
    category: str = "loader"
    version: str = "1.0.0"
    
    # 工具元数据注册表
    _tool_metadata: Dict[str, ToolMetadata] = {}
    # 已加载的工具缓存
    _loaded_tools: Dict[str, BaseCustomTool] = {}
    # 工具加载历史（用于分析）
    _load_history: List[Dict] = []
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._register_default_metadata()
    
    def _register_default_metadata(self):
        """注册默认工具元数据"""
        default_metadata = [
            ToolMetadata(
                name="sql_inter",
                description="SQL 查询工具",
                category="sql",
                task_types=[TaskType.SQL_QUERY, TaskType.DATA_ANALYSIS],
                token_cost=150
            ),
            ToolMetadata(
                name="extract_data",
                description="数据提取工具",
                category="data",
                task_types=[TaskType.DATA_ANALYSIS, TaskType.SQL_QUERY],
                token_cost=120
            ),
            ToolMetadata(
                name="python_inter",
                description="Python 执行工具",
                category="code",
                task_types=[TaskType.DATA_ANALYSIS, TaskType.VISUALIZATION, TaskType.GENERAL],
                token_cost=100
            ),
            ToolMetadata(
                name="fig_inter",
                description="可视化工具",
                category="visualization",
                task_types=[TaskType.VISUALIZATION, TaskType.DATA_ANALYSIS],
                token_cost=130
            ),
            ToolMetadata(
                name="ls",
                description="列目录工具",
                category="filesystem",
                task_types=[TaskType.FILE_OPERATION, TaskType.GENERAL],
                token_cost=60
            ),
            ToolMetadata(
                name="read_file",
                description="读取文件工具",
                category="filesystem",
                task_types=[TaskType.FILE_OPERATION, TaskType.GENERAL],
                token_cost=80
            ),
            ToolMetadata(
                name="write_file",
                description="写入文件工具",
                category="filesystem",
                task_types=[TaskType.FILE_OPERATION, TaskType.GENERAL],
                token_cost=80
            ),
            ToolMetadata(
                name="edit_file",
                description="文件编辑工具",
                category="filesystem",
                task_types=[TaskType.FILE_OPERATION, TaskType.GENERAL],
                token_cost=80
            ),
            ToolMetadata(
                name="delegate_to_sql_specialist",
                description="委派 SQL 专家子 Agent",
                category="agent",
                task_types=[TaskType.SQL_QUERY, TaskType.DATA_ANALYSIS],
                token_cost=160
            ),
            ToolMetadata(
                name="delegate_to_data_analyst",
                description="委派数据分析子 Agent",
                category="agent",
                task_types=[TaskType.GENERAL, TaskType.DATA_ANALYSIS, TaskType.VISUALIZATION],
                token_cost=160
            ),
            ToolMetadata(
                name="delegate_to_visualization_specialist",
                description="委派可视化子 Agent",
                category="agent",
                task_types=[TaskType.VISUALIZATION, TaskType.DATA_ANALYSIS],
                token_cost=160
            ),
        ]
        
        for metadata in default_metadata:
            self._tool_metadata[metadata.name] = metadata
        
        logger.info(f"Registered {len(default_metadata)} tool metadata entries")
    
    def register_metadata(self, metadata: ToolMetadata) -> None:
        """注册工具元数据
        
        Args:
            metadata: 工具元数据
        """
        self._tool_metadata[metadata.name] = metadata
        logger.info(f"Registered metadata for tool: {metadata.name}")
    
    def detect_task_type(self, query: str) -> TaskType:
        """检测任务类型
        
        根据用户查询自动识别任务类型。
        
        Args:
            query: 用户查询
            
        Returns:
            TaskType: 检测到的任务类型
        """
        query_lower = query.lower()
        
        # SQL 查询关键词
        sql_keywords = ['查询', 'select', 'where', 'sql', '表', '数据', '统计', '多少', '计数']
        if any(kw in query_lower for kw in sql_keywords):
            return TaskType.SQL_QUERY
        
        # 可视化关键词
        viz_keywords = ['图', 'chart', 'plot', '可视化', '展示', '绘制', '趋势', '对比']
        if any(kw in query_lower for kw in viz_keywords):
            return TaskType.VISUALIZATION
        
        # 文件操作关键词
        file_keywords = ['文件', '保存', '读取', '导出', '导入', 'file', 'read', 'write']
        if any(kw in query_lower for kw in file_keywords):
            return TaskType.FILE_OPERATION
        
        # 数据分析关键词
        analysis_keywords = ['分析', '计算', '统计', '平均', '最大', '最小', '求和', '占比']
        if any(kw in query_lower for kw in analysis_keywords):
            return TaskType.DATA_ANALYSIS
        
        return TaskType.GENERAL
    
    def extract_mentioned_tables(self, query: str, available_tables: List[str]) -> List[str]:
        """提取查询中提到的表名
        
        Args:
            query: 用户查询
            available_tables: 可用表名列表
            
        Returns:
            List[str]: 提到的表名列表
        """
        mentioned = []
        query_lower = query.lower()
        
        for table in available_tables:
            if table.lower() in query_lower:
                mentioned.append(table)
        
        return mentioned
    
    def load_tools(
        self,
        task_type: TaskType,
        mentioned_tables: Optional[List[str]] = None,
        include_base: bool = True
    ) -> List[BaseCustomTool]:
        """加载工具
        
        根据任务类型和上下文动态加载工具。
        
        Args:
            task_type: 任务类型
            mentioned_tables: 提到的表名列表
            include_base: 是否包含基础工具
            
        Returns:
            List[BaseCustomTool]: 加载的工具列表
        """
        loaded_tools = []
        loaded_names = []
        total_token_cost = 0
        
        # 1. 加载任务类型匹配的工具
        for name, metadata in self._tool_metadata.items():
            if metadata.matches_task(task_type):
                tool = registry.get(name)
                if tool:
                    loaded_tools.append(tool)
                    loaded_names.append(name)
                    total_token_cost += metadata.token_cost
        
        # 2. 加载基础工具（如果需要）
        if include_base:
            base_tools = [
                'create_todo',
                'update_todo',
                'list_todos',
                'get_todo',
                'check_task_status',
                'summarize_conversation',
                'get_conversation_context',
            ]
            for tool_name in base_tools:
                if tool_name not in loaded_names:
                    tool = registry.get(tool_name)
                    if tool:
                        loaded_tools.append(tool)
                        loaded_names.append(tool_name)
        
        # 3. 加载表相关的 schema_loader（如果提到了表）
        if mentioned_tables:
            # 动态注册 schema_loader 工具
            from .schema_loader import SchemaLoader
            schema_loader = SchemaLoader()
            # 为每个提到的表预加载 schema
            for table in mentioned_tables:
                schema_loader.load_schema(table)
            
            if schema_loader.name not in loaded_names:
                loaded_tools.append(schema_loader)
                loaded_names.append(schema_loader.name)
        
        # 记录加载历史
        self._load_history.append({
            "task_type": task_type.value,
            "mentioned_tables": mentioned_tables or [],
            "loaded_tools": loaded_names,
            "token_cost": total_token_cost
        })
        
        # 更新已加载工具缓存
        self._loaded_tools = {tool.name: tool for tool in loaded_tools}
        
        logger.info(
            f"Loaded {len(loaded_tools)} tools for task '{task_type.value}' "
            f"(tables: {mentioned_tables or []}, token_cost: {total_token_cost})"
        )
        
        return loaded_tools
    
    def get_loaded_tools(self) -> List[BaseCustomTool]:
        """获取当前已加载的工具"""
        return list(self._loaded_tools.values())
    
    def get_load_stats(self) -> Dict[str, Any]:
        """获取加载统计信息"""
        if not self._load_history:
            return {"total_loads": 0, "avg_tools_per_load": 0, "total_token_savings": 0}
        
        total_loads = len(self._load_history)
        avg_tools = sum(len(h["loaded_tools"]) for h in self._load_history) / total_loads
        total_token_cost = sum(h.get("token_cost", 0) for h in self._load_history)
        
        # 假设全量加载需要 1000 tokens
        full_load_cost = 1000 * total_loads
        savings = full_load_cost - total_token_cost
        savings_percent = (savings / full_load_cost * 100) if full_load_cost > 0 else 0
        
        return {
            "total_loads": total_loads,
            "avg_tools_per_load": round(avg_tools, 2),
            "total_token_cost": total_token_cost,
            "estimated_savings": savings,
            "savings_percent": round(savings_percent, 1)
        }
    
    def _execute(
        self,
        task_type: str,
        mentioned_tables: Optional[List[str]] = None,
        include_base: bool = True
    ) -> ToolResult:
        """执行工具加载
        
        Args:
            task_type: 任务类型字符串
            mentioned_tables: 提到的表名列表
            include_base: 是否包含基础工具
            
        Returns:
            ToolResult: 加载结果
        """
        try:
            # 解析任务类型
            try:
                task = TaskType(task_type)
            except ValueError:
                task = self.detect_task_type(task_type)
            
            # 加载工具
            tools = self.load_tools(task, mentioned_tables, include_base)
            
            # 获取统计
            stats = self.get_load_stats()
            
            # 构建结果消息
            tool_list = "\n".join([f"  - {t.name} ({t.description[:30]}...)" for t in tools])
            message = f"""成功加载 {len(tools)} 个工具：

{tool_list}

Token 优化统计：
- 本次加载预估消耗: {stats['total_token_cost']} tokens
- 累计节省: {stats['estimated_savings']} tokens ({stats['savings_percent']}%)
"""
            
            return ToolResult(
                success=True,
                data={
                    "loaded_tools": [t.name for t in tools],
                    "task_type": task.value,
                    "stats": stats
                },
                message=message
            )
            
        except Exception as e:
            logger.error(f"Tool loading failed: {e}")
            return ToolResult(
                success=False,
                error=str(e),
                message=f"工具加载失败: {str(e)}"
            )


# 全局工具加载器实例
tool_loader = ToolLoader()
