# SQL 生成剥离改造计划

> 状态同步（2026-04-02）：计划主体已落地，本文档保留为设计决策与验收依据。

## 1. 背景与目标

当前系统已具备以下能力：
- 短期记忆：/files/（StateBackend，会话内）
- 长期记忆：/memories/（StoreBackend，跨会话）
- 摘要压缩：SummarizationMiddleware（自动触发 + 手动触发）
- SQL 执行链：语义层检索 -> LLM 生成 SQL -> sql_inter 执行

本次改造核心目标：
1. 将“SQL 生成”从现有 sql_specialist 逻辑中剥离，独立为 SQL 生成 Agent。
2. 强制 SQL 生成输出满足 sql_inter 的入参契约，保证可执行。
3. 保留并复用现有语义层（缓存 + 向量检索）能力。
4. 解决工具与 LLM 迭代约 5 轮后上下文膨胀问题，避免上下文爆炸导致的性能和稳定性下降。
5. 摘要必须自动固定生成并注入上下文，不依赖人工触发。
6. 不同类型摘要必须进入对应 LLM 上下文槽位，避免关键信息遗忘。

---

## 2. 当前问题

1. SQL 生成与执行耦合在同一流程中，职责不清晰。
2. 生成结果虽然有兜底解析，但主路径仍依赖“文本提取”，契约约束不够强。
3. 执行失败后的自动修复机制不足，稳定性仍可提升。
4. 工具与 LLM 反复迭代时，历史 ToolMessage 与中间结果累积过快，约 5 轮后易出现上下文爆炸。

---

## 2.1 新增问题专项：上下文爆炸

### 现象

在“查询 -> 分析 -> 修复 -> 再查询”的循环任务中，工具输出和中间推理会在短时间内放大上下文体积。
常见表现：
1. 响应耗时明显上升。
2. LLM 开始忽略前文关键约束（例如 SQL 契约）。
3. 多轮后工具选择混乱，出现重复调用。

### 根因

1. 大体量工具输出原样回灌到对话历史。
2. 当前摘要压缩主要按消息数/token 阈值触发，但不区分“高价值上下文”和“低价值工具噪声”。
3. 缺少专门的“上下文治理角色”，无法在多轮循环中做结构化裁剪。

### 是否要新增 Agent

结论：优先复用现有中间件体系，新增 context_guardian 作为可选增强。

定位：
- 不替代 SummarizationMiddleware。
- 压缩策略改为“LLM 主导，规则兜底”：优先调用 LLM 生成结构化摘要，规则仅在 LLM 失败时启用。
- 与 sql_generator_agent 配合，优先保证 SQL 契约、表语义和最近错误上下文不丢失。

### 压缩策略决议（更新）

结论：规则手动压缩不足以稳定应对多轮工具-LLM循环，必须引入 LLM 摘要压缩。

执行原则：
1. LLM 摘要为主路径（默认开启）。
2. 规则压缩为降级路径（仅在 LLM 超时/异常时启用）。
3. 输出必须结构化，禁止自由散文，确保后续链路可消费。
4. 摘要必须自动触发，禁止人工手动触发作为主路径。
5. 摘要按类型路由到固定上下文槽位，不可混写。

### 自动固定摘要机制（新增）

触发方式（自动）：
1. 每次工具调用结束后自动触发轻量摘要（post-tool）。
2. 每次 SQL 执行失败后自动触发错误摘要（post-error）。
3. 每轮模型调用前自动聚合最近摘要并注入运行时 prompt（pre-model）。

固定输出（必须结构化）：
```json
{
  "task_goal": "...",
  "tool_decision": "为何选择该工具",
  "sql_reasoning": "为何生成该 SQL",
  "latest_valid_sql": "SELECT ...",
  "latest_error": "...",
  "schema_digest": "...",
  "next_action": "..."
}
```

