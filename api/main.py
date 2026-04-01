"""FastAPI 主应用

提供 REST API 接口。
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from config.settings import get_settings
from api.routes import chat, tools, health

# 配置日志
logging.basicConfig(
    level=getattr(logging, get_settings().log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动
    logger.info("Starting Data Analysis Agent API...")
    yield
    # 关闭
    logger.info("Shutting down Data Analysis Agent API...")


# 创建 FastAPI 应用
app = FastAPI(
    title="Data Analysis Agent API",
    description="基于 LangGraph 的智能数据分析 Agent API",
    version="2.0.0",
    lifespan=lifespan
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(tools.router, prefix="/api", tags=["tools"])


@app.get("/")
async def root():
    """根路径"""
    return {
        "name": "Data Analysis Agent API",
        "version": "2.0.0",
        "docs": "/docs"
    }
