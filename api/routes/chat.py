"""聊天路由"""
from fastapi import APIRouter, HTTPException
from typing import Dict
import logging

from agents.supervisor import SupervisorAgent, create_supervisor_agent
from api.schemas.request import ChatRequest
from api.schemas.response import ChatResponse, ChatStreamResponse

router = APIRouter()
logger = logging.getLogger(__name__)

# 存储 Agent 实例
_agent_instances: Dict[str, SupervisorAgent] = {}


def get_agent(thread_id: str) -> SupervisorAgent:
    """获取或创建 Agent 实例"""
    if thread_id not in _agent_instances:
        _agent_instances[thread_id] = create_supervisor_agent()
    return _agent_instances[thread_id]


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """发送消息并获取回复
    
    Args:
        request: 聊天请求
        
    Returns:
        ChatResponse: 聊天响应
    """
    try:
        agent = get_agent(request.thread_id)
        
        if request.stream:
            raise HTTPException(status_code=400, detail="Use /chat/stream for streaming")
        
        invoke_kwargs = {}
        if request.role:
            invoke_kwargs["role"] = request.role
        if request.permissions is not None:
            invoke_kwargs["permissions"] = request.permissions
        if request.user_id:
            invoke_kwargs["user_id"] = request.user_id

        result = await agent.invoke(request.message, request.thread_id, **invoke_kwargs)
        
        return ChatResponse(
            content=result.get("content", ""),
            thread_id=request.thread_id,
            message_type="assistant"
        )
        
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """流式聊天
    
    使用 SSE (Server-Sent Events) 返回流式响应。
    """
    from fastapi.responses import StreamingResponse
    import json
    
    async def event_generator():
        try:
            agent = get_agent(request.thread_id)

            invoke_kwargs = {}
            if request.role:
                invoke_kwargs["role"] = request.role
            if request.permissions is not None:
                invoke_kwargs["permissions"] = request.permissions
            if request.user_id:
                invoke_kwargs["user_id"] = request.user_id

            result = await agent.invoke(request.message, request.thread_id, **invoke_kwargs)
            payload = ChatStreamResponse(
                type="assistant",
                content=result.get("content", ""),
                done=False,
            )
            yield f"data: {json.dumps(payload.model_dump(), default=str)}\n\n"
            
            # 发送结束标记
            done_payload = ChatStreamResponse(type="done", content="", done=True)
            yield f"data: {json.dumps(done_payload.model_dump(), default=str)}\n\n"
            
        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'content': str(e), 'done': True})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )


@router.delete("/chat/{thread_id}")
async def clear_chat(thread_id: str):
    """清除会话历史"""
    if thread_id in _agent_instances:
        del _agent_instances[thread_id]
    
    return {"message": f"Session {thread_id} cleared"}
