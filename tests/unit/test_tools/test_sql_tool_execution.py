"""SQL tool execution tests."""

from tools.sql.query_tool import SQLQueryTool


class DummyDB:
    def __init__(self, results):
        self._results = results

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def execute_query(self, sql):
        return self._results

    def table_exists(self, table_name: str) -> bool:
        return True

    def get_table_count(self, table_name: str) -> int:
        return len(self._results)

    def execute_scalar(self, sql, params=None):
        return 1


def test_sql_tool_execute_success(monkeypatch):
    monkeypatch.setattr("tools.sql.query_tool.DatabaseManager", lambda: DummyDB([{"id": 1}, {"id": 2}]))

    tool = SQLQueryTool()
    result = tool._execute("SELECT * FROM users")

    assert result.success is True
    assert result.metadata["total_count"] == 2
    assert len(result.data) == 2


def test_sql_tool_execute_empty_result(monkeypatch):
    monkeypatch.setattr("tools.sql.query_tool.DatabaseManager", lambda: DummyDB([]))

    tool = SQLQueryTool()
    result = tool._execute("SELECT * FROM users WHERE id = 999")

    assert result.success is True
    assert result.data == []
    assert "未找到匹配记录" in result.message
