# Deep Agents 架构文档

> 同步日期：2026-04-02（对齐当前 main 分支代码）

## 1. 核心角色

- `SupervisorAgent`：统一编排入口，负责工具调用、中间件串联、线程状态管理。
- `SubAgentMiddleware`：负责子 Agent 派发与 SQL 专线执行。
- `sql_generator_agent`：仅负责 SQL 生成（结构化输出契约）。
- `context_guardian_agent`：上下文治理角色（通过摘要槽位提供运行时提示）。

## 2. 组件关系

```text
Supervisor
  -> FilesystemMiddleware
  -> TodoListMiddleware
  -> SubAgentMiddleware
  -> MiddlewareManager(ToolAuth/ToolCache/ContextEditing)
  -> ToolRuntimeMiddleware
  -> SummarizationMiddleware
```

## 3. 子 Agent 工具分层

主 Agent 可见（高抽象）：
- `delegate_to_sql_specialist`
- `delegate_to_data_analyst`
- `delegate_to_visualization_specialist`
- `check_task_status`
- `rebuild_data_semantic_layer`

子 Agent 内部（实现层）：
- `sql_inter`
- `extract_data`
- `python_inter`
- `fig_inter`
- `llm_skill`
- `table_metadata`

## 4. SQL 执行治理（重点）

```text
generate_sql_via_agent -> validate_sql_for_executor -> (HITL) -> sql_inter
                    \-> repair_sql_on_error(失败后一次)
```

约束：
- 仅允许 `SELECT/WITH`
- 强制拦截写操作关键字

## 5. 上下文爆炸治理

已实现机制：
- `context_compact_gate`
- `_llm_summarize_context`（主路径）
- `_rule_summarize_fallback`（降级）
- `_route_summary_to_slots`（decision/sql/error/schema）
- `_compose_runtime_prompt_from_slots`（槽位注入）

## 6. HITL 与恢复

- 中断点：SQL 执行前 `_hitl_interrupt`
- 决策处理：`_hitl_resume_handler`
- API：`POST /api/resume`
- 图恢复：`SupervisorAgent.resume()` -> `Command(resume=payload)`

## 7. 持久化与恢复前提

- 短期文件：`/files/*`
- 长期记忆：`/memories/*`
- 中断恢复依赖 checkpointer：
  - memory: 默认
  - sqlite: 可配置，失败自动回退 memory
