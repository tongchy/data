"""API request schemas."""

from pydantic import BaseModel, Field
from typing import Optional


class ChatRequest(BaseModel):
    """聊天请求"""

    message: str = Field(..., description="用户消息")
    thread_id: Optional[str] = Field(default="default", description="会话 ID")
    stream: bool = Field(default=False, description="是否流式返回")
