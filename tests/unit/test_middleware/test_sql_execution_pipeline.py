"""SQL 执行流水线测试。"""

from middleware.subagent import SubAgentMiddleware


class DummyTool:
    def __init__(self, name, fn):
        self.name = name
        self._fn = fn

    def invoke(self, kwargs):
        return self._fn(kwargs)


def test_pipeline_generate_validate_execute_success(monkeypatch):
    mw = SubAgentMiddleware([])
    monkeypatch.setattr(mw, "_collect_table_context", lambda *_: "users(id,name)")

    llm_tool = DummyTool("llm_skill", lambda _k: '{"sql_query":"SELECT 1"}')
    sql_tool = DummyTool("sql_inter", lambda _k: "查询成功，共返回 1 条记录")

    result = mw._run_sql_specialist({"llm_skill": llm_tool, "sql_inter": sql_tool}, "测试任务", {"thread_id": "t1"})

    assert "SQL 查询专家已完成执行" in result
    assert "SELECT 1" in result


def test_pipeline_execute_fail_then_repair_success(monkeypatch):
    mw = SubAgentMiddleware([])
    monkeypatch.setattr(mw, "_collect_table_context", lambda *_: "users(id,name)")

    def llm_fn(kwargs):
        prompt = kwargs.get("prompt", "")
        if "修复" in prompt:
            return '{"sql_query":"SELECT 2"}'
        return '{"sql_query":"SELECT broken"}'

    sql_calls = {"n": 0}

    def sql_fn(kwargs):
        sql_calls["n"] += 1
        if sql_calls["n"] == 1:
            return "SQL 执行失败：Unknown column"
        return "查询成功，共返回 1 条记录"

    llm_tool = DummyTool("llm_skill", llm_fn)
    sql_tool = DummyTool("sql_inter", sql_fn)

    result = mw._run_sql_specialist({"llm_skill": llm_tool, "sql_inter": sql_tool}, "测试任务", {"thread_id": "t2"})

    assert "修复成功" in result
    assert "SELECT 2" in result


def test_pipeline_rejects_invalid_sql_contract(monkeypatch):
    mw = SubAgentMiddleware([])
    monkeypatch.setattr(mw, "_collect_table_context", lambda *_: "users(id,name)")

    llm_tool = DummyTool("llm_skill", lambda _k: '{"sql_query":"DELETE FROM users"}')
    sql_tool = DummyTool("sql_inter", lambda _k: "不应执行")

    result = mw._run_sql_specialist({"llm_skill": llm_tool, "sql_inter": sql_tool}, "测试任务", {"thread_id": "t3"})

    assert "SQL 契约校验失败" in result
