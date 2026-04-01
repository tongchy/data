"""类型定义模块"""
from typing import TypedDict, List, Dict, Any, Optional
from langchain_core.messages import BaseMessage
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
