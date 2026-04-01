"""中间件基类与管理器

定义所有中间件继承的 BaseMiddleware ABC，
以及负责按优先级排序并依次执行钩子的 MiddlewareManager。
"""
from __future__ import annotations

import logging
from abc import ABC
from typing import Any, Callable, Dict, List, Optional, Tuple

from middleware.types import MiddlewareCommand

logger = logging.getLogger(__name__)


class BaseMiddleware(ABC):
    """中间件基类

    所有中间件继承此类，选择性地覆盖所需钩子。
    默认实现均为「直通」（不修改状态或消息）。

    Attributes:
        name:     中间件唯一名称
        priority: 执行优先级，数字越大越先运行（默认 0）
    """

    name: str = "BaseMiddleware"
    priority: int = 0

    # ------------------------------------------------------------------ hooks

    async def before_agent(
        self, state: Dict[str, Any]
    ) -> Optional[MiddlewareCommand]:
        """Agent 启动前（一次性）"""
        return None

    async def before_model(
        self, state: Dict[str, Any], messages: List[Any]
    ) -> Optional[MiddlewareCommand]:
        """每次模型调用前"""
        return None

    async def wrap_model_call(
        self,
        state: Dict[str, Any],
        messages: List[Any],
        handler: Callable,
    ) -> Any:
        """包装模型调用（链式）"""
        return await handler(messages)

    async def after_model(
        self, state: Dict[str, Any], response: Any
    ) -> Optional[MiddlewareCommand]:
        """每次模型调用后"""
        return None

    async def wrap_tool_call(
        self,
        state: Dict[str, Any],
        tool_call: Any,
        handler: Callable,
    ) -> Any:
        """包装工具调用（链式）"""
        return await handler(tool_call)

    async def after_tool_call(
        self, state: Dict[str, Any], tool_call: Any, result: Any
    ) -> Optional[MiddlewareCommand]:
        """每次工具调用后"""
        return None

    async def after_agent(
        self, state: Dict[str, Any], final_result: Any
    ) -> Optional[MiddlewareCommand]:
        """Agent 执行结束后（一次性）"""
        return None


class MiddlewareManager:
    """中间件管理器

    按优先级 (priority 降序) 维护中间件列表，提供统一的钩子执行接口。
    支持链式调用的 wrap_* 方法和顺序执行的普通钩子。
    """

    def __init__(self) -> None:
        self._middlewares: List[BaseMiddleware] = []

    # ------------------------------------------------------------------ registry

    def add(self, middleware: BaseMiddleware) -> "MiddlewareManager":
        """注册中间件，自动按 priority 降序排序"""
        self._middlewares.append(middleware)
        self._middlewares.sort(key=lambda m: m.priority, reverse=True)
        logger.debug("Added middleware %s (priority=%d)", middleware.name, middleware.priority)
        return self

    def remove(self, name: str) -> bool:
        """按名称移除中间件，返回是否成功"""
        before = len(self._middlewares)
        self._middlewares = [m for m in self._middlewares if m.name != name]
        return len(self._middlewares) < before

    @property
    def middlewares(self) -> List[BaseMiddleware]:
        return list(self._middlewares)

    def names(self) -> List[str]:
        return [m.name for m in self._middlewares]

    # ------------------------------------------------------------------ hook runners

    async def run_before_agent(
        self, state: Dict[str, Any]
    ) -> Optional[MiddlewareCommand]:
        for mw in self._middlewares:
            cmd = await mw.before_agent(state)
            if cmd:
                if cmd.stop:
                    return cmd
                if cmd.update:
                    state.update(cmd.update)
        return None

    async def run_before_model(
        self, state: Dict[str, Any], messages: List[Any]
    ) -> Tuple[Optional[MiddlewareCommand], List[Any]]:
        """执行所有 before_model 钩子，返回 (最后非空命令, 当前消息列表)"""
        last_cmd: Optional[MiddlewareCommand] = None
        for mw in self._middlewares:
            cmd = await mw.before_model(state, messages)
            if cmd:
                if cmd.stop:
                    return cmd, messages
                if cmd.update:
                    state.update(cmd.update)
                if cmd.messages is not None:
                    messages = cmd.messages
                last_cmd = cmd
        return last_cmd, messages

    async def run_wrap_tool_call(
        self,
        state: Dict[str, Any],
        tool_call: Any,
        handler: Callable,
    ) -> Any:
        """以洋葱模型链式执行 wrap_tool_call，最内层调用真实 handler"""
        mws = self._middlewares

        async def chain(idx: int) -> Any:
            if idx >= len(mws):
                return await handler(tool_call)

            async def next_handler(_tc: Any) -> Any:
                return await chain(idx + 1)

            return await mws[idx].wrap_tool_call(state, tool_call, next_handler)

        return await chain(0)

    async def run_after_tool_call(
        self, state: Dict[str, Any], tool_call: Any, result: Any
    ) -> None:
        for mw in self._middlewares:
            cmd = await mw.after_tool_call(state, tool_call, result)
            if cmd and cmd.update:
                state.update(cmd.update)

    async def run_after_model(
        self, state: Dict[str, Any], response: Any
    ) -> None:
        for mw in self._middlewares:
            cmd = await mw.after_model(state, response)
            if cmd and cmd.update:
                state.update(cmd.update)

    async def run_after_agent(
        self, state: Dict[str, Any], final_result: Any
    ) -> None:
        for mw in self._middlewares:
            cmd = await mw.after_agent(state, final_result)
            if cmd and cmd.update:
                state.update(cmd.update)
