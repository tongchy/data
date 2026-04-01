"""Agent 状态定义

定义 LangGraph 使用的状态类型。
"""
from typing import TypedDict, List, Dict, Any, Optional

try:
    from langchain_core.messages import BaseMessage
except Exception:  # pragma: no cover - 在最小环境下兜底
    BaseMessage = Any

import pandas as pd


class AgentState(TypedDict):
    """Agent 状态定义
    
    用于 LangGraph 的状态管理，定义了 Agent 执行过程中的所有状态字段。
    """
    # 消息历史
    messages: List[BaseMessage]
    
    # 数据上下文
    dataframes: Dict[str, pd.DataFrame]  # DataFrame 存储
    query_results: Dict[str, List[Dict]]  # 查询结果
    
    # 执行上下文
    current_step: str  # 当前执行步骤
    errors: List[str]  # 错误列表
    metadata: Dict[str, Any]  # 元数据
    
    # 可视化
    images: Dict[str, str]  # 图片路径映射


class DataAgentState(AgentState):
    """数据分析 Agent 专用状态
    
    继承自基础 AgentState，添加数据分析特有的字段。
    """
    # 扩展特定字段
    analysis_type: Optional[str]  # 分析类型
    target_tables: List[str]  # 目标表列表
    generated_sql: Optional[str]  # 生成的 SQL


class UnifiedRuntimeState(TypedDict):
    """统一运行时状态（Deep Agents 风格）"""

    # 消息与任务
    messages: List[Any]
    current_task: Optional[str]
    task_type: Optional[str]
    todo_list: List[Dict[str, Any]]

    # 动态工具与表语义
    context: Dict[str, Any]
    loaded_tools: List[str]
    loaded_tables: List[str]
    table_semantics: Dict[str, Dict[str, Any]]

    # 工具调用统计
    tool_usage_stats: Dict[str, int]
    tool_failures: Dict[str, int]
    total_tool_calls: int

    # 拦截层状态（权限/缓存）
    tool_cache: Dict[str, str]
    cache_hits: int
    cache_misses: int
    auth_denials: int

    # 路由与跳转策略
    consecutive_failures: int
    jump_strategy: str
    last_jump_decision: Optional[str]

    # 运行时元数据
    runtime_stats: Dict[str, Any]


def create_default_runtime_state() -> UnifiedRuntimeState:
    """创建默认统一运行时状态。"""
    return {
        "messages": [],
        "current_task": None,
        "task_type": None,
        "todo_list": [],
        "context": {},
        "loaded_tools": [],
        "loaded_tables": [],
        "table_semantics": {},
        "tool_usage_stats": {},
        "tool_failures": {},
        "total_tool_calls": 0,
        "tool_cache": {},
        "cache_hits": 0,
        "cache_misses": 0,
        "auth_denials": 0,
        "consecutive_failures": 0,
        "jump_strategy": "normal",
        "last_jump_decision": None,
        "runtime_stats": {},
    }
