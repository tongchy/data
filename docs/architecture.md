# 架构文档

> 同步日期：2026-04-02

## 1. 总体结构

```text
graph.py:data_agent
  -> SupervisorAgent
    -> create_react_agent(checkpointer=memory|sqlite)
    -> middleware chains
    -> delegate tools
```

分层说明：
- 编排层：`agents/supervisor.py`
- 中间件层：`middleware/*`
- 执行工具层：`tools/*`
- 存储层：`filesystem/backends/*`
- 基础设施：MySQL + SiliconFlow + LangGraph

## 2. 关键运行路径

### 2.1 聊天路径

```text
POST /api/chat
  -> api/routes/chat.py:get_agent()
  -> SupervisorAgent.invoke()
  -> runtime create_react_agent
  -> 返回 content
```

### 2.2 HITL 恢复路径

```text
POST /api/resume
  -> api/routes/resume.py
  -> SupervisorAgent.resume(thread_id, payload)
  -> graph.ainvoke(Command(resume=payload))
```

## 3. SQL 子链路（最新）

```text
SubAgentMiddleware._run_sql_specialist
  1) context_compact_gate
  2) _collect_table_context(语义层)
  3) generate_sql_via_agent
  4) validate_sql_for_executor
  5) _hitl_interrupt(可选)
  6) sql_inter
  7) repair_sql_on_error(失败时一次重试)
```

## 4. 语义层与缓存

- 首次构建：`_build_semantic_layer`
- 向量模型：`BAAI/bge-m3`
- 缓存字段：`self._semantic_layer`
- 刷新入口：`rebuild_data_semantic_layer`

## 5. 上下文治理

- 摘要主路径：`_llm_summarize_context`
- 兜底路径：`_rule_summarize_fallback`
- 路由槽位：`decision/schema/sql/error`
- 单槽位保留：最近 3 条
- 快照文件：`/files/context_snapshot_{thread_id}.md`

## 6. Checkpointer 策略

`graph.py:get_checkpointer()`：
- `checkpointer_backend=memory` -> `MemorySaver`
- `checkpointer_backend=sqlite` -> `SqliteSaver`
- sqlite 不可用时自动回退到 `MemorySaver`

## 7. API 路由清单

- `GET /api/health`
- `GET /api/ready`
- `GET /api/live`
- `POST /api/chat`
- `POST /api/chat/stream`
- `DELETE /api/chat/{thread_id}`
- `POST /api/resume`
- `GET /api/tools`
- `GET /api/tools/{category}`
