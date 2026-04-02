"""SQL 生成链路测试。"""

from middleware.subagent import SubAgentMiddleware


class DummyTool:
    def __init__(self, name, payload):
        self.name = name
        self._payload = payload

    def invoke(self, _kwargs):
        return self._payload


def test_sql_generator_returns_contract_json():
    mw = SubAgentMiddleware([])
    tool_map = {"llm_skill": DummyTool("llm_skill", '{"sql_query": "SELECT 1"}')}

    sql = mw.generate_sql_via_agent("查询测试", "table t(id)", tool_map)

    assert sql == "SELECT 1"


def test_sql_generator_rejects_non_select_statement():
    mw = SubAgentMiddleware([])
    ok, reason = mw.validate_sql_for_executor("DELETE FROM t")

    assert ok is False
    assert "SELECT/WITH" in reason or "危险关键字" in reason


def test_sql_generator_handles_markdown_wrapped_output():
    mw = SubAgentMiddleware([])
    text = """```json
{"sql_query": "SELECT * FROM `users` LIMIT 10"}
```"""

    sql = mw._extract_sql_from_text(text)

    assert sql == "SELECT * FROM `users` LIMIT 10"
