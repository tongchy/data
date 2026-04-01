"""Tool runtime middleware tests - 验证简化后的 fallback 行为。

注：权限检查和缓存功能已移至新的中间件系统（ToolAuthMiddleware 和 ToolCacheMiddleware）。
此文件现在验证 tool_runtime 作为同步 fallback 时的基本行为。
"""

from langchain_core.tools import StructuredTool

from middleware.tool_runtime import ToolRuntimeMiddleware


def test_tool_runtime_basic_invocation():
    """验证 tool_runtime 进行基本的工具调用和统计。"""
    calls = {"count": 0}

    def echo(value: str) -> str:
        calls["count"] += 1
        return f"result:{value}"

    tool = StructuredTool.from_function(func=echo, name="echo", description="echo tool")
    state = {
        "tool_usage_stats": {},
        "tool_failures": {},
        "total_tool_calls": 0,
        "consecutive_failures": 0,
    }

    wrapped = ToolRuntimeMiddleware().wrap_tool(tool, state=state, permissions=["*"])
    result = wrapped.invoke({"value": "test"})

    # 验证基本调用工作
    assert result == "result:test"
    assert calls["count"] == 1
    assert state["total_tool_calls"] == 1
    assert state["tool_usage_stats"]["echo"] == 1
    assert state["consecutive_failures"] == 0


def test_tool_runtime_failure_tracking():
    """验证 tool_runtime 跟踪失败。"""
    def failing_tool() -> str:
        raise ValueError("Test error")

    tool = StructuredTool.from_function(func=failing_tool, name="fail", description="fail tool")
    state = {
        "tool_usage_stats": {},
        "tool_failures": {},
        "total_tool_calls": 0,
        "consecutive_failures": 0,
    }

    wrapped = ToolRuntimeMiddleware().wrap_tool(tool, state=state, permissions=["*"])
    result = wrapped.invoke({})

    # 验证失败跟踪
    assert "工具调用失败" in result
    assert state["tool_failures"]["fail"] == 1
    assert state["consecutive_failures"] == 1
