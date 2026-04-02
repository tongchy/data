"""
Deep Agents 数据分析 Agent - 主入口

基于 LangChain Deep Agents 架构的重构版本
提供任务规划、子 Agent 派发、记忆管理等高级功能

使用方法:
    # LangGraph CLI 部署
    langgraph dev
    
    # 或直接导入使用
    from graph import supervisor_agent
    response = await supervisor_agent.invoke("分析设备数据")
"""

import os
import sys
from typing import Any, Dict, List, Optional, Callable

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from langgraph.store.memory import InMemoryStore
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.runnables import RunnableConfig

# 导入配置
from config.settings import get_settings

# 导入 Supervisor Agent
from agents.supervisor import SupervisorAgent, create_supervisor_agent

# 全局 Agent 实例
_supervisor_agent: Optional[SupervisorAgent] = None
_store: Optional[InMemoryStore] = None
_checkpointer: Optional[Any] = None
_checkpointer_cm: Optional[Any] = None


def get_store() -> InMemoryStore:
    """获取或创建 Store 实例"""
    global _store
    if _store is None:
        _store = InMemoryStore()
    return _store


def get_checkpointer() -> Any:
    """获取 checkpointer。

    当前环境默认使用 MemorySaver。
    若配置为 sqlite 但未安装对应依赖，则自动回退到 MemorySaver。
    """
    global _checkpointer, _checkpointer_cm
    if _checkpointer is not None:
        return _checkpointer

    settings = get_settings()
    backend = (settings.checkpointer_backend or "memory").lower()

    if backend == "sqlite":
        try:
            from langgraph.checkpoint.sqlite import SqliteSaver  # type: ignore

            path = settings.checkpointer_path or "./.langgraph_checkpoints.sqlite"
            _checkpointer_cm = SqliteSaver.from_conn_string(path)
            _checkpointer = _checkpointer_cm.__enter__()
            return _checkpointer
        except Exception:
            # 当前环境未安装 sqlite checkpointer 依赖，回退到内存实现
            _checkpointer = MemorySaver()
            return _checkpointer

    _checkpointer = MemorySaver()
    return _checkpointer


def get_supervisor_agent() -> SupervisorAgent:
    """获取或创建 Supervisor Agent 实例"""
    global _supervisor_agent
    if _supervisor_agent is None:
        settings = get_settings()
        store = get_store()
        checkpointer = get_checkpointer()
        _supervisor_agent = create_supervisor_agent(settings, store, checkpointer)
    return _supervisor_agent


# ============================================================================
# LangGraph 兼容接口 - 必须返回 StateGraph 或 CompiledGraph
# ============================================================================

def data_agent(config: RunnableConfig) -> Any:
    """
    数据分析 Agent 入口函数
    
    LangGraph 工厂函数，返回编译后的图
    
    Args:
        config: RunnableConfig 配置
        
    Returns:
        编译后的 Agent 图
    """
    # 直接复用 SupervisorAgent 中已创建的 agent，避免重复初始化
    agent = get_supervisor_agent()
    return agent.agent


# ============================================================================
# 工具导出（兼容旧版接口）
# ============================================================================

def get_tools() -> List[Callable]:
    """
    获取所有可用工具
    
    Returns:
        工具函数列表
    """
    agent = get_supervisor_agent()
    return agent.tools


def get_agent_status() -> Dict[str, Any]:
    """
    获取 Agent 状态信息
    
    Returns:
        状态字典
    """
    agent = get_supervisor_agent()
    return agent.get_status()
