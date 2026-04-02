"""Supervisor HITL resume 测试。"""

import asyncio

from agents.supervisor import SupervisorAgent
from config.settings import Settings


class DummyGraph:
    def __init__(self, result):
        self.result = result

    async def ainvoke(self, _payload, config=None):
        return {"messages": [type("Msg", (), {"content": self.result})()]}


def test_resume_uses_thread_runtime_graph(monkeypatch):
    monkeypatch.setattr("agents.supervisor.create_llm", lambda settings: object())
    monkeypatch.setattr("agents.supervisor.create_react_agent", lambda **kwargs: DummyGraph("base"))

    agent = SupervisorAgent(Settings(), store=None, checkpointer=None)
    agent.runtime_graphs["t-resume"] = DummyGraph("runtime")

    result = asyncio.run(agent.resume("t-resume", {"decision": "approve"}))
    assert result["messages"][0].content == "runtime"


def test_resume_falls_back_to_base_graph(monkeypatch):
    monkeypatch.setattr("agents.supervisor.create_llm", lambda settings: object())
    monkeypatch.setattr("agents.supervisor.create_react_agent", lambda **kwargs: DummyGraph("base"))

    agent = SupervisorAgent(Settings(), store=None, checkpointer=None)

    result = asyncio.run(agent.resume("missing-thread", {"decision": "approve"}))
    assert result["messages"][0].content == "base"
