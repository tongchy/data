"""graph checkpointer 工厂测试。"""

from types import SimpleNamespace

import graph


def test_get_checkpointer_memory(monkeypatch):
    monkeypatch.setattr(graph, "_checkpointer", None)
    monkeypatch.setattr(graph, "get_settings", lambda: SimpleNamespace(checkpointer_backend="memory", checkpointer_path=None))

    cp = graph.get_checkpointer()

    assert cp is not None
    assert cp.__class__.__name__ in {"MemorySaver", "InMemorySaver"}


def test_get_checkpointer_sqlite(monkeypatch):
    monkeypatch.setattr(graph, "_checkpointer", None)
    monkeypatch.setattr(
        graph,
        "get_settings",
        lambda: SimpleNamespace(checkpointer_backend="sqlite", checkpointer_path="./.test_checkpoints.sqlite"),
    )

    cp = graph.get_checkpointer()

    assert cp is not None
    assert cp.__class__.__name__ == "SqliteSaver"
