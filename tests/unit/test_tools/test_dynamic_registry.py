"""DynamicToolRegistry 单元测试"""
from tools.dynamic_registry import DynamicToolRegistry


# ────────────────── 辅助 ──────────────────────────────────────────────────────

class FakeTool:
    def __init__(self, name: str):
        self.name = name


# ────────────────── 测试 ─────────────────────────────────────────────────────

def test_register_and_contains():
    reg = DynamicToolRegistry()
    tool = FakeTool("my_tool")
    assert reg.register(tool) is True
    assert "my_tool" in reg


def test_register_duplicate_returns_false():
    reg = DynamicToolRegistry()
    tool = FakeTool("dup_tool")
    reg.register(tool)
    assert reg.register(tool) is False
    assert len(reg) == 1


def test_unregister_existing():
    reg = DynamicToolRegistry()
    reg.register(FakeTool("alpha"))
    assert reg.unregister("alpha") is True
    assert "alpha" not in reg
    assert len(reg) == 0


def test_unregister_nonexistent():
    reg = DynamicToolRegistry()
    assert reg.unregister("ghost") is False


def test_get_returns_tool():
    reg = DynamicToolRegistry()
    tool = FakeTool("finder")
    reg.register(tool)
    assert reg.get("finder") is tool


def test_get_nonexistent_returns_none():
    reg = DynamicToolRegistry()
    assert reg.get("missing") is None


def test_list_tools():
    reg = DynamicToolRegistry()
    reg.register(FakeTool("a"))
    reg.register(FakeTool("b"))
    reg.register(FakeTool("c"))
    assert sorted(reg.list_tools()) == ["a", "b", "c"]


def test_get_all():
    reg = DynamicToolRegistry()
    tool = FakeTool("x")
    reg.register(tool)
    all_tools = reg.get_all()
    assert tool in all_tools


def test_metadata_stored_and_retrieved():
    reg = DynamicToolRegistry()
    meta = {"source": "mcp", "version": "2.0"}
    reg.register(FakeTool("meta_tool"), metadata=meta)
    assert reg.get_metadata("meta_tool") == meta


def test_metadata_default_empty():
    reg = DynamicToolRegistry()
    reg.register(FakeTool("no_meta"))
    assert reg.get_metadata("no_meta") == {}


def test_metadata_nonexistent_empty():
    reg = DynamicToolRegistry()
    assert reg.get_metadata("ghost") == {}


def test_len():
    reg = DynamicToolRegistry()
    assert len(reg) == 0
    reg.register(FakeTool("t1"))
    reg.register(FakeTool("t2"))
    assert len(reg) == 2


def test_repr_contains_tool_names():
    reg = DynamicToolRegistry()
    reg.register(FakeTool("foo"))
    assert "foo" in repr(reg)
