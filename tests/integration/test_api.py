"""API integration tests."""

import json
from types import SimpleNamespace

from api.routes import chat as chat_route
from api.routes import resume as resume_route
from agents.supervisor import SupervisorAgent
from config.settings import Settings


class DummySupervisor:
    async def invoke(self, message: str, thread_id: str = None, **kwargs):
        return {"content": f"supervisor:{message}:{thread_id}"}

    async def resume(self, thread_id: str, payload: dict):
        decision = payload.get("decision", "approve")
        return {"messages": [SimpleNamespace(content=f"resumed:{thread_id}:{decision}", type="ai")]}


def test_chat_route_uses_supervisor(test_client, monkeypatch):
    monkeypatch.setattr(chat_route, "get_agent", lambda thread_id: DummySupervisor())

    response = test_client.post(
        "/api/chat",
        json={"message": "分析设备数据", "thread_id": "t-1", "stream": False},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["content"] == "supervisor:分析设备数据:t-1"
    assert body["thread_id"] == "t-1"


def test_chat_stream_route_uses_supervisor(test_client, monkeypatch):
    monkeypatch.setattr(chat_route, "get_agent", lambda thread_id: DummySupervisor())

    with test_client.stream(
        "POST",
        "/api/chat/stream",
        json={"message": "画图", "thread_id": "stream-1", "stream": True},
    ) as response:
        payload = "".join(response.iter_text())

    assert response.status_code == 200
    events = []
    for chunk in payload.strip().split("\n\n"):
        if chunk.startswith("data: "):
            events.append(json.loads(chunk[6:]))

    assert events[0]["type"] == "assistant"
    assert events[0]["content"] == "supervisor:画图:stream-1"
    assert events[-1]["done"] is True


def test_chat_route_hits_text_processing_branch(test_client, monkeypatch):
    captured = {}

    class FakeRuntimeAgent:
        async def ainvoke(self, payload, config=None):
            return {"messages": [SimpleNamespace(content="text-branch-hit", type="ai")]}

    def fake_create_react_agent(**kwargs):
        if kwargs.get("name") == "supervisor_agent_runtime":
            captured["tool_names"] = [tool.name for tool in kwargs["tools"]]
            captured["prompt"] = kwargs["prompt"]
        return FakeRuntimeAgent()

    monkeypatch.setattr("agents.supervisor.create_llm", lambda settings: object())
    monkeypatch.setattr("agents.supervisor.create_react_agent", fake_create_react_agent)

    agent = SupervisorAgent(Settings(), store=None)
    monkeypatch.setattr(chat_route, "get_agent", lambda thread_id: agent)

    response = test_client.post(
        "/api/chat",
        json={"message": "请总结并分类下面这段文本", "thread_id": "api-text-1", "stream": False},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["content"] == ""
    assert "llm_skill" in captured["tool_names"]
    assert "优先使用 llm_skill" in captured["prompt"]


def test_resume_route_uses_supervisor_resume(test_client, monkeypatch):
    monkeypatch.setattr(resume_route, "get_agent", lambda thread_id: DummySupervisor())

    response = test_client.post(
        "/api/resume",
        json={"thread_id": "r-1", "decision": "approve"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["thread_id"] == "r-1"
    assert body["decision"] == "approve"
    assert body["content"] == "resumed:r-1:approve"
