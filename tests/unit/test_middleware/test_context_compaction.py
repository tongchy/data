"""上下文压缩与槽位路由测试。"""

from middleware.subagent import SubAgentMiddleware


class DummyBackend:
    def __init__(self):
        self.writes = []

    def write_file(self, path, content, append=False):
        self.writes.append((path, content, append))
        return {"success": True}


class DummyTool:
    def __init__(self, name, fn):
        self.name = name
        self._fn = fn

    def invoke(self, kwargs):
        return self._fn(kwargs)


def _summary_json():
    return (
        '{"task_goal":"统计设备",'
        '"tool_decision":"优先 sql_specialist",'
        '"sql_reasoning":"按 schema 生成",'
        '"latest_valid_sql":"SELECT 1",'
        '"latest_error":"",'
        '"schema_digest":"users(id,name)",'
        '"next_action":"执行 SQL"}'
    )


def test_context_compaction_keeps_sql_contract_fields():
    mw = SubAgentMiddleware([])
    summary = mw._rule_summarize_fallback("任务", {"latest_valid_sql": "SELECT 1"}, [])

    assert "latest_valid_sql" in summary
    assert "task_goal" in summary


def test_context_compaction_drops_large_tool_payloads():
    mw = SubAgentMiddleware([])
    dropped = mw._build_context_drop_blacklist(["x" * 2000])

    assert len(dropped["dropped_payloads"]) == 1


def test_context_snapshot_written_to_files_path():
    backend = DummyBackend()
    mw = SubAgentMiddleware([], backend=backend)
    tool_map = {"llm_skill": DummyTool("llm_skill", lambda _k: _summary_json())}

    ctx = mw.context_compact_gate("任务", {"thread_id": "abc"}, ["tool output"], tool_map)

    assert "latest_summary" in ctx
    assert backend.writes
    assert backend.writes[0][0] == "/files/context_snapshot_abc.md"


def test_context_compaction_prefers_llm_summary():
    mw = SubAgentMiddleware([])
    tool_map = {"llm_skill": DummyTool("llm_skill", lambda _k: _summary_json())}

    ctx = mw.context_compact_gate("任务", {"thread_id": "a"}, [], tool_map)

    assert ctx["latest_summary"]["task_goal"] == "统计设备"
    assert ctx["latest_summary"].get("_fallback") is None


def test_context_compaction_fallback_when_llm_fails():
    mw = SubAgentMiddleware([])
    tool_map = {"llm_skill": DummyTool("llm_skill", lambda _k: (_ for _ in ()).throw(RuntimeError("boom")))}

    ctx = mw.context_compact_gate("任务", {"thread_id": "a"}, ["output"], tool_map)

    assert ctx["latest_summary"]["_fallback"] is True


def test_summary_auto_routed_to_slots():
    mw = SubAgentMiddleware([])
    tool_map = {"llm_skill": DummyTool("llm_skill", lambda _k: _summary_json())}

    ctx = mw.context_compact_gate("任务", {"thread_id": "a"}, [], tool_map)

    slots = ctx["summary_slots"]
    assert slots["decision_summary"]
    assert slots["sql_summary"]
    assert slots["schema_summary"]


def test_pre_model_prompt_includes_slot_summaries():
    mw = SubAgentMiddleware([])
    context = {
        "summary_slots": {
            "decision_summary": ["d1"],
            "schema_summary": ["s1"],
            "sql_summary": ["q1"],
            "error_summary": ["e1"],
        }
    }

    prompt = mw._compose_runtime_prompt_from_slots(context)

    assert "[decision_summary]" in prompt
    assert "[schema_summary]" in prompt
    assert "[sql_summary]" in prompt
    assert "[error_summary]" in prompt
