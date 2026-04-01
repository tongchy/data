"""API response schemas."""

from pydantic import BaseModel


class ChatResponse(BaseModel):
    """聊天响应"""

    content: str
    thread_id: str
    message_type: str = "assistant"


class ChatStreamResponse(BaseModel):
    """流式聊天响应"""

    type: str
    content: str
    done: bool = False
