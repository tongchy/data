"""ToolAuthMiddleware 单元测试"""
import asyncio
from typing import Any, Callable, Dict

from middleware.tool_auth import ToolAuthMiddleware
from middleware.permissions import PermissionManager, Role


# ────────────────── 辅助 ──────────────────────────────────────────────────────

class FakeToolCall:
    def __init__(self, name: str, tool_id: str = "tc-001"):
        self.name = name
        self.id = tool_id


async def _call(mw: ToolAuthMiddleware, role: str, tool_name: str) -> Any:
    state: Dict[str, Any] = {"context": {"role": role}}

    async def handler(tc):
        return f"ok:{tc.name}"

    return await mw.wrap_tool_call(state, FakeToolCall(tool_name), handler)


# ────────────────── 测试 ─────────────────────────────────────────────────────

def test_admin_can_use_any_tool():
    mw = ToolAuthMiddleware()
    result = asyncio.run(_call(mw, "admin", "delete_file"))
    assert result == "ok:delete_file"


def test_guest_can_read():
    mw = ToolAuthMiddleware()
    result = asyncio.run(_call(mw, "guest", "read_file"))
    assert result == "ok:read_file"


def test_guest_denied_write():
    mw = ToolAuthMiddleware()
    state: Dict[str, Any] = {"context": {"role": "guest"}}

    async def run():
        async def handler(tc):
            return "ok"
        return await mw.wrap_tool_call(state, FakeToolCall("write_file"), handler)

    result = asyncio.run(run())
    # 应返回 ToolMessage 拒绝消息
    from langchain_core.messages import ToolMessage
    assert isinstance(result, ToolMessage)
    assert "权限拒绝" in result.content
    assert state["auth_denials"] == 1


def test_analyst_can_execute():
    mw = ToolAuthMiddleware()
    result = asyncio.run(_call(mw, "analyst", "python_inter"))
    assert result == "ok:python_inter"


def test_user_denied_execute():
    mw = ToolAuthMiddleware()
    state: Dict[str, Any] = {"context": {"role": "user"}}

    async def run():
        async def handler(tc):
            return "ok"
        return await mw.wrap_tool_call(state, FakeToolCall("python_inter"), handler)

    result = asyncio.run(run())
    from langchain_core.messages import ToolMessage
    assert isinstance(result, ToolMessage)


def test_unknown_role_treated_as_guest():
    mw = ToolAuthMiddleware()
    state: Dict[str, Any] = {"context": {"role": "hacker"}}

    async def run():
        async def handler(tc):
            return "ok"
        return await mw.wrap_tool_call(state, FakeToolCall("delete_file"), handler)

    result = asyncio.run(run())
    from langchain_core.messages import ToolMessage
    assert isinstance(result, ToolMessage)


def test_unregistered_tool_denied():
    mw = ToolAuthMiddleware()
    # "magic_tool" 未注册到 PermissionManager，默认拒绝
    state: Dict[str, Any] = {"context": {"role": "analyst"}}

    async def run():
        async def handler(tc):
            return "ok"
        return await mw.wrap_tool_call(state, FakeToolCall("magic_tool"), handler)

    result = asyncio.run(run())
    from langchain_core.messages import ToolMessage
    assert isinstance(result, ToolMessage)


def test_cache_cleared_after_agent():
    mw = ToolAuthMiddleware()
    # 先产生缓存
    asyncio.run(_call(mw, "guest", "read_file"))
    assert len(mw._cache) > 0
    # after_agent 应清除
    asyncio.run(mw.after_agent({}, None))
    assert len(mw._cache) == 0


def test_auth_denials_accumulate():
    mw = ToolAuthMiddleware()
    state: Dict[str, Any] = {"context": {"role": "guest"}}

    async def run():
        async def handler(tc):
            return "ok"
        await mw.wrap_tool_call(state, FakeToolCall("write_file"), handler)
        await mw.wrap_tool_call(state, FakeToolCall("delete_file"), handler)

    asyncio.run(run())
    assert state["auth_denials"] == 2
