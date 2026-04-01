"""pytest 配置"""
import pytest
import os
import sys
from fastapi.testclient import TestClient

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


@pytest.fixture
def mock_settings():
    """模拟配置"""
    from config.settings import Settings
    return Settings(
        debug=True,
        database={
            "host": "localhost",
            "port": 3306,
            "user": "root",
            "password": "test",
            "database": "test_db"
        }
    )


@pytest.fixture
def test_client():
    """FastAPI test client."""
    from api.main import app

    with TestClient(app) as client:
        yield client
