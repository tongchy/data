"""健康检查路由"""
from fastapi import APIRouter, status
from pydantic import BaseModel
from typing import Dict
import datetime

from config.settings import get_settings
from tools.registry import registry

router = APIRouter()


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    version: str
    timestamp: str
    tools_count: int


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """健康检查端点
    
    返回服务状态信息。
    """
    settings = get_settings()
    
    return HealthResponse(
        status="healthy",
        version=settings.version,
        timestamp=datetime.datetime.now().isoformat(),
        tools_count=len(registry.get_all())
    )


@router.get("/ready")
async def readiness_check():
    """就绪检查"""
    return {"ready": True}


@router.get("/live")
async def liveness_check():
    """存活检查"""
    return {"alive": True}