上下文槽位（按类型路由）：
1. decision_summary：工具选择决策摘要（避免遗忘工具选择依据）——注入工具选择 LLM 的 prompt。
2. sql_summary：SQL 生成原因与最新可执行 SQL 的结果——注入 SQL 生成 LLM 的 prompt。
3. error_summary：最近错误与修复动作——注入 SQL 生成 LLM 的 prompt（放在 sql_summary 之后）。
4. schema_summary：表语义/字段关键摘要——注入 SQL 生成 LLM 的 prompt（放在 sql_summary 之前）。

注入规则：
1. pre-model 时按槽位拼接（decision -> sql -> error -> schema）。
2. 同槽位仅保留最近 N 条（建议 N=3），超出自动覆盖旧条目。
3. 严禁把原始大体量工具输出直接注入主上下文。

---

## 2.2 与现有体系融合约束（必须遵守）

1. 不改动主入口模式：保持 `SupervisorAgent.invoke()` + `create_react_agent` 运行方式不变。
2. SQL 生成剥离优先落在 `middleware/subagent.py`，避免修改 API 层协议。
3. 上下文治理优先复用 `MiddlewareManager` 链路（ToolAuth/ToolCache/ContextEditing）和现有 `SummarizationMiddleware`。
3.1 在不改入口的前提下，将 `SummarizationMiddleware` 升级为 LLM 摘要实现（保留规则兜底）。
3.2 摘要注入必须自动完成，禁止依赖 `summarize_conversation` 人工触发。
4. 新增能力默认内部启用，不新增对外 API 字段，不破坏现有前端调用。

---

## 2.3 新增问题专项：Human-in-the-Loop（HITL）

### 背景

当前 SQL 是由 LLM 直接生成后自动执行的，用户在执行前无法审查或修改 SQL。
对于数据敏感或查询逻辑复杂的场景，需要人工确认 SQL 后再执行，避免误查或结果异常。

### 设计决策

1. 使用 LangGraph 原生 `interrupt()` 机制，在 SQL 执行前暂停图执行。
2. 暂停时向前端返回待审查 SQL + schema 摘要，不阻塞其他会话线程。
3. 前端提交恢复指令（`Command(resume=...)`），携带以下三种决策之一：
   - `approve`：直接执行当前 SQL
   - `edit`：用户修改后的 SQL 重新走校验链路再执行
   - `reject`：放弃执行，向用户返回拒绝原因
4. HITL 通过配置开关 `enable_hitl`（默认 `false`）控制，可按环境或会话级别启用。
5. HITL 节点不修改 `SupervisorAgent.invoke()` 接口，通过 `thread_id` + checkpointer 实现状态暂停与恢复。

### interrupt() 触发点

触发位置：`_run_sql_specialist()` 中 `validate_sql_for_executor()` 通过后、`sql_inter` 调用前。

```text
generate_sql_via_agent()
  → validate_sql_for_executor()  ✓
  → [HITL interrupt]  ← 暂停，向前端推送 pending_sql
  → sql_inter 执行               ← 恢复后继续
```

### interrupt 载荷格式

```json
{
  "stage": "pre_execution",
  "sql_query": "SELECT ...",
  "schema_digest": "...",
  "task_goal": "..."
}
```

### resume 指令格式

```json
{ "decision": "approve" }
{ "decision": "edit", "edited_sql": "SELECT ... LIMIT 100" }
{ "decision": "reject", "reason": "查询范围过大" }
```

### 与现有体系融合约束

1. 需要 checkpointer（`MemorySaver` 或 Redis）已在 `SupervisorAgent` 中配置，HITL 才能正常暂停与恢复。
2. `edit` 决策时，修改后的 SQL 必须重新经过 `validate_sql_for_executor()`，不可绕过校验。
3. API 层 `api/routes/chat.py` 需支持接收 `Command` 类型的恢复请求（新增 resume 端点或在现有 chat 端点扩展）。
4. HITL 开关关闭时，流程与原有完全一致，不引入任何额外延迟。

