"""数据分析 Agent

封装数据分析 Agent 的高级接口。
"""
from typing import AsyncIterator, Dict, Any, Optional
from langchain_core.messages import HumanMessage, AIMessage
import logging

from agents.graphs.react_graph import create_data_agent_graph, SYSTEM_PROMPT
from config.settings import get_settings

logger = logging.getLogger(__name__)


class DataAnalysisAgent:
    """数据分析 Agent
    
    提供高级接口用于与数据分析 Agent 交互。
    
    Example:
        >>> agent = DataAnalysisAgent()
        >>> async for message in agent.chat("查询所有用户"):
        ...     print(message)
    """
    
    def __init__(self, system_prompt: str = None, model=None):
        """初始化 Agent
        
        Args:
            system_prompt: 自定义系统提示词
            model: 自定义语言模型
        """
        self.settings = get_settings()
        self.system_prompt = system_prompt or SYSTEM_PROMPT
        self.graph = create_data_agent_graph(
            prompt=self.system_prompt,
            model=model
        )
        self.message_history = []
        
        logger.info("DataAnalysisAgent initialized")
    
    async def chat(self, message: str, thread_id: str = None) -> AsyncIterator[Dict[str, Any]]:
        """发送消息并获取回复
        
        Args:
            message: 用户消息
            thread_id: 会话 ID
            
        Yields:
            Dict: 消息事件
        """
        config = {"configurable": {"thread_id": thread_id or "default"}}
        
        # 添加用户消息到历史
        self.message_history.append(HumanMessage(content=message))
        
        # 调用 graph
        inputs = {"messages": self.message_history}
        
        async for event in self.graph.astream(inputs, config, stream_mode="values"):
            messages = event.get("messages", [])
            if messages:
                last_message = messages[-1]
                
                # 更新历史
                if last_message not in self.message_history:
                    self.message_history.append(last_message)
                
                # yield 消息
                yield {
                    "type": last_message.type if hasattr(last_message, 'type') else 'unknown',
                    "content": last_message.content if hasattr(last_message, 'content') else str(last_message),
                    "message": last_message
                }
    
    async def invoke(self, message: str, thread_id: str = None) -> Dict[str, Any]:
        """同步调用获取完整回复
        
        Args:
            message: 用户消息
            thread_id: 会话 ID
            
        Returns:
            Dict: 包含完整回复的结果
        """
        config = {"configurable": {"thread_id": thread_id or "default"}}
        
        inputs = {"messages": [HumanMessage(content=message)]}
        
        result = await self.graph.ainvoke(inputs, config)
        
        messages = result.get("messages", [])
        if messages:
            last_message = messages[-1]
            return {
                "content": last_message.content if hasattr(last_message, 'content') else str(last_message),
                "messages": messages
            }
        
        return {"content": "", "messages": []}
    
    def clear_history(self):
        """清除消息历史"""
        self.message_history = []
        logger.info("Message history cleared")
