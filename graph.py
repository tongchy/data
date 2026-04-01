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
from config.settings import Settings

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
        settings = Settings()
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
    from langgraph.graph import StateGraph, MessagesState
    from langgraph.prebuilt import ToolNode
    from langchain_core.messages import SystemMessage
    
    # 获取 Supervisor Agent
    agent = get_supervisor_agent()
    
    # 创建 StateGraph
    workflow = StateGraph(MessagesState)
    
    # 定义系统提示
    system_prompt = """你是一个智能数据分析助手，可以帮助用户：
1. 查询数据库获取数据
2. 分析数据并生成报告
3. 创建可视化图表

请根据用户需求，使用适当的工具完成任务。"""
    
    # 定义 Agent 节点
    def agent_node(state: MessagesState):
        messages = state["messages"]
        # 添加系统消息
        if not any(isinstance(m, SystemMessage) for m in messages):
            messages = [SystemMessage(content=system_prompt)] + messages
        
        # 调用 LLM
        response = agent.llm.invoke(messages)
        return {"messages": [response]}
    
    # 定义工具节点
    tool_node = ToolNode(agent.tools)
    
    # 添加节点
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node)
    
    # 添加边
    workflow.set_entry_point("agent")
    workflow.add_conditional_edges(
        "agent",
        lambda state: "tools" if state["messages"][-1].tool_calls else "end"
    )
    workflow.add_edge("tools", "agent")
    
    # 编译图
    return workflow.compile()


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