---

## 3. 目标架构（改造后）

```text
用户任务
  -> Supervisor
    -> sql_specialist（编排器）
      1) 语义层检索 schema_context
      2) 委派 sql_generator_agent 生成 SQL（仅负责生成）
      3) auto_summary_router 自动生成并路由摘要到对应槽位
      4) validate_sql_for_executor
      5) [HITL interrupt] 若 enable_hitl=true：暂停等待人工审批
         - approve → 继续步骤 6
         - edit    → 重跑步骤 4 后继续步骤 6
         - reject  → 终止并返回拒绝原因
      6) sql_inter 执行
      7) 失败时 repair_sql_on_error 并重试（最多 1 次）
```

角色分工：
- sql_generator_agent：只做 SQL 生成，不做执行。
- sql_specialist：只做编排、校验、执行与重试。
- context_guardian（可选）：只做上下文治理，不做业务推理与工具执行。
- HITL 节点：只做执行前人工确认，不做生成与分析。

---

## 4. SQL 契约定义（必须满足）

生成阶段输出契约：
```json
{
  "sql_query": "SELECT ..."
}
```

执行前校验规则：
1. 必须存在 sql_query 字段，且类型为字符串。
2. 语句必须以 SELECT 或 WITH 开头。
3. 禁止危险关键字：INSERT/UPDATE/DELETE/DROP/CREATE/ALTER/TRUNCATE。
4. 若为 markdown 包裹或非 JSON，必须在进入执行前转换为契约格式。

---

## 5. 分阶段实施计划

### 阶段 A：能力拆分（P0）

目标：完成“生成”和“执行”职责隔离。

实施项：
1. 新增 sql 生成子 Agent 定义文件。
2. 在子 Agent 工厂中注册 sql_generator_agent。
3. 改造 SubAgentMiddleware：新增“生成委派 + 校验 + 修复重试”方法。
4. 重构 _run_sql_specialist：仅保留编排执行逻辑。

验收标准：
- SQL 进入 sql_inter 前均满足 {sql_query: str} 契约。
- sql_specialist 中不再直接承担 SQL 生成 prompt 逻辑。

### 阶段 B：稳定性增强（P1）

目标：提升执行成功率和可观测性。

实施项：
1. 增加一次失败修复重试。
2. 增加结构化日志：task_id、sql_query、error、retry_count。
3. 增加常见错误修复策略（字段不存在、表不存在、语法错误）。

验收标准：
- 执行失败时可自动重试一次并记录日志。
- 中文查询场景成功率明显提升。

### 阶段 C：运维与性能（P2）

目标：降低重复生成成本并增强可调试性。

实施项：
1. 增加 SQL 生成缓存（task_prompt + schema_context 维度）。
2. 增加 strict_sql_contract 开关。
3. 增加“只生成 SQL 不执行”的调试入口。

验收标准：
- 重复任务响应更快，问题定位更直接。
### 阶段 E：Human-in-the-Loop（P1）

目标：在 SQL 执行前引入人工审批环节，提升数据安全性与用户信任。

实施项：
1. 在 `middleware/subagent.py::_run_sql_specialist()` 中新增 `_hitl_interrupt()` 调用点。
2. 新增 `_hitl_interrupt(sql_query, schema_digest, task_goal) -> None` 函数（调用 LangGraph `interrupt()`）。
3. 新增 `_hitl_resume_handler(resume: dict, sql_query: str, schema_context: str, tool_map: dict) -> Optional[str]` 处理三种决策。
4. 在 `config/settings.py` 新增 `enable_hitl: bool = False` 与 `hitl_timeout_seconds: int = 300`。
5. 在 `api/routes/` 新增 `resume.py`，提供 `POST /resume` 端点支持 `Command(resume=...)` 恢复。
6. 新增测试 `tests/unit/test_middleware/test_hitl.py`。

