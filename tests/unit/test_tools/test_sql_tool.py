"""SQL 查询工具测试"""
import pytest
from tools.sql.query_tool import SQLQueryTool


class TestSQLQueryTool:
    """测试 SQL 查询工具"""
    
    def test_is_safe_query_select(self):
        """测试安全的 SELECT 查询"""
        tool = SQLQueryTool()
        assert tool._is_safe_query("SELECT * FROM users") is True
        assert tool._is_safe_query("select * from users") is True
        assert tool._is_safe_query("SELECT id, name FROM users WHERE id = 1") is True
    
    def test_is_safe_query_forbidden(self):
        """测试禁止的操作"""
        tool = SQLQueryTool()
        assert tool._is_safe_query("DELETE FROM users") is False
        assert tool._is_safe_query("INSERT INTO users VALUES (1)") is False
        assert tool._is_safe_query("UPDATE users SET name = 'test'") is False
        assert tool._is_safe_query("DROP TABLE users") is False
