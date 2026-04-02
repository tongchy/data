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
from contextlib import asynccontextmanager

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from langgraph.store.memory import InMemoryStore
from langchain_core.runnables import RunnableConfig

# 导入配置
from config.settings import get_settings

# 导入 Supervisor Agent
from agents.supervisor import SupervisorAgent, create_supervisor_agent

# 全局 Agent 实例
_supervisor_agent: Optional[SupervisorAgent] = None
_store: Optional[InMemoryStore] = None


def get_store() -> InMemoryStore:
    """获取或创建 Store 实例"""
    global _store
    if _store is None:
        _store = InMemoryStore()
    return _store


def get_supervisor_agent() -> SupervisorAgent:
    """获取或创建 Supervisor Agent 实例"""
    global _supervisor_agent
    if _supervisor_agent is None:
        settings = get_settings()
        store = get_store()
        _supervisor_agent = create_supervisor_agent(settings, store)
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


# ============================================================================
# 直接执行入口
# ============================================================================

if __name__ == "__main__":
    import asyncio
    
    async def main():
        """测试主函数"""
        print("=" * 60)
        print("Deep Agents 数据分析 Agent")
        print("=" * 60)
        
        # 显示 Agent 状态
        agent = get_supervisor_agent()
        status = agent.get_status()
        
        print("\n📊 Agent 状态:")
        print(f"  - 后端: {list(status['backends']['store_backends'].keys())}")
        print(f"  - 子 Agent: {list(status['subagents'].keys())}")
        print(f"  - 工具数: {sum(len(v) for v in status['tools'].values())}")
        
        print("\n🔧 可用工具:")
        for category, tools in status['tools'].items():
            print(f"  [{category}]")
            for tool in tools:
                print(f"    - {tool}")
        
        # 测试对话
        print("\n" + "=" * 60)
        print("测试对话:")
        print("=" * 60)
        
        test_messages = [
            "你好，请介绍一下你的功能",
            "帮我分析一下设备数据",
        ]
        
        for msg in test_messages:
            print(f"\n👤 用户: {msg}")
            try:
                from langchain_core.messages import HumanMessage
                graph = data_agent(RunnableConfig(configurable={"thread_id": "test"}))
                response = await graph.ainvoke({"messages": [HumanMessage(content=msg)]})
                
                # 提取 AI 回复
                if "messages" in response:
                    ai_messages = [m for m in response["messages"] if hasattr(m, 'type') and m.type == "ai"]
                    if ai_messages:
                        print(f"🤖 Agent: {ai_messages[-1].content[:200]}...")
                    else:
                        print(f"🤖 Agent: {response}")
                else:
                    print(f"🤖 Agent: {response}")
                    
            except Exception as e:
                print(f"❌ 错误: {e}")
        
        print("\n" + "=" * 60)
        print("测试完成")
        print("=" * 60)
    
    # 运行测试
    asyncio.run(main())
