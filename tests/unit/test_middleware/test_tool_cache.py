"""ToolCacheMiddleware 单元测试"""
import asyncio
from typing import Any, Callable, Dict
from unittest.mock import MagicMock

from langchain_core.messages import ToolMessage

from middleware.tool_cache import ToolCacheMiddleware
from middleware.cache_backend import InMemoryCacheBackend


# ────────────────── 辅助 ──────────────────────────────────────────────────────

class FakeToolCall:
    def __init__(self, name: str, args: Dict[str, Any] | None = None):
        self.name = name
        self.args = args or {}
        self.id = "tc-001"


def _state() -> Dict[str, Any]:
    return {"cache_hits": 0, "cache_misses": 0}


async def _invoke(mw: ToolCacheMiddleware, tool_name: str, args: Dict, state: Dict, response: str) -> Any:
    call_count = {"n": 0}

    async def handler(tc):
        call_count["n"] += 1
        return ToolMessage(content=response, tool_call_id=tc.id)

    result = await mw.wrap_tool_call(state, FakeToolCall(tool_name, args), handler)
    return result, call_count["n"]


# ────────────────── 测试 ─────────────────────────────────────────────────────

def test_cache_miss_executes_handler():
    mw = ToolCacheMiddleware()
    state = _state()
    result, calls = asyncio.run(_invoke(mw, "sql_inter", {"q": "SELECT 1"}, state, "row1"))
    assert calls == 1
    assert state["cache_misses"] == 1
    assert state["cache_hits"] == 0


def test_cache_hit_returns_cached():
    mw = ToolCacheMiddleware()
    state = _state()
    # 第一次 miss → 写缓存
    asyncio.run(_invoke(mw, "sql_inter", {"q": "SELECT 1"}, state, "row1"))
    # 第二次 hit → 不执行 handler
    result, calls = asyncio.run(_invoke(mw, "sql_inter", {"q": "SELECT 1"}, state, "ignored"))
    assert calls == 0
    assert state["cache_hits"] == 1
    assert isinstance(result, ToolMessage)
    assert "[缓存]" in result.content
    assert "row1" in result.content


def test_different_args_are_different_cache_entries():
    mw = ToolCacheMiddleware()
    state = _state()
    asyncio.run(_invoke(mw, "sql_inter", {"q": "SELECT 1"}, state, "row1"))
    result, calls = asyncio.run(_invoke(mw, "sql_inter", {"q": "SELECT 2"}, state, "row2"))
    assert calls == 1  # 不同参数不命中缓存


def test_skip_tool_bypasses_cache():
    mw = ToolCacheMiddleware(skip_tools={"write_file"})
    state = _state()
    # 第一次写入缓存跳过
    asyncio.run(_invoke(mw, "write_file", {}, state, "written"))
    # 第二次仍然调用 handler
    result, calls = asyncio.run(_invoke(mw, "write_file", {}, state, "written2"))
    assert calls == 1
    assert state["cache_hits"] == 0


def test_stats_reflect_hits_and_misses():
    backend = InMemoryCacheBackend()
    mw = ToolCacheMiddleware(backend=backend)
    state = _state()
    asyncio.run(_invoke(mw, "extract_data", {"id": 1}, state, "data"))
    asyncio.run(_invoke(mw, "extract_data", {"id": 1}, state, "data"))  # hit
    stats = mw.get_stats()
    assert stats["cache_hits"] == 1
    assert stats["cache_misses"] == 1
    assert stats["hit_rate"] == 50.0


def test_empty_content_not_cached():
    """Handler 返回空内容时不写入缓存"""
    mw = ToolCacheMiddleware()
    state = _state()

    async def run():
        async def handler(tc):
            return ToolMessage(content="", tool_call_id=tc.id)
        return await mw.wrap_tool_call(state, FakeToolCall("some_tool"), handler)

    asyncio.run(run())
    # 再次调用应该再次执行 handler（未缓存）
    call_count = {"n": 0}

    async def run2():
        async def handler(tc):
            call_count["n"] += 1
            return ToolMessage(content="", tool_call_id=tc.id)
        return await mw.wrap_tool_call(state, FakeToolCall("some_tool"), handler)

    asyncio.run(run2())
    assert call_count["n"] == 1
