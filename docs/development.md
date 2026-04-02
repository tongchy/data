# 开发指南

> 同步日期：2026-04-02

## 1. 环境准备

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e ".[dev]"
cp .env.example .env
```

## 2. 关键配置

`.env` 常用项：

```env
# 模型
MODEL_API_KEY=
MODEL_BASE_URL=https://api.siliconflow.cn/v1
MODEL_MODEL_NAME=deepseek-ai/DeepSeek-V3

# 数据库
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=
DB_DATABASE=alarm

# HITL / Checkpointer
ENABLE_HITL=false
HITL_TIMEOUT_SECONDS=300
CHECKPOINTER_BACKEND=memory
CHECKPOINTER_PATH=./.langgraph_checkpoints.sqlite

# 日志
LOG_LEVEL=INFO
```

## 3. 运行方式

### 3.1 LangGraph 调试（推荐）

```bash
langgraph dev
```

### 3.2 FastAPI

```bash
python scripts/run_api.py
# 或
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

## 4. 测试命令

```bash
pytest
```

常用回归：

```bash
pytest tests/unit/test_agents/test_graph_checkpointer.py tests/unit/test_agents/test_supervisor_resume.py -q
pytest tests/unit/test_middleware/test_hitl.py -q
pytest tests/unit/test_middleware/test_context_compaction.py -q
pytest tests/unit/test_middleware/test_sql_execution_pipeline.py -q
pytest tests/integration/test_api.py -q
```

## 5. 调试要点

- SQL 链路入口：`SubAgentMiddleware._run_sql_specialist`
- HITL 恢复入口：`SupervisorAgent.resume`
- API 恢复路由：`POST /api/resume`
- checkpointer 创建：`graph.py:get_checkpointer`

## 6. 文档维护建议

每次涉及以下改动后请同步 `docs/`：
- 新增或变更 API 路由
- 变更 SQL 校验/执行策略
- 变更上下文摘要策略
- 变更 checkpointer 与恢复行为
