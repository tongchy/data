"""API integration tests."""

import json

from api.routes import chat as chat_route


class DummySupervisor:
    async def invoke(self, message: str, thread_id: str = None, **kwargs):
        return {"content": f"supervisor:{message}:{thread_id}"}


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
