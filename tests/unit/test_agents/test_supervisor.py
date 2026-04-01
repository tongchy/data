"""Supervisor tests."""

from types import SimpleNamespace

from langchain_core.tools import StructuredTool

from agents.supervisor import SupervisorAgent
from config.settings import Settings


class FakeRuntimeAgent:
    async def ainvoke(self, payload, config=None):
        user_message = payload["messages"][0]["content"]
        return {"messages": [SimpleNamespace(content=f"handled:{user_message}", type="ai")]}


def test_supervisor_invoke_updates_runtime_state(monkeypatch):
    monkeypatch.setattr("agents.supervisor.create_llm", lambda settings: object())
    monkeypatch.setattr("agents.supervisor.create_react_agent", lambda **kwargs: FakeRuntimeAgent())

    agent = SupervisorAgent(Settings(), store=None)

    import asyncio
    result = asyncio.run(agent.invoke("查询 t_orders", thread_id="thread-a", permissions=["*"]))

    assert result["messages"][-1].content == "handled:查询 t_orders"
    state = agent.thread_states["thread-a"]
    assert state["current_task"] == "查询 t_orders"
    assert state["task_type"]
    assert "runtime_stats" in state
    assert state["runtime_stats"]["middleware_order"][0] == "todo_list"


def test_supervisor_manager_tool_cache_path(monkeypatch):
    monkeypatch.setattr("agents.supervisor.create_llm", lambda settings: object())
    monkeypatch.setattr("agents.supervisor.create_react_agent", lambda **kwargs: FakeRuntimeAgent())

    agent = SupervisorAgent(Settings(), store=None)
    calls = {"count": 0}

    def echo(value: str) -> str:
        calls["count"] += 1
        return f"echo:{value}"

    tool = StructuredTool.from_function(func=echo, name="echo", description="echo")
    state = {
        "context": {"role": "admin"},
        "tool_usage_stats": {},
        "tool_failures": {},
        "tool_cache": {},
        "cache_hits": 0,
        "cache_misses": 0,
        "auth_denials": 0,
        "total_tool_calls": 0,
        "consecutive_failures": 0,
    }

    import asyncio

    first = asyncio.run(agent._invoke_tool_via_manager(tool, {"value": "x"}, state, permissions=["echo"]))
    second = asyncio.run(agent._invoke_tool_via_manager(tool, {"value": "x"}, state, permissions=["echo"]))

    assert first == "echo:x"
    assert "[缓存]" in second
    assert calls["count"] == 1
    assert state["cache_hits"] == 1
    assert state["total_tool_calls"] == 1


def test_supervisor_manager_tool_auth_path(monkeypatch):
    monkeypatch.setattr("agents.supervisor.create_llm", lambda settings: object())
    monkeypatch.setattr("agents.supervisor.create_react_agent", lambda **kwargs: FakeRuntimeAgent())

    agent = SupervisorAgent(Settings(), store=None)

    def write_file(path: str) -> str:
        return path

    tool = StructuredTool.from_function(func=write_file, name="write_file", description="write")
    state = {
        "context": {"role": "guest"},
        "tool_usage_stats": {},
        "tool_failures": {},
        "tool_cache": {},
        "cache_hits": 0,
        "cache_misses": 0,
        "auth_denials": 0,
        "total_tool_calls": 0,
        "consecutive_failures": 0,
    }

    import asyncio

    result = asyncio.run(agent._invoke_tool_via_manager(tool, {"path": "/tmp/x"}, state, permissions=["write_file"]))

    assert "权限拒绝" in result
    assert state["auth_denials"] == 1
    assert state["total_tool_calls"] == 0
