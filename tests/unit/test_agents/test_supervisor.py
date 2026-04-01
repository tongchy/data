"""Supervisor tests."""

import asyncio
from types import SimpleNamespace

from langchain_core.tools import StructuredTool

from agents.supervisor import SupervisorAgent
from config.settings import Settings
from tools.code.llm_skill_tool import llm_skill
from tools.loader.tool_loader import TaskType, ToolLoader


class FakeRuntimeAgent:
    async def ainvoke(self, payload, config=None):
        user_message = payload["messages"][0]["content"]
        return {"messages": [SimpleNamespace(content=f"handled:{user_message}", type="ai")]}


def test_supervisor_invoke_updates_runtime_state(monkeypatch):
    monkeypatch.setattr("agents.supervisor.create_llm", lambda settings: object())
    monkeypatch.setattr("agents.supervisor.create_react_agent", lambda **kwargs: FakeRuntimeAgent())

    agent = SupervisorAgent(Settings(), store=None)

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

    result = asyncio.run(agent._invoke_tool_via_manager(tool, {"path": "/tmp/x"}, state, permissions=["write_file"]))

    assert "权限拒绝" in result
    assert state["auth_denials"] == 1
    assert state["total_tool_calls"] == 0


def test_tool_loader_prioritizes_llm_skill_for_text_processing():
    loader = ToolLoader()

    task_type = loader.detect_task_type("请把下面内容总结并分类")
    tools = loader.load_tools(task_type, include_base=False)
    tool_names = [tool.name for tool in tools]

    assert task_type == TaskType.TEXT_PROCESSING
    assert "llm_skill" in tool_names


def test_supervisor_runtime_exposes_llm_skill_for_text_tasks(monkeypatch):
    captured = {}

    def fake_create_react_agent(**kwargs):
        if kwargs.get("name") == "supervisor_agent_runtime":
            captured["runtime_tools"] = [tool.name for tool in kwargs["tools"]]
            captured["runtime_prompt"] = kwargs["prompt"]
        return FakeRuntimeAgent()

    monkeypatch.setattr("agents.supervisor.create_llm", lambda settings: object())
    monkeypatch.setattr("agents.supervisor.create_react_agent", fake_create_react_agent)

    agent = SupervisorAgent(Settings(), store=None)
    result = asyncio.run(agent.invoke("请把下面文本总结并分类", thread_id="thread-text", permissions=["*"]))

    assert result["messages"][-1].content == "handled:请把下面文本总结并分类"
    assert "llm_skill" in captured["runtime_tools"]
    assert "优先使用 llm_skill" in captured["runtime_prompt"]
    assert agent.thread_states["thread-text"]["task_type"] == TaskType.TEXT_PROCESSING.value


def test_supervisor_runtime_invokes_llm_skill_for_text_tasks(monkeypatch):
    class DummyLLM:
        def invoke(self, _messages):
            class Resp:
                content = '{"summary": "已总结", "category": "summary"}'

            return Resp()

    class CallingRuntimeAgent:
        def __init__(self, tools):
            self._tools = {tool.name: tool for tool in tools}

        async def ainvoke(self, payload, config=None):
            result = self._tools["llm_skill"].invoke(
                {
                    "prompt": payload["messages"][0]["content"],
                    "json_mode": True,
                    "output_schema": {
                        "type": "object",
                        "properties": {
                            "summary": {"type": "string"},
                            "category": {"type": "string"},
                        },
                        "required": ["summary", "category"],
                    },
                }
            )
            return {"messages": [SimpleNamespace(content=result, type="ai")]}

    def fake_create_react_agent(**kwargs):
        if kwargs.get("name") == "supervisor_agent_runtime":
            return CallingRuntimeAgent(kwargs["tools"])
        return FakeRuntimeAgent()

    monkeypatch.setattr("agents.supervisor.create_llm", lambda settings: object())
    monkeypatch.setattr("agents.supervisor.create_react_agent", fake_create_react_agent)

    llm_skill._settings.model.api_key = "test-key"
    llm_skill._llm = DummyLLM()

    agent = SupervisorAgent(Settings(), store=None)
    result = asyncio.run(agent.invoke("请把下面文本总结并分类", thread_id="thread-call", permissions=["*"]))

    content = result["messages"][-1].content
    assert "已总结" in content
    assert "category" in content
