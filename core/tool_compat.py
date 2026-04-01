"""LangChain tool 装饰器兼容层。"""

from typing import Callable
from langchain_core.tools import tool


def compatible_tool(name: str, description: str):
    """返回兼容不同 langchain-core 版本的 `@tool` 装饰器。"""

    def decorator(func: Callable):
        try:
            wrapped = tool(name=name, description=description)(func)
        except TypeError:
            wrapped = tool(name)(func)
            if hasattr(wrapped, "description"):
                wrapped.description = description
        return wrapped

    return decorator
