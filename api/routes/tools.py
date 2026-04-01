"""工具路由"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Dict, Any

from tools.registry import registry

router = APIRouter()


class ToolInfo(BaseModel):
    """工具信息"""
    name: str
    description: str
    category: str
    version: str


@router.get("/tools", response_model=List[ToolInfo])
async def list_tools():
    """列出所有可用工具
    
    Returns:
        List[ToolInfo]: 工具列表
    """
    tools = registry.list_tools()
    return [
        ToolInfo(
            name=t["name"],
            description=t["description"],
            category=t["category"],
            version=t["version"]
        )
        for t in tools
    ]


@router.get("/tools/{category}")
async def list_tools_by_category(category: str):
    """按类别列出工具
    
    Args:
        category: 工具类别
        
    Returns:
        List[Dict]: 工具列表
    """
    tools = registry.get_by_category(category)
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "version": tool.version
        }
        for tool in tools
    ]
