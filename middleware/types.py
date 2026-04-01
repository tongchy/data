"""中间件类型定义

定义中间件系统使用的枚举、数据类和 Pydantic 模型。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class MiddlewareHookType(str, Enum):
    """中间件钩子类型"""

    BEFORE_AGENT = "before_agent"
    BEFORE_MODEL = "before_model"
    WRAP_MODEL_CALL = "wrap_model_call"
    AFTER_MODEL = "after_model"
    WRAP_TOOL_CALL = "wrap_tool_call"
    AFTER_TOOL_CALL = "after_tool_call"
    AFTER_AGENT = "after_agent"


@dataclass
class MiddlewareCommand:
    """中间件返回命令

    Attributes:
        update:   需要合并到 state 的键值对
        messages: 替换当前消息列表（用于 before_model / wrap_model_call）
        jump_to:  跳转目标节点名称
        stop:     是否中止后续中间件的执行
        data:     包装钩子（wrap_*）返回给调用方的附加数据
    """

    update: Optional[Dict[str, Any]] = None
    messages: Optional[List[Any]] = None
    jump_to: Optional[str] = None
    stop: bool = False
    data: Optional[Any] = None
