"""HITL resume 路由。"""

from typing import Optional, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.routes.chat import get_agent

router = APIRouter()


class ResumeRequest(BaseModel):
    """恢复中断会话请求。"""

    thread_id: str = Field(..., description="会话 ID")
    decision: Literal["approve", "edit", "reject"] = Field(..., description="人工决策")
    edited_sql: Optional[str] = Field(default=None, description="编辑后的 SQL（decision=edit 时必填）")
    reason: Optional[str] = Field(default=None, description="拒绝原因（decision=reject 时可选）")


@router.post("/resume")
async def resume_chat(request: ResumeRequest):
    """恢复被 HITL 中断的会话。"""
    if request.decision == "edit" and not (request.edited_sql or "").strip():
        raise HTTPException(status_code=400, detail="decision=edit 时 edited_sql 不能为空")

    agent = get_agent(request.thread_id)

    payload = {
        "decision": request.decision,
        "edited_sql": request.edited_sql,
        "reason": request.reason,
    }

    try:
        result = await agent.resume(request.thread_id, payload)
        messages = result.get("messages") if isinstance(result, dict) else None
        content = ""
        if messages:
            last = messages[-1]
            content = getattr(last, "content", "") or str(last)
        return {
            "thread_id": request.thread_id,
            "decision": request.decision,
            "content": content,
            "raw": result,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"resume failed: {exc}") from exc
