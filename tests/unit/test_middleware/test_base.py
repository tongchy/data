"""MiddlewareManager 与 BaseMiddleware 基础测试"""
import asyncio
from typing import Any, Callable, Dict, List, Optional

import pytest

from middleware.base import BaseMiddleware, MiddlewareManager
from middleware.types import MiddlewareCommand


# ────────────────── 辅助实现 ──────────────────────────────────────────────────

class RecordMiddleware(BaseMiddleware):
    """记录每次钩子调用的中间件"""

    def __init__(self, name: str, priority: int = 0) -> None:
        self.name = name
        self.priority = priority
        self.calls: List[str] = []

    async def before_model(
        self, state: Dict[str, Any], messages: List[Any]
    ) -> Optional[MiddlewareCommand]:
        self.calls.append("before_model")
        return None

    async def after_tool_call(
        self, state: Dict[str, Any], tool_call: Any, result: Any
    ) -> Optional[MiddlewareCommand]:
        self.calls.append("after_tool_call")
        return None


class UpdateMiddleware(BaseMiddleware):
    """before_model 中向 state 写入更新"""

    name = "UpdateMiddleware"
    priority = 5

    async def before_model(
        self, state: Dict[str, Any], messages: List[Any]
    ) -> Optional[MiddlewareCommand]:
        return MiddlewareCommand(update={"injected": True})


class StopMiddleware(BaseMiddleware):
    """before_model 中发出 stop 指令"""

    name = "StopMiddleware"
    priority = 10

    async def before_model(
        self, state: Dict[str, Any], messages: List[Any]
    ) -> Optional[MiddlewareCommand]:
        return MiddlewareCommand(stop=True, update={"stopped": True})


# ────────────────── 测试：优先级排序 ─────────────────────────────────────────

def test_add_sorts_by_priority():
    manager = MiddlewareManager()
    m_low  = RecordMiddleware("low",  priority=1)
    m_high = RecordMiddleware("high", priority=99)
    m_mid  = RecordMiddleware("mid",  priority=50)

    manager.add(m_low)
    manager.add(m_high)
    manager.add(m_mid)

    names = [m.name for m in manager.middlewares]
    assert names == ["high", "mid", "low"], f"Expected priority order, got {names}"


def test_remove_by_name():
    manager = MiddlewareManager()
    manager.add(RecordMiddleware("alpha"))
    manager.add(RecordMiddleware("beta"))
    assert manager.remove("alpha") is True
    assert [m.name for m in manager.middlewares] == ["beta"]


def test_remove_nonexistent_returns_false():
    manager = MiddlewareManager()
    assert manager.remove("ghost") is False


# ────────────────── 测试：run_before_model ────────────────────────────────────

def test_run_before_model_calls_all_middlewares():
    manager = MiddlewareManager()
    m1 = RecordMiddleware("m1", priority=10)
    m2 = RecordMiddleware("m2", priority=5)
    manager.add(m1)
    manager.add(m2)

    state: Dict[str, Any] = {}
    messages = ["hello"]
    asyncio.run(manager.run_before_model(state, messages))

    assert "before_model" in m1.calls
    assert "before_model" in m2.calls


def test_run_before_model_applies_update():
    manager = MiddlewareManager()
    manager.add(UpdateMiddleware())

    state: Dict[str, Any] = {}
    asyncio.run(manager.run_before_model(state, []))
    assert state.get("injected") is True


def test_run_before_model_stop_halts_chain():
    manager = MiddlewareManager()
    stop_mw   = StopMiddleware()            # priority=10
    record_mw = RecordMiddleware("after", priority=1)
    manager.add(stop_mw)
    manager.add(record_mw)

    state: Dict[str, Any] = {}
    cmd, _ = asyncio.run(manager.run_before_model(state, []))

    assert cmd is not None
    assert cmd.stop is True
    # record_mw 不应该被调用到
    assert "before_model" not in record_mw.calls


def test_run_before_model_replaces_messages():
    class MessageReplaceMiddleware(BaseMiddleware):
        name = "MessageReplaceMiddleware"
        priority = 0

        async def before_model(self, state, messages):
            return MiddlewareCommand(messages=["replaced"])

    manager = MiddlewareManager()
    manager.add(MessageReplaceMiddleware())

    state: Dict[str, Any] = {}
    _, out_messages = asyncio.run(manager.run_before_model(state, ["original"]))
    assert out_messages == ["replaced"]


# ────────────────── 测试：run_wrap_tool_call 链 ───────────────────────────────

def test_run_wrap_tool_call_passthrough():
    """无中间件时应直接调用 handler"""

    async def handler(tc):
        return f"result:{tc}"

    manager = MiddlewareManager()
    result = asyncio.run(manager.run_wrap_tool_call({}, "my_tool", handler))
    assert result == "result:my_tool"


def test_run_wrap_tool_call_chain_order():
    """中间件应按 priority 由高到低包装（洋葱模型）"""
    order: List[str] = []

    class OuterMW(BaseMiddleware):
        name = "outer"
        priority = 10

        async def wrap_tool_call(self, state, tool_call, handler):
            order.append("outer_before")
            res = await handler(tool_call)
            order.append("outer_after")
            return res

    class InnerMW(BaseMiddleware):
        name = "inner"
        priority = 1

        async def wrap_tool_call(self, state, tool_call, handler):
            order.append("inner_before")
            res = await handler(tool_call)
            order.append("inner_after")
            return res

    async def handler(tc):
        order.append("handler")
        return "done"

    manager = MiddlewareManager()
    manager.add(InnerMW())
    manager.add(OuterMW())
    asyncio.run(manager.run_wrap_tool_call({}, "tool", handler))

    assert order == ["outer_before", "inner_before", "handler", "inner_after", "outer_after"]
