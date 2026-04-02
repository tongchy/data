# 架构文档

## 系统架构

Data Analysis Agent 2.0 采用分层架构设计，各层职责清晰，便于维护和扩展。

# 架构文档

> 本文档描述 Data Analysis Agent 2.0 的真实运行时架构。  
> 入口：`langgraph dev` 加载 `graph.py::data_agent`

---

## 总体分层

```
┌──────────────────────────────────────────────────────┐
│            Supervisor Agent（主 Agent）               │
│  create_react_agent + 14 个工具                      │
│  文件系统(4) | TODO(4) | 子Agent派发(3+2) | 会话(2)  │
└──────────────┬───────────────────────────────────────┘
               │ delegate_to_*
┌──────────────▼───────────────────────────────────────┐
│            SubAgentMiddleware（中间件调度层）          │
│  sql_specialist  │  data_analyst  │  viz_specialist  │
│                  │                │                  │
│  ┌───────────────▼──────────────┐ │                  │
│  │     数据语义层（向量缓存）    │ │                  │
│  │  _build_semantic_layer()     │ │                  │
│  │  BAAI/bge-m3 向量检索        │ │                  │
│  └───────────────┬──────────────┘ │                  │
│                  ▼                │                  │
│  sql_inter / extract_data /      python_inter /      │
│  llm_skill / table_metadata      fig_inter /         │
│                                  llm_skill           │
└──────────────────────────────────────────────────────┘
               │
┌──────────────▼───────────────────────────────────────┐
│            后端层（Backend Layer）                    │
│  StateBackend（/files/，会话内内存）                  │
│  StoreBackend（/memories/，LangGraph Store 跨会话）   │
└──────────────────────────────────────────────────────┘
               │
┌──────────────▼───────────────────────────────────────┐
│            基础设施层                                 │
│  MySQL（数据存储）  SiliconFlow（DeepSeek-V3 / bge-m3）│
│  LangSmith（链路追踪，可选）                          │
└──────────────────────────────────────────────────────┘
```

---

## Supervisor Agent

**文件**: `agents/supervisor.py`，**图入口**: `graph.py`

- 使用 `langgraph.prebuilt.create_react_agent` 构建
- 全部中间件工具在初始化时注入（文件系统、TODO、子Agent派发）
- `invoke()` 配置 `recursion_limit: 8`，防止无限递归
- 单例模式：`get_supervisor_agent()` 缓存实例，`graph.py` 直接返回 `agent.agent`

**提示词设计**：强制规则块置于最顶部，防止 LLM 输出文字描述代替工具调用。

---

## 中间件层

### FilesystemMiddleware

**文件**: `middleware/filesystem.py`  
提供 `ls / read_file / write_file / edit_file` 四个工具。  
路由：`/files/*` → `StateBackend`（内存）；`/memories/*` → `StoreBackend`（持久化）

### TodoListMiddleware

**文件**: `middleware/todo_list.py`  
提供 `create_todo / update_todo / list_todos / get_todo` 四个工具，任务状态：pending / in_progress / completed / failed

### SubAgentMiddleware

**文件**: `middleware/subagent.py`

核心执行管道（sql_specialist）：
```
任务 → 数据语义层检索 → LLM 生成 SQL → sql_inter 执行 → 错误判断 → 返回
```

**数据语义层**：首次调用时构建，扫全库表名 + 列定义 + 样例 + metadata，
通过 `BAAI/bge-m3` 向量化存入 `self._semantic_layer`，后续直接读缓存。
检索优先级：① 余弦相似度向量检索 → ② 英文 token 精确匹配 → ③ 前 top-k 兜底

### SummarizationMiddleware / ContextEditingMiddleware

**文件**: `memory/summarization.py`、`middleware/context_edit.py`  
自动压缩历史对话；自动清理旧工具结果，保持上下文可控。

---

## 工具层（双层）

### 主 Agent 可见工具（14 个，高抽象层）

| 类别 | 工具 |
|------|------|
| 文件系统 | `ls` `read_file` `write_file` `edit_file` |
| 任务规划 | `create_todo` `update_todo` `list_todos` `get_todo` |
| 子Agent派发 | `delegate_to_sql_specialist` `delegate_to_data_analyst` `delegate_to_visualization_specialist` |
| 语义管理 | `rebuild_data_semantic_layer` |
| 状态/派发 | `check_task_status` `summarize_conversation` / `get_conversation_context` |

### 子 Agent 内部工具（6 个，实现层）

| 工具名 | 输入 | 说明 |
|--------|------|------|
| `sql_inter` | `sql_query: str` | 执行 MySQL SELECT，返回结果列表 |
| `extract_data` | `sql_query: str, df_name: str` | 提取数据到 pandas DataFrame |
| `python_inter` | `py_code: str` | 执行 Python 代码（eval/exec） |
| `fig_inter` | `py_code: str, fname: str` | 执行绘图代码并保存 PNG |
| `llm_skill` | `prompt: str, json_mode?: bool` | LLM 文本推理 |
| `table_metadata` | `table_name: str` | 查询 INFORMATION_SCHEMA 统计信息 |

分层原因：主 Agent 只看到 14 个高抽象工具，节省约 70% 的工具描述 token；
子 Agent 通过直接执行管道规避 SiliconFlow 20015 错误（禁止多轮 ToolMessage 链）。

---

## 数据库访问

```python
from database.connection import DatabaseManager

with DatabaseManager() as db:
    results = db.execute_query("SELECT * FROM device LIMIT 10")
```

---

## 扩展点

| 扩展 | 方法 |
|------|------|
| 添加子 Agent | 继承 `SubAgent`，在 `supervisor.py::_init_subagents()` 注册 |
| 添加主 Agent 工具 | 继承 `BaseCustomTool`，注册到 `registry`，在 `supervisor.py` 的工具列表中添加 |
| 添加 API 路由 | 在 `api/routes/` 添加新路由文件 |
| 切换 LLM | 修改 `.env` 中 `MODEL_*` 变量 |
| 刷新语义层 | 主 Agent 调用 `rebuild_data_semantic_layer` 工具 |