验收标准：
- `enable_hitl=true` 时，执行前推送 `pending_sql` 到前端并暂停。
- `approve` / `edit` / `reject` 三条路径均可正常恢复。
- `edit` 路径下修改后的 SQL 强制经过 `validate_sql_for_executor()`。
- `enable_hitl=false` 时，流程与原有完全一致，零额外延迟。
- 新增 checkpointer 配置文档，说明 HITL 依赖持久化 checkpointer。
### 阶段 D：上下文治理专项（P0-P1 并行）

目标：控制 5 轮以上工具-LLM循环中的上下文体积，并保证关键信息不丢失。

实施项：
1. 新增 context_guardian Agent（轻量级，纯文本压缩职责）。
2. 定义上下文保留白名单：
  - 当前任务目标
  - 最近一次可执行 SQL
  - 最近一次 SQL 执行错误
  - 当前 schema_context 摘要
  - 最近 1~2 次高价值工具结果
3. 定义上下文清理黑名单：
  - 大型原始数据结果全集
  - 重复性日志
  - 历史多轮同类失败细节（仅保留最新一轮）
4. 在每轮工具调用后增加“压缩闸门”：
  - 达到阈值时先压缩再进入下一轮模型调用
  - 压缩结果写入 /files/context_snapshot_{thread_id}.md 供可观测与回放
  - 压缩摘要自动写入对应上下文槽位（decision/sql/error/schema）
5. 升级 SummarizationMiddleware 触发策略：
  - 从“仅看 token/消息数”升级为“阈值 + 内容类型”双触发
  - 触发后优先调用 LLM 输出结构化摘要（JSON schema）
  - LLM 失败时自动降级规则压缩，不中断主流程
  - 对 ToolMessage 采用更激进压缩策略，对用户意图与最终结论采用保守策略
  - pre-model 自动注入摘要槽位，确保工具选择决策与 SQL 生成原因持续可见

验收标准：
1. 连续 8~10 轮工具-LLM循环不发生上下文爆炸。
2. SQL 契约信息在压缩后仍保持完整。
3. 平均响应时延和 token 消耗显著下降。
4. 无需人工触发摘要工具，系统可自动稳定运行。
5. 工具选择决策与 SQL 生成原因在多轮后不遗忘。

---

## 6. 执行清单（可打勾）

### P0 必做
- [ ] 新建 agents/subagents/sql_generator_agent.py
- [ ] 更新 agents/subagents/__init__.py 导出 create_sql_generator_agent
- [ ] 在 agents/supervisor.py 初始化并挂接 sql_generator_agent（内部使用）
- [ ] 在 middleware/subagent.py 新增 generate_sql_via_agent()
- [ ] 在 middleware/subagent.py 新增 validate_sql_for_executor()
- [ ] 在 middleware/subagent.py 新增 repair_sql_on_error()
- [ ] 重构 middleware/subagent.py::_run_sql_specialist()
- [ ] 新增 tests/unit/test_agents/test_sql_generator.py
- [ ] 新增 tests/unit/test_middleware/test_sql_execution_pipeline.py
- [ ] 新建 agents/subagents/context_guardian_agent.py
- [ ] 在 agents/subagents/__init__.py 导出 create_context_guardian_agent
- [ ] 在 middleware/subagent.py 内部注册 context_guardian（内部调用，不暴露委派工具）
- [ ] 在 middleware/subagent.py 增加 context_compact_gate()（每轮调用后执行）
- [ ] 在 middleware/subagent.py 实现 `_llm_summarize_context()`（主路径）
- [ ] 在 middleware/subagent.py 实现规则兜底 `_rule_summarize_fallback()`
- [ ] 在 middleware/subagent.py 实现 `_route_summary_to_slots()`（decision/sql/error/schema）
- [ ] 在 middleware/subagent.py 实现 `_compose_runtime_prompt_from_slots()`（pre-model 自动注入）
- [ ] 在 middleware/subagent.py 实现高价值上下文白名单保留规则
- [ ] 在 middleware/subagent.py 实现低价值工具输出裁剪规则
- [ ] 新增 tests/unit/test_middleware/test_context_compaction.py

### P0 按文件逐步实施顺序（函数级）

> 目标：先打通“SQL 生成剥离”主链路，再接入“上下文治理”，最后补测试。

#### 第 1 步：新增 SQL 生成 Agent 定义

文件：`agents/subagents/sql_generator_agent.py`

新增内容：
1. `SQL_GENERATOR_SUBAGENT`（SubAgent 实例）
2. `create_sql_generator_agent(tools=None) -> SubAgent`

实现要求：
1. 默认工具仅 `llm_skill`（可选 `table_metadata`）
2. system_prompt 明确只返回 `{"sql_query":"..."}` 契约
3. 明确禁止执行 SQL、禁止做数据分析与可视化

#### 第 2 步：新增上下文治理 Agent 定义

文件：`agents/subagents/context_guardian_agent.py`

新增内容：
1. `CONTEXT_GUARDIAN_SUBAGENT`（SubAgent 实例）
2. `create_context_guardian_agent(tools=None) -> SubAgent`

实现要求：
1. 仅做上下文压缩与保真保留
2. 输出结构建议为：`{"compact_context":"...","kept_items":[...],"dropped_items":[...]}`
3. 禁止调用业务执行工具（sql_inter/python_inter/fig_inter）

#### 第 3 步：更新子 Agent 导出入口

文件：`agents/subagents/__init__.py`

修改函数/符号：
1. 新增导入 `create_sql_generator_agent`
2. 新增导入 `create_context_guardian_agent`
3. 更新 `__all__`

#### 第 4 步：在 Supervisor 初始化内部 Agent

文件：`agents/supervisor.py`

优先修改函数：
1. `_init_subagents()`

具体改动：
1. 初始化 `self.sql_generator_agent = create_sql_generator_agent()`
2. 仅将 sql_generator 作为内部能力传入 SubAgentMiddleware（例如构造参数或 setter）
3. context_guardian 不在 Supervisor 暴露为可委派子 Agent，避免新增外部工具面
4. 保持现有 `sql_agent/data_analysis_agent/visualization_agent` 不受影响

#### 第 5 步：改造 SubAgentMiddleware 的 SQL 主链路（第一阶段）

文件：`middleware/subagent.py`

优先新增函数：
1. `generate_sql_via_agent(task_prompt, schema_context, tool_map) -> Optional[str]`
2. `validate_sql_for_executor(sql_query: str) -> tuple[bool, str]`
3. `repair_sql_on_error(sql_query: str, error_text: str, schema_context: str, tool_map) -> Optional[str]`

优先改造函数：
1. `_run_sql_specialist()`

改造顺序：
1. 保留 `_collect_table_context()` 作为入口（语义层不动）
2. 将 `_generate_sql_with_llm()` 主路径替换为 `generate_sql_via_agent()`
3. 在执行前调用 `validate_sql_for_executor()`
4. 若 `settings.enable_hitl=True`，调用 `_hitl_interrupt(sql_query, schema_digest, task_goal)` 暂停等待人工决策
5. 执行 `sql_inter`
6. 失败时调用 `repair_sql_on_error()` 并重试 1 次

#### 第 5.5 步（P1）：接入 HITL 中断与恢复

文件：`middleware/subagent.py`、`api/routes/resume.py`（新建）、`config/settings.py`

新增内容：

1. `config/settings.py`：新增字段
   ```python
   enable_hitl: bool = False
   hitl_timeout_seconds: int = 300
   ```

2. `middleware/subagent.py`：新增 `_hitl_interrupt(sql_query, schema_digest, task_goal) -> None`
   - 仅在 `self.settings.enable_hitl` 为 `True` 时执行，否则直接返回
   - 内部调用：`from langgraph.types import interrupt; interrupt({"stage": "pre_execution", "sql_query": sql_query, "schema_digest": schema_digest, "task_goal": task_goal})`

3. `middleware/subagent.py`：新增 `_hitl_resume_handler(resume: dict, sql_query: str, schema_context: str, tool_map: dict) -> Optional[str]`
   - `decision == "approve"` → 返回原始 `sql_query`
   - `decision == "edit"` → 取 `resume["edited_sql"]`，重调 `validate_sql_for_executor()`，通过则返回，否则抛出异常
   - `decision == "reject"` → 返回 `None`，调用方向用户返回 `resume.get("reason", "用户拒绝执行")`

4. `api/routes/resume.py`：新增 `POST /resume` 端点
   - 请求体：`{"thread_id": "...", "decision": "approve|edit|reject", "edited_sql": "...", "reason": "..."}`
   - 调用：`supervisor.graph.invoke(Command(resume=payload), config={"configurable": {"thread_id": thread_id}})`
   - 返回恢复后响应或终止状态

实现注意事项：
1. `interrupt()` 需要 checkpointer 已配置并持久化（`MemorySaver` 仅适用于开发环境，生产需 Redis/Postgres checkpointer）。
2. 恢复时的 `thread_id` 必须与暂停时一致，前端须持久保存。
3. `edit` 路径下的修改 SQL 不可绕过 `validate_sql_for_executor()`，防止注入危险语句。
4. HITL 超时处理：超时后自动以 `reject` 方式终止，防止会话永久挂起。

#### 第 6 步：改造 SubAgentMiddleware 的上下文治理链路（第二阶段）

文件：`middleware/subagent.py`

新增函数：
1. `context_compact_gate(task_prompt: str, context: dict, tool_outputs: list) -> dict`
2. `_llm_summarize_context(task_prompt: str, context: dict, tool_outputs: list) -> dict`
3. `_rule_summarize_fallback(task_prompt: str, context: dict, tool_outputs: list) -> dict`
4. `_route_summary_to_slots(summary: dict, context: dict) -> dict`
5. `_compose_runtime_prompt_from_slots(context: dict) -> str`
6. `_build_context_keep_whitelist(...) -> dict`
7. `_build_context_drop_blacklist(...) -> dict`

接入点：
1. 在 `_run_sql_specialist()` 中“生成 SQL 前”和“执行失败重试前”各调用一次 `context_compact_gate()`
2. 压缩结果写入 `/files/context_snapshot_{thread_id}.md`

补充说明：
1. `thread_id` 从 `delegate_to_*` 的 context 中读取；缺失时使用 `default`
2. 先执行 LLM 摘要压缩（结构化 JSON），失败时走规则兜底
3. `llm_skill` 调用建议启用 `json_mode=True` + `output_schema`
4. 摘要输出必须包含字段：`task_goal`、`tool_decision`、`sql_reasoning`、`latest_valid_sql`、`latest_error`、`schema_digest`、`next_action`
5. 摘要路由必须自动执行，禁止把“手动摘要工具”作为主链路依赖

#### 第 7 步：补齐 SQL 生成单元测试

文件：`tests/unit/test_agents/test_sql_generator.py`

新增测试用例：
1. `test_sql_generator_returns_contract_json()`
2. `test_sql_generator_rejects_non_select_statement()`
3. `test_sql_generator_handles_markdown_wrapped_output()`

#### 第 8 步：补齐 SQL 执行链路测试

文件：`tests/unit/test_middleware/test_sql_execution_pipeline.py`

新增测试用例：
1. `test_pipeline_generate_validate_execute_success()`
2. `test_pipeline_execute_fail_then_repair_success()`
3. `test_pipeline_rejects_invalid_sql_contract()`

#### 第 9 步：补齐上下文压缩测试

文件：`tests/unit/test_middleware/test_context_compaction.py`

新增测试用例：
1. `test_context_compaction_keeps_sql_contract_fields()`
2. `test_context_compaction_drops_large_tool_payloads()`
3. `test_context_snapshot_written_to_files_path()`
4. `test_context_compaction_prefers_llm_summary()`
5. `test_context_compaction_fallback_when_llm_fails()`
6. `test_summary_auto_routed_to_slots()`
7. `test_pre_model_prompt_includes_slot_summaries()`

#### 第 10 步：联调与回归顺序

执行顺序：
1. 先跑 `test_sql_generator.py`
2. 再跑 `test_sql_execution_pipeline.py`
3. 最后跑 `test_context_compaction.py`
4. 进行一次端到端手测：连续 8~10 轮 SQL 任务，确认无上下文爆炸

联调检查点（与现有体系绑定）：
1. `agents/supervisor.py` 的 `middleware_order` 统计仍可正常输出。
2. `summarization_middleware.add_message()` 在用户与助手消息两处调用仍生效。
3. `FilesystemMiddleware` 的 `/files/` 快照文件可被 `read_file` 直接读取。

### P1 应做
- [ ] 增加执行失败自动重试（最多 1 次）
- [ ] 增加 SQL 生成/执行结构化日志
- [ ] 增加常见 SQL 错误修复规则
- [ ] 升级 SummarizationMiddleware 为“阈值 + 内容类型”双触发 + LLM 主导摘要
- [ ] 增加 /files/context_snapshot_{thread_id}.md 快照落盘与回放测试
- [ ] 增加“自动摘要触发覆盖率”指标（目标 100%）- [ ] 在 config/settings.py 新增 enable_hitl（默认 false）与 hitl_timeout_seconds（默认 300）
- [ ] 在 middleware/subagent.py 新增 `_hitl_interrupt()` 与 `_hitl_resume_handler()`
- [ ] 在 api/routes/ 新增 resume.py，提供 POST /resume 端点，支持 Command(resume=...) 恢复
- [ ] 新增 tests/unit/test_middleware/test_hitl.py（approve / edit / reject 三路径测试）
- [ ] 补充 checkpointer 配置文档（HITL 依赖持久化 checkpointer）
### P2 可做
- [ ] 增加 SQL 生成缓存
- [ ] 增加 strict_sql_contract 配置项
- [ ] 增加“只生成 SQL”调试工具
- [ ] 增加 context_compaction_level 配置（conservative/balanced/aggressive）
- [ ] 增加上下文压缩指标面板（压缩率、保留命中率、失败回放率）

---

## 7. 风险与回滚

主要风险：
1. Agent 拆分后链路变长，初期可能带来少量延迟。
2. 校验规则过严可能导致误拦截。
3. 上下文压缩过强可能导致关键线索丢失。

回滚策略：
1. 保留旧 _generate_sql_with_llm 路径，挂在 feature flag 下。
2. 新链路灰度发布，按任务类型逐步切换。
3. context_guardian 与 context_compact_gate 均通过开关控制，可一键降级回现有策略。

---

## 8. Definition of Done

满足以下条件视为完成：
1. 所有 SQL 任务在执行前均满足 sql_inter 入参契约。
2. 生成职责与执行职责彻底分离。
3. 执行失败有自动修复重试，且可观测。
4. 不破坏现有短期/长期记忆与摘要能力。
5. 单元测试和集成测试覆盖关键路径并通过。
6. 连续 8 轮以上工具-LLM迭代保持稳定，无上下文爆炸。
7. 压缩后 SQL 生成成功率与执行成功率不下降。
8. 无人工触发前提下，摘要自动生成并注入上下文槽位。
9. 多轮后仍可复现工具选择决策与 SQL 生成原因。
10. `enable_hitl=true` 时，SQL 执行前必定暂停并等待人工确认；`approve` / `edit` / `reject` 三路径均可正常完成会话。
11. `edit` 路径下的修改 SQL 强制经过契约校验，不可绕过。
12. `enable_hitl=false`（默认）时，全链路行为与改造前完全一致，零额外延迟。
