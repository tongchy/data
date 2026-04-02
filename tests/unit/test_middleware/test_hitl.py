"""HITL 中断恢复测试。"""

from config.settings import Settings
from middleware.subagent import SubAgentMiddleware


def test_hitl_resume_approve():
    mw = SubAgentMiddleware([], settings=Settings(enable_hitl=True))
    out = mw._hitl_resume_handler({"decision": "approve"}, "SELECT 1", "schema", {})
    assert out == "SELECT 1"


def test_hitl_resume_edit_and_validate():
    mw = SubAgentMiddleware([], settings=Settings(enable_hitl=True))
    out = mw._hitl_resume_handler(
        {"decision": "edit", "edited_sql": "SELECT 2"},
        "SELECT 1",
        "schema",
        {},
    )
    assert out == "SELECT 2"


def test_hitl_resume_reject():
    mw = SubAgentMiddleware([], settings=Settings(enable_hitl=True))
    out = mw._hitl_resume_handler({"decision": "reject"}, "SELECT 1", "schema", {})
    assert out is None


def test_hitl_interrupt_disabled_returns_none():
    mw = SubAgentMiddleware([], settings=Settings(enable_hitl=False))
    out = mw._hitl_interrupt("SELECT 1", "schema", "goal")
    assert out is None
