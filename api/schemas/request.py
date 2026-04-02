"""API request schemas."""

from pydantic import BaseModel, Field
from typing import Optional, List


class ChatRequest(BaseModel):
    """聊天请求"""

    message: str = Field(..., description="用户消息")
    thread_id: Optional[str] = Field(default="default", description="会话 ID")
    stream: bool = Field(default=False, description="是否流式返回")
    role: Optional[str] = Field(default=None, description="用户角色（guest/user/analyst/admin）")
    permissions: Optional[List[str]] = Field(default=None, description="可调用工具白名单，使用 [\"*\"] 表示全部")
    user_id: Optional[str] = Field(default=None, description="用户标识（可选）")
