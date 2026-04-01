"""ContextEditor 与 ContextEditingMiddleware 单元测试"""
import asyncio
from typing import Any, Dict, List
from unittest.mock import MagicMock

from langchain_core.messages import ToolMessage, AIMessage, HumanMessage

from middleware.context_editor import ContextEdit, ContextEditor
from middleware.context_edit import ContextEditingMiddleware


# ────────────────── 辅助 ──────────────────────────────────────────────────────

def _tool_msg(content: str, tool_call_id: str = "tc-1") -> ToolMessage:
    return ToolMessage(content=content, tool_call_id=tool_call_id)


def _human(content: str) -> HumanMessage:
    return HumanMessage(content=content)


def _ai(content: str) -> AIMessage:
    return AIMessage(content=content)


# ────────────────── ContextEditor 测试 ───────────────────────────────────────

def test_truncate_keeps_last_n():
    editor = ContextEditor()
    editor.add_edit(ContextEdit("truncate", "messages", {"keep": 3}))
    msgs = [_human(f"msg{i}") for i in range(10)]
    result = editor.apply(msgs, {})
    assert len(result) == 3
    assert result[-1].content == "msg9"


def test_truncate_no_op_when_under_limit():
    editor = ContextEditor()
    editor.add_edit(ContextEdit("truncate", "messages", {"keep": 20}))
    msgs = [_human("a"), _human("b")]
    result = editor.apply(msgs, {})
    assert result == msgs


def test_clear_tool_results_replaces_old():
    editor = ContextEditor()
    editor.add_edit(
        ContextEdit("clear", "tool_results", {"keep": 2, "placeholder": "[cleared]"})
    )
    msgs = [
        _tool_msg("t1", "id1"),
        _tool_msg("t2", "id2"),
        _tool_msg("t3", "id3"),
        _tool_msg("t4", "id4"),
    ]
    result = editor.apply(msgs, {})
    assert len(result) == 4
    # 前两条被替换
    assert result[0].content == "[cleared]"
    assert result[1].content == "[cleared]"
    # 后两条保留
    assert result[2].content == "t3"
    assert result[3].content == "t4"


def test_clear_tool_results_preserves_non_tool_order():
    editor = ContextEditor()
    editor.add_edit(
        ContextEdit("clear", "tool_results", {"keep": 1, "placeholder": "[X]"})
    )
    msgs = [
        _human("q1"),
        _tool_msg("r1", "id1"),
        _ai("a1"),
        _tool_msg("r2", "id2"),
    ]
    result = editor.apply(msgs, {})
    assert result[0].content == "q1"     # human 保留
    assert result[1].content == "[X]"    # tool 1 被清理
    assert result[2].content == "a1"     # ai 保留
    assert result[3].content == "r2"     # tool 2 保留（最新1条）


def test_clear_edits_removes_all():
    editor = ContextEditor()
    editor.add_edit(ContextEdit("truncate", "messages", {"keep": 1}))
    editor.clear_edits()
    msgs = [_human("a"), _human("b"), _human("c")]
    result = editor.apply(msgs, {})
    assert len(result) == 3  # 无编辑，原样返回


# ────────────────── ContextEditingMiddleware 测试 ────────────────────────────

def test_middleware_no_op_below_threshold():
    mw = ContextEditingMiddleware(trigger_tokens=10_000)
    msgs = [_human("short")]
    state: Dict[str, Any] = {}
    result = asyncio.run(mw.before_model(state, msgs))
    assert result is None
    assert "context_edited" not in state


def test_middleware_triggers_above_threshold():
    mw = ContextEditingMiddleware(trigger_tokens=1, keep_tool_results=1)
    # 构造超长 tool 消息
    long_content = "x" * 10000
    msgs = [
        _tool_msg(long_content, "id1"),
        _tool_msg(long_content, "id2"),
        _tool_msg("short", "id3"),
    ]
    state: Dict[str, Any] = {}
    cmd = asyncio.run(mw.before_model(state, msgs))

    assert cmd is not None
    assert cmd.update is not None
    assert cmd.update.get("context_edited") is True
    assert cmd.messages is not None
    # 应保留最新 1 条 tool 消息，其余被替换
    tool_msgs = [m for m in cmd.messages if getattr(m, "type", None) == "tool"]
    non_placeholder = [m for m in tool_msgs if m.content != "[已清理]"]
    assert len(non_placeholder) == 1
    assert non_placeholder[0].content == "short"


def test_count_tokens_estimates_correctly():
    mw = ContextEditingMiddleware()
    msgs = [_human("a" * 400)]  # 400 chars → 100 tokens
    assert mw._count_tokens(msgs) == 100
