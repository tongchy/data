"""TableMetadataTool 单元测试"""

from tools.loader.table_metadata import TableMetadataTool


class FakeDatabaseManager:
    def __init__(self, rows):
        self._rows = rows

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute_query(self, query, params):
        return self._rows


def test_empty_table_name_returns_error():
    tool = TableMetadataTool()
    result = tool._execute(table_name="")
    assert result.success is False
    assert "未提供表名" in result.message


def test_table_not_found_returns_error(monkeypatch):
    monkeypatch.setattr(
        "database.connection.DatabaseManager",
        lambda: FakeDatabaseManager([]),
    )
    tool = TableMetadataTool()
    result = tool._execute(table_name="missing_table")
    assert result.success is False
    assert "missing_table" in result.message


def test_table_metadata_returns_stats(monkeypatch):
    rows = [
        {
            "TABLE_NAME": "orders",
            "TABLE_ROWS": 12345,
            "DATA_LENGTH": 2048,
            "INDEX_LENGTH": 1024,
            "UPDATE_TIME": "2026-04-01 10:00:00",
        }
    ]
    monkeypatch.setattr(
        "database.connection.DatabaseManager",
        lambda: FakeDatabaseManager(rows),
    )
    tool = TableMetadataTool()
    result = tool._execute(table_name="orders")
    assert result.success is True
    assert result.data["TABLE_NAME"] == "orders"
    assert "12,345" in result.message
    assert "2.00 KB" in result.message
    assert "1.00 KB" in result.message


def test_fmt_bytes_handles_invalid_input():
    assert TableMetadataTool._fmt_bytes(None) == "0 B"
    assert TableMetadataTool._fmt_bytes("abc") == "N/A"