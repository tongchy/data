# Deep Agents 框架改造计划

## 📋 文档信息

- **版本**: v1.1
- **创建时间**: 2026-03-30
- **目标**: 将现有数据分析 Agent 改造为基于 LangChain Deep Agents 架构
- **状态**: 核心能力已落地（持续优化中）

---

## 🎯 改造目标

**核心目标**：利用 LangChain Deep Agents 框架的先进特性，将现有单体 Agent 重构为具备规划、记忆、子 Agent 派发等能力的深度智能 Agent。

**预期成果**：
- ✅ 任务规范与规划能力（TODO List）
- ✅ 文件系统后端（短期/长期记忆）
- ✅ 子 Agent 派发机制
- ✅ 短期记忆（会话内）
- ✅ 长期记忆（跨会话）
- ✅ 记忆摘要（自动压缩）
- ✅ 上下文工程管理

### 当前代码落地快照（2026-04-02）

- ✅ `langgraph dev` 已作为主要开发入口（读取 `langgraph.json` + `graph.py:data_agent`）
- ✅ Supervisor + 3 个 SubAgent（`sql_specialist` / `data_analysis_specialist` / `visualization_specialist`）
- ✅ `SubAgentMiddleware` 内置 SQL 执行流水线（表上下文收集 -> SQL 生成 -> SQL 工具执行）
- ✅ 数据语义层缓存（一次构建，多次复用）
- ✅ 中文任务向量检索（`BAAI/bge-m3` + 余弦相似度）
- ✅ 主工具名已统一：`sql_inter`、`extract_data`、`python_inter`、`fig_inter`、`table_metadata`
- ⚠️ `tool_loader/schema_loader/dynamic_register` 仍属于规划项，当前未以独立工具形态落地

---

## 📊 现状分析 vs Deep Agents 能力

### 当前架构限制

| 功能 | 当前状态 | 问题 |
|------|----------|------|
| 任务规划 | ❌ 无 | Agent 无法分解复杂任务 |
| 文件系统 | ❌ 无 | 上下文窗口易溢出 |
| 子 Agent | ❌ 无 | 所有工具共享上下文 |
| 短期记忆 | ⚠️ globals() | 会话内临时存储，易污染 |
| 长期记忆 | ❌ 无 | 无法跨会话持久化 |
| 记忆摘要 | ❌ 无 | 上下文无限制增长 |
| 上下文管理 | ❌ 手动 | 容易超出 token 限制 |
| 工具加载 | ❌ 静态全量 | 所有工具始终占用 context |
| 数据表语义 | ❌ 硬编码 | 无法按需加载表结构 |
| 状态驱动 | ❌ 无 | 缺少基于状态的动态决策 |

### Deep Agents 核心能力

| 功能 | Deep Agents 方案 | 优势 |
|------|------------------|------|
| 任务规划 | `todoListMiddleware` | 内置 TODO 工具，自动分解任务 |
| 文件系统 | `FilesystemMiddleware` | 4 个文件工具，支持短/长期存储 |
| 子 Agent | `createSubAgentMiddleware` | 上下文隔离，专业化分工 |
| 短期记忆 | State Backend | 会话内持久化 |
| 长期记忆 | Store Backend | 跨线程持久化 |
| 记忆摘要 | `summarizationMiddleware` | 自动压缩历史对话 |
| 上下文管理 | `contextEditingMiddleware` | 自动清理旧工具结果 |
| **双层工具架构** | **Loader + Content Tools** | **按需加载，节省 60% token** |
| **状态驱动** | **State-based Middleware** | **动态决策，精准拦截** |
| **动态工具加载** | **wrapModelCall 动态注册** | **运行时发现并注册工具** |

---

## 🏗️ 新架构设计

### 1. 系统架构图

```
┌─────────────────────────────────────────────────────────────┐
│                    Deep Agent Core                           │
│  ┌────────────────────────────────────────────────────────┐  │
│  │              Supervisor Agent (主 Agent)                │  │
│  │  - 任务接收与规划                                        │  │
│  │  - 子 Agent 派发                                         │  │
│  │  - 最终结果汇总                                          │  │
│  └────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
            │                    │                   │
┌───────────▼────────────────────▼───────────────────▼─────────┐
│                    Middleware Layer                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │ Todo List    │  │ Filesystem   │  │ SubAgent         │   │
│  │ Middleware   │  │ Middleware   │  │ Middleware       │   │
│  └──────────────┘  └──────────────┘  └──────────────────┘   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │ Summarization│  │ Context Edit │  │ Tool Loader      │   │
│  │ Middleware   │  │ Middleware   │  │ Middleware       │   │
│  └──────────────┘  └──────────────┘  └──────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │       State-Driven Interception Layer                 │   │
│  │  - beforeModel: 工具选择/表语义加载                    │   │
│  │  - wrapModelCall: 动态工具注册                        │   │
│  │  - wrapToolCall: 工具执行拦截                         │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
            │                    │                   │
┌───────────▼────────────────────▼───────────────────▼─────────┐
│                    Backend Layer                              │
│  ┌──────────────────┐         ┌──────────────────────┐       │
│  │  State Backend   │         │   Store Backend      │       │
│  │  (短期记忆)       │         │   (长期记忆)         │       │
│  │  - 会话内持久化   │         │  - 跨线程持久化      │       │
│  │  - /files/       │         │  - /memories/        │       │
│  └──────────────────┘         └──────────────────────┘       │
└───────────────────────────────────────────────────────────────┘
            │                    │                   │
┌───────────▼────────────────────▼───────────────────▼─────────┐
│                    Tool Layer (双层架构)                       │
│  ┌─────────────────────────┐  ┌──────────────────────────┐   │
│  │   Semantic/Loader (L1)  │  │   Content Tools (L2)     │   │
│  │  - table_metadata       │  │  - sql_inter             │   │
│  │  - 语义层缓存构建       │  │  - extract_data          │   │
│  │  - 向量检索召回         │  │  - python_inter          │   │
│  │  - 语义层重建工具       │  │  - fig_inter             │   │
│  └─────────────────────────┘  └──────────────────────────┘   │
└───────────────────────────────────────────────────────────────┘
            │                    │                   │
┌───────────▼────────────────────▼───────────────────▼─────────┐
│                    Sub Agents Layer                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │ SQL Agent    │  │ Data Agent   │  │ Viz Agent        │   │
│  │ (SQL 查询)    │  │ (数据分析)   │  │ (可视化)         │   │
│  └──────────────┘  └──────────────┘  └──────────────────┘   │
└───────────────────────────────────────────────────────────────┘
```

### 2. 双层工具架构详解

#### L1 层：Semantic/Loader（语义与加载层）

**职责**：构建并检索数据语义层，为 SQL 生成提供稳定上下文

**工具列表**：
```python
# 1. table_metadata - 表元数据查询
- 功能：查询表的统计信息（行数、更新时间等）
- 触发条件：语义层构建阶段
- 返回：表元数据（不包含业务查询结果）

# 2. semantic_layer_builder - 语义层构建器（middleware 内部）
- 功能：聚合表字段、注释、样例数据并缓存
- 触发条件：首次 SQL 任务或手工刷新
- 返回：语义层缓存（含表描述）

# 3. vector_retriever - 向量召回器（middleware 内部）
- 功能：基于 `BAAI/bge-m3` 对任务与表描述做向量匹配
- 触发条件：SQL 生成前
- 返回：Top-K 候选表上下文

# 4. rebuild_data_semantic_layer - 语义层重建工具
- 功能：手动触发语义层刷新
- 触发条件：表结构更新后
- 返回：重建成功/失败状态
```

**示例**：
```python
# 语义层检索示例（逻辑位于 middleware/subagent.py）
semantic_context = subagent_middleware._retrieve_from_semantic_layer(
    task_prompt="分析最近7天设备告警趋势",
    tool_map=tool_map,
    top_k=4,
)
# 返回：包含匹配表名、字段、样例、元数据的 schema_context 字符串
```

#### L2 层：Content Tools（内容工具层）

**职责**：执行实际业务逻辑，处理数据

**工具列表**：
```python
# 现有工具迁移到 L2 层
- sql_inter: SQL 查询执行（需先通过 L1 加载表语义）
- extract_data: 数据提取（需先通过 L1 确认可访问）
- python_inter: Python 代码执行
- fig_inter: 可视化绘图
```

**特点**：
- ✅ 按需加载：仅在需要时注册到 context
- ✅ 语义增强：携带 L1 提供的表结构信息
- ✅ 权限控制：基于用户角色过滤可用工具

#### 双层架构工作流程

```
用户请求："分析设备告警数据"
    ↓
Supervisor Agent
    ↓
[Middleware: beforeModel]
    ├─ 读取/构建语义层缓存
    ├─ 向量召回 Top-K 相关表
    └─ 组装 schema_context 注入 SQL 生成提示词
    ↓
[Model Call]
    ├─ 接收：精简的工具列表 + 相关表语义
    ├─ 决策：选择 sql_inter
    └─ 生成：SQL 查询（基于准确的表结构）
    ↓
[Middleware: wrapToolCall]
    ├─ 验证：工具调用权限
    ├─ 注入：表结构信息到工具参数
    └─ 执行：sql_inter
    ↓
返回结果
```

**Token 节省对比**：

| 方案 | 工具描述 tokens | 表结构 tokens | 总计 |
|------|----------------|--------------|------|
| 传统全量 | 5000 | 3000 | 8000 |
| 双层按需 | 1500 | 800 | 2300 |
| **节省** | **-70%** | **-73%** | **-71%** |

---

### 3. 状态驱动的中间件拦截机制（规划项，未完全落地）

#### 3.1 中间件执行流程

```
Agent Invocation
    ↓
[beforeAgent] - 一次性钩子（初始化检查）
    ↓
Agent Loop Start
    ↓
[beforeModel] - 每次模型调用前
    ├─ 状态检查：当前任务类型、用户权限、上下文长度
    ├─ 工具选择：基于任务类型选择可用工具
    ├─ 语义加载：调用语义层检索相关表结构
    └─ 状态更新：注册工具到 context
    ↓
[wrapModelCall] - 包装模型调用
    ├─ 请求拦截：修改 system message（注入工具元数据）
    ├─ 动态注册：运行时注册新工具
    ├─ 调用模型：handler(request)
    └─ 响应处理：提取工具调用意图
    ↓
[Model executes]
    ↓
[afterModel] - 每次模型调用后
    ├─ 响应分析：检查是否包含工具调用
    ├─ 状态追踪：记录工具使用统计
    └─ 决策：是否需要再次调用模型
    ↓
[wrapToolCall] - 包装工具调用
    ├─ 权限验证：检查工具访问权限
    ├─ 参数注入：添加表结构语义
    ├─ 执行拦截：可短路（不调用真实工具）
    ├─ 调用工具：handler(request)
    └─ 结果处理：格式化、缓存
    ↓
[afterToolCall] - 每次工具调用后
    ├─ 结果分析：检查执行成功/失败
    ├─ 状态更新：更新文件系统
    └─ 决策：是否重试或继续
    ↓
Agent Loop Continue / End
    ↓
[afterAgent] - 一次性钩子（清理、持久化）
```

#### 3.2 状态 Schema 设计

```python
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any

class AgentState(BaseModel):
    """Agent 状态 Schema"""
    
    # 消息历史
    messages: List[BaseMessage] = Field(default_factory=list)
    
    # 任务状态
    current_task: Optional[str] = Field(default=None)
    task_type: Optional[str] = Field(default=None)  # "query" | "analyze" | "visualize"
    todo_list: List[Dict[str, Any]] = Field(default_factory=list)
    
    # 工具状态
    loaded_tools: List[str] = Field(default_factory=list)  # 已加载工具名
    tool_usage_stats: Dict[str, int] = Field(default_factory=dict)  # 使用统计
    
    # 数据表状态
    loaded_tables: List[str] = Field(default_factory=list)  # 已加载表名
    table_semantics: Dict[str, Dict] = Field(default_factory=dict)  # 表语义缓存
    
    # 记忆状态
    short_term_files: List[str] = Field(default_factory=list)
    long_term_memories: List[str] = Field(default_factory=list)
    
    # 私有状态（不返回给用户）
    _internal_counters: Dict[str, int] = Field(default_factory=dict)
    _cache: Dict[str, Any] = Field(default_factory=dict)
```

#### 3.3 中间件拦截实现

**中间件 1：动态工具加载器**

```python
from langchain import createMiddleware

class ToolLoaderState(BaseModel):
    loaded_tools: List[str] = Field(default_factory=list)
    tool_metadata: Dict[str, Dict] = Field(default_factory=dict)

tool_loader_middleware = createMiddleware(
    name="ToolLoaderMiddleware",
    stateSchema=ToolLoaderState,
    beforeModel={
        "canJumpTo": ["end"],
        "hook": (state) -> Optional[Dict]:
            # 状态驱动决策：根据任务类型加载工具
            if state.task_type == "sql_query":
                tools_to_load = ["sql_inter", "extract_data"]
            elif state.task_type == "data_analysis":
                tools_to_load = ["extract_data", "python_inter"]
            elif state.task_type == "visualization":
                tools_to_load = ["fig_inter", "python_inter"]
            else:
                tools_to_load = ["sql_inter", "extract_data", "python_inter", "fig_inter"]
            
            # 过滤已加载的工具
            new_tools = [t for t in tools_to_load if t not in state.loaded_tools]
            
            if new_tools:
                # 调用 Loader Tool 加载元数据
                metadata = await tool_loader.load(new_tools)
                return {
                    "loaded_tools": state.loaded_tools + new_tools,
                    "tool_metadata": {**state.tool_metadata, **metadata}
                }
            
            return None
    }
)
```

**中间件 2：表语义动态加载器**

```python
class TableSemanticsState(BaseModel):
    loaded_tables: List[str] = Field(default_factory=list)
    table_semantics: Dict[str, Dict] = Field(default_factory=dict)
    _last_table_check: int = Field(default=0)  # 私有状态

table_loader_middleware = createMiddleware(
    name="TableLoaderMiddleware",
    stateSchema=TableSemanticsState,
    wrapModelCall: async (request, handler):
        # 从用户消息中提取表名
        last_message = request.messages[-1].content
        mentioned_tables = extract_table_names(last_message)
        
        # 过滤未加载的表
        tables_to_load = [
            t for t in mentioned_tables 
            if t not in request.state.loaded_tables
        ]
        
        if tables_to_load:
            # 调用 schema_loader 加载表结构
            semantics = await schema_loader.load(tables_to_load)
            
            # 更新状态
            updated_state = {
                "loaded_tables": request.state.loaded_tables + tables_to_load,
                "table_semantics": {**request.state.table_semantics, **semantics}
            }
            
            # 注入表语义到 system message
            semantics_text = format_table_semantics(semantics)
            enhanced_system_msg = request.systemMessage.concat(
                f"\n\n可用数据表结构：\n{semantics_text}"
            )
            
            # 调用模型
            response = await handler({
                **request,
                "systemMessage": enhanced_system_msg
            })
            
            # 返回 Command 包含状态更新
            return Command(update=updated_state)
        
        # 无需加载，直接调用
        return await handler(request)
)
```

**中间件 3：工具调用权限拦截器**

```python
class ToolAuthState(BaseModel):
    tool_permissions: Dict[str, List[str]] = Field(default_factory=dict)
    _auth_cache: Dict[str, bool] = Field(default_factory=dict)

tool_auth_middleware = createMiddleware(
    name="ToolAuthMiddleware",
    stateSchema=ToolAuthState,
    wrapToolCall: async (request, handler):
        tool_name = request.tool_call.name
        user_id = request.runtime.context.get("user_id")
        
        # 检查权限缓存
        cache_key = f"{user_id}:{tool_name}"
        if cache_key in request.state._auth_cache:
            if not request.state._auth_cache[cache_key]:
                return Command({
                    "update": {},
                    "messages": [ToolMessage(
                        content=f"权限不足：无权使用工具 {tool_name}",
                        tool_call_id=request.tool_call.id
                    )]
                })
        
        # 调用权限检查
        has_permission = await check_tool_permission(user_id, tool_name)
        
        # 更新缓存
        request.state._auth_cache[cache_key] = has_permission
        
        if not has_permission:
            return Command({
                "update": {},
                "messages": [ToolMessage(
                    content=f"权限拒绝：工具 {tool_name} 需要更高级别权限",
                    tool_call_id=request.tool_call.id
                )]
            })
        
        # 权限通过，执行工具
        return await handler(request)
)
```

**中间件 4：工具调用短路缓存**

```python
class ToolCacheState(BaseModel):
    tool_cache: Dict[str, Any] = Field(default_factory=dict)
    cache_hits: int = Field(default=0)

tool_cache_middleware = createMiddleware(
    name="ToolCacheMiddleware",
    stateSchema=ToolCacheState,
    wrapToolCall: async (request, handler):
        tool_name = request.tool_call.name
        args_hash = hash(json.dumps(request.tool_call.args, sort_keys=True))
        cache_key = f"{tool_name}:{args_hash}"
        
        # 检查缓存
        if cache_key in request.state.tool_cache:
            # 缓存命中，短路返回
            request.state.cache_hits += 1
            return Command({
                "update": {"cache_hits": request.state.cache_hits},
                "messages": [ToolMessage(
                    content=request.state.tool_cache[cache_key],
                    tool_call_id=request.tool_call.id
                )]
            })
        
        # 缓存未命中，执行真实工具
        result = await handler(request)
        
        # 更新缓存（仅缓存成功结果）
        if result.status == "success":
            request.state.tool_cache[cache_key] = result.content
        
        return result
)
```

#### 3.4 中间件组合使用

```python
from langchain import createAgent

agent = createAgent(
    model="deepseek-ai/DeepSeek-V3",
    tools=[],  # 初始为空，由中间件动态加载
    store=InMemoryStore(),  # 长期记忆存储
    middleware=[
        # 1. 任务规划层
        todoListMiddleware(),
        
        # 2. 文件系统层
        createFilesystemMiddleware(backend=composite_backend),
        
        # 3. 子 Agent 层
        createSubAgentMiddleware(subagents=[...]),
        
        # 4. 状态驱动层（关键）
        tool_loader_middleware,      # 动态工具加载
        table_loader_middleware,     # 动态表语义加载
        tool_auth_middleware,        # 权限检查
        tool_cache_middleware,       # 缓存短路
        
        # 5. 上下文管理层
        summarizationMiddleware(...),
        contextEditingMiddleware(...),
        
        # 6. 监控层
        createMiddleware(
            name="UsageTracker",
            afterModel=lambda state: {"tool_usage_stats": track_usage(state)}
        ),
    ],
    contextSchema=z.object({
        "user_id": z.string(),
        "tenant_id": z.string(),
        "permissions": z.list(z.string()),
    })
)
```

#### 3.5 状态驱动决策示例

```python
# 示例：基于状态的条件跳转
smart_routing_middleware = createMiddleware(
    name="SmartRoutingMiddleware",
    beforeModel={
        "canJumpTo": ["tools", "end"],
        "hook": (state) -> Optional[Dict]:
            # 规则 1：上下文过长 → 触发摘要
            if count_tokens(state.messages) > 8000:
                return {"jumpTo": "summarize"}
            
            # 规则 2：连续 3 次工具失败 → 结束并报错
            failure_count = state._internal_counters.get("tool_failures", 0)
            if failure_count >= 3:
                return {
                    "messages": [AIMessage(
                        content="连续多次工具调用失败，请检查输入后重试"
                    )],
                    "jumpTo": "end"
                }
            
            # 规则 3：明确需要子 Agent → 跳转
            if "delegate to subagent" in state.messages[-1].content.lower():
                return {"jumpTo": "subagent"}
            
            return None
    }
)
```

---

## 📁 目录结构（改造后）

```
project/
├── README.md
├── requirements.txt
├── .env
├── langgraph.json
│
├── config/
│   ├── __init__.py
│   └── settings.py                    # Pydantic 配置管理
│
├── agents/                            # Agent 层
│   ├── __init__.py
│   ├── supervisor.py                  # 主 Agent（Supervisor）
│   ├── subagents/                     # 子 Agent 定义
│   │   ├── __init__.py
│   │   ├── sql_agent.py               # SQL 查询子 Agent
│   │   ├── data_analysis_agent.py     # 数据分析子 Agent
│   │   └── visualization_agent.py     # 可视化子 Agent
│   └── prompts/                       # 提示词库
│       ├── __init__.py
│       ├── supervisor_prompt.py       # 主 Agent 提示词
│       └── subagent_prompts.py        # 子 Agent 提示词
│
├── middleware/                        # 中间件层
│   ├── __init__.py
│   ├── todo_list.py                   # TODO List 中间件
│   ├── filesystem.py                  # 文件系统中间件
│   ├── subagent.py                    # 子 Agent 中间件
│   ├── summarization.py               # 记忆摘要中间件
│   └── context_edit.py                # 上下文编辑中间件
│
├── memory/                            # 记忆管理
│   ├── __init__.py
│   ├── short_term.py                  # 短期记忆（State Backend）
│   └── long_term.py                   # 长期记忆（Store Backend）
│
├── tools/                             # 工具层
│   ├── __init__.py
│   ├── base.py
│   ├── registry.py
│   ├── dynamic_registry.py
│   ├── sql/
│   │   └── query_tool.py              # 工具名: sql_inter
│   ├── data/
│   │   └── extract_tool.py            # 工具名: extract_data
│   ├── code/
│   │   └── python_executor.py         # 工具名: python_inter
│   └── visualization/
│       └── plot_tool.py               # 工具名: fig_inter
│
├── filesystem/                        # 文件系统后端
│   ├── __init__.py
│   ├── backends/                      # 后端实现
│   │   ├── __init__.py
│   │   ├── state_backend.py           # 状态后端
│   │   └── store_backend.py           # 存储后端
│   └── composite.py                   # 复合后端
│
└── graph.py                           # 主入口（兼容旧版）
```

---

## 🔧 核心改造模块

### 模块一：任务规范（TODO List）

**功能**：使 Agent 能够分解复杂任务、跟踪进度、调整计划

**中间件**：`todoListMiddleware`

**改造方案**：
```python
from langchain import createAgent, todoListMiddleware

# 添加到主 Agent
supervisor_agent = createAgent(
    model="deepseek-ai/DeepSeek-V3",
    tools=all_tools,
    middleware=[
        todoListMiddleware(),  # 启用任务规划
    ]
)
```

**使用场景**：
1. 用户提出复杂需求："分析设备数据并生成报告"
2. Agent 自动分解：
   - [ ] 查询设备数据表
   - [ ] 提取数据到 pandas
   - [ ] 统计分析
   - [ ] 生成可视化图表
   - [ ] 汇总报告
3. 逐项执行并跟踪进度

**优势**：
- ✅ 复杂任务可视化
- ✅ 进度可追踪
- ✅ 支持动态调整

---

### 模块二：文件系统后端

**功能**：提供文件读写工具，管理短期和长期记忆

**中间件**：`createFilesystemMiddleware`

**工具列表**：
- `ls` - 列出文件
- `read_file` - 读取文件
- `write_file` - 写入文件
- `edit_file` - 编辑文件

**改造方案**：
```python
from deepagents import createFilesystemMiddleware, CompositeBackend, StateBackend, StoreBackend
from langchain.langgraph import InMemoryStore

# 配置复合后端
store = InMemoryStore()

agent = createAgent(
    model="deepseek-ai/DeepSeek-V3",
    store=store,  # 启用长期记忆
    middleware=[
        createFilesystemMiddleware(
            backend=lambda config: CompositeBackend(
                StateBackend(config),  # 短期：/files/
                {"/memories/": StoreBackend(config)}  # 长期：/memories/
            ),
            customToolDescriptions={
                "ls": "列出当前工作目录的文件",
                "read_file": "读取文件内容，可指定行数",
                "write_file": "创建新文件或覆盖现有文件",
                "edit_file": "编辑现有文件的特定行",
            }
        )
    ]
)
```

**使用场景**：
1. **短期记忆**（`/files/`）：
   - 保存中间查询结果
   - 临时数据存储
   - 会话内共享

2. **长期记忆**（`/memories/`）：
   - 用户偏好设置
   - 历史分析模式
   - 跨会话知识

**示例**：
```python
# Agent 自动写入短期记忆
write_file("/files/query_result_20260330.json", query_results)

# Agent 保存长期记忆
write_file("/memories/user_preferences.json", {
    "preferred_chart_type": "bar",
    "default_date_range": "last_30_days"
})
```

---

### 模块三：子 Agent 派发

**功能**：创建专业化子 Agent，实现上下文隔离

**中间件**：`createSubAgentMiddleware`

**改造方案**：
```python
from deepagents import createSubAgentMiddleware, SubAgent

# 定义子 Agent
sql_subagent = SubAgent(
    name="sql_specialist",
    description="SQL 查询专家，负责数据库查询和数据提取",
    systemPrompt="""你是 SQL 查询专家。职责：
    1. 根据用户需求生成优化的 SQL 查询
    2. 执行查询并验证结果
    3. 将结果保存到文件系统
    
    可用工具：
    - sql_inter: 执行 SQL 查询
    - extract_data: 提取数据到 pandas
    
    工作流：
    1. 理解查询需求
    2. 生成 SQL
    3. 执行并验证
    4. 保存结果到 /files/sql_result_{task_id}.json
    """,
    tools=[sql_inter, extract_data],
    model="deepseek-ai/DeepSeek-V3"
)

data_analysis_subagent = SubAgent(
    name="data_analyst",
    description="数据分析专家，负责统计分析和数据处理",
    systemPrompt="""你是数据分析专家。职责：
    1. 从文件系统读取数据
    2. 执行统计分析
    3. 生成数据洞察
    
    可用工具：
    - python_inter: 执行 Python 代码
    - read_file: 读取数据文件
    
    工作流：
    1. 从 /files/ 读取数据
    2. 使用 pandas 分析
    3. 保存分析结果到 /files/analysis_{task_id}.json
    """,
    tools=[python_inter],
    model="deepseek-ai/DeepSeek-V3"
)

viz_subagent = SubAgent(
    name="visualization_specialist",
    description="可视化专家，负责创建图表和可视化展示",
    systemPrompt="""你是可视化专家。职责：
    1. 从文件系统读取分析结果
    2. 创建专业的可视化图表
    3. 保存图表到磁盘
    
    可用工具：
    - fig_inter: 执行绘图代码
    - read_file: 读取数据
    
    要求：
    - 使用 matplotlib/seaborn
    - 图表必须美观专业
    - 保存为 PNG 格式
    """,
    tools=[fig_inter],
    model="deepseek-ai/DeepSeek-V3"
)

# 创建主 Agent
supervisor = createAgent(
    model="deepseek-ai/DeepSeek-V3",
    tools=[],  # 主 Agent 不直接使用工具
    middleware=[
        createSubAgentMiddleware(
            subagents=[
                sql_subagent,
                data_analysis_subagent,
                viz_subagent
            ]
        )
    ]
)
```

**任务派发流程**：
```
用户请求："分析设备类型分布并可视化"
    ↓
Supervisor Agent
    ↓
派发任务给 sql_subagent："查询设备类型数据"
    ├─ 执行 SQL 查询
    └─ 保存到 /files/device_types.json
    ↓
派发任务给 data_analyst："分析设备类型分布"
    ├─ 读取 /files/device_types.json
    ├─ 统计分析
    └─ 保存到 /files/device_analysis.json
    ↓
派发任务给 viz_specialist："创建可视化图表"
    ├─ 读取 /files/device_analysis.json
    ├─ 创建柱状图
    └─ 保存到 images/device_chart.png
    ↓
Supervisor 汇总结果 → 返回用户
```

**优势**：
- ✅ 上下文隔离（每个子 Agent 独立上下文）
- ✅ 专业化分工
- ✅ 防止主 Agent 上下文膨胀
- ✅ 可并行执行

---

### 模块四：短期记忆（Session Memory）

**功能**：会话内持久化记忆，跨轮次共享

**实现**：State Backend

**改造方案**：
```python
from deepagents import StateBackend

# State Backend 自动包含在 FilesystemMiddleware 中
# 默认路径：/files/

# Agent 自动使用
write_file("/files/current_session_data.json", data)
read_file("/files/current_session_data.json")
```

**特点**：
- ✅ 会话内持久化（同一 thread）
- ✅ 自动清理（会话结束）
- ✅ 支持文件操作

---

### 模块五：长期记忆（Persistent Memory）

**功能**：跨会话持久化记忆

**实现**：Store Backend + LangGraph Store

**改造方案**：
```python
from langchain.langgraph import InMemoryStore
from deepagents import StoreBackend, CompositeBackend

# 配置 Store
store = InMemoryStore()

# 配置复合后端
backend = CompositeBackend(
    StateBackend(config),  # 短期：/files/
    {"/memories/": StoreBackend(config, store)}  # 长期：/memories/
)

agent = createAgent(
    model="deepseek-ai/DeepSeek-V3",
    store=store,
    middleware=[
        createFilesystemMiddleware(backend=backend)
    ]
)
```

**使用场景**：
```python
# 保存用户偏好
write_file("/memories/user_123/preferences.json", {
    "default_chart_type": "bar",
    "timezone": "Asia/Shanghai"
})

# 保存历史模式
write_file("/memories/analysis_patterns.json", {
    "common_queries": ["设备统计", "告警分析"],
    "frequent_tables": ["t_base_device_type", "t_fw_alarm_record"]
})

# 跨会话读取
prefs = read_file("/memories/user_123/preferences.json")
```

---

### 模块六：记忆摘要（Memory Summarization）

**功能**：自动压缩历史对话，防止上下文溢出

**中间件**：`summarizationMiddleware`

**改造方案**：
```python
from langchain import summarizationMiddleware

agent = createAgent(
    model="deepseek-ai/DeepSeek-V3",
    middleware=[
        summarizationMiddleware(
            model="deepseek-ai/DeepSeek-V3-Mini",  # 使用小模型降低成本
            trigger={
                "tokens": 4000,  # 超过 4000 tokens 触发
                "messages": 10   # 或超过 10 条消息
            },
            keep={
                "messages": 20   # 保留最近 20 条消息
            },
            summaryPrompt="""总结以下对话历史，提取关键信息：
            - 用户目标
            - 已完成的任务
            - 重要发现
            - 待办事项
            
            {messages}
            """
        )
    ]
)
```

**工作流程**：
```
对话历史增长
    ↓
达到触发条件（4000 tokens 或 10 条消息）
    ↓
自动触发摘要
    ├─ 保留最近 20 条消息
    ├─ 压缩旧消息为摘要
    └─ 插入摘要消息
    ↓
上下文窗口保持可控
```

**优势**：
- ✅ 自动管理上下文
- ✅ 保留关键信息
- ✅ 降低 token 成本
- ✅ 支持长对话

---

### 模块七：上下文编辑（Context Engineering）

**功能**：自动清理旧的工具结果，保持上下文精简

**中间件**：`contextEditingMiddleware`

**改造方案**：
```python
from langchain import contextEditingMiddleware, ClearToolUsesEdit

agent = createAgent(
    model="deepseek-ai/DeepSeek-V3",
    middleware=[
        contextEditingMiddleware(
            edits=[
                ClearToolUsesEdit(
                    triggerTokens=100000,  # 10 万 tokens 触发
                    keep=3,                # 保留最近 3 个工具结果
                    clearToolInputs=False, # 保留工具调用参数
                    placeholder="[cleared]" # 替换为占位符
                )
            ]
        )
    ]
)
```

**效果**：
```
原始上下文（10 万 tokens）:
- AI: 调用工具 A
- Tool: [大量结果数据...]
- AI: 调用工具 B
- Tool: [大量结果数据...]
- ...
    ↓
清理后:
- AI: 调用工具 A
- Tool: [cleared]
- AI: 调用工具 B  
- Tool: [cleared]
- AI: 调用工具 C
- Tool: [完整结果]  ← 保留最近 3 个
```

---

## 🚀 实施路线图

### 阶段 1：基础准备（1-2 天）

**目标**：安装依赖、配置环境

**任务**：
1. ✅ 安装 deepagents 包
2. ✅ 升级 langchain、langgraph
3. ✅ 配置 LangGraph Store
4. ✅ 创建新的目录结构

**代码示例**：
```bash
# 安装依赖
pip install deepagents
pip install --upgrade langchain langgraph langchain-core
```

**交付物**：
- 新目录结构
- 更新后的 requirements.txt

---

### 阶段 2：文件系统后端（2-3 天）

**目标**：实现短/长期记忆

**任务**：
1. ✅ 实现 State Backend
2. ✅ 实现 Store Backend
3. ✅ 实现 Composite Backend
4. ✅ 集成 FilesystemMiddleware
5. ✅ 测试文件工具

**代码文件**：
- `filesystem/backends/state_backend.py`
- `filesystem/backends/store_backend.py`
- `filesystem/composite.py`
- `middleware/filesystem.py`

**交付物**：
- 可运行的文件系统后端
- 短/长期记忆功能

---

### 阶段 3：子 Agent 系统（3-4 天）

**目标**：实现子 Agent 派发机制

**任务**：
1. ✅ 定义子 Agent 基类
2. ✅ 实现 SQL 子 Agent
3. ✅ 实现数据分析子 Agent
4. ✅ 实现可视化子 Agent
5. ✅ 创建 SubAgentMiddleware
6. ✅ 测试任务派发流程

**代码文件**：
- `agents/subagents/sql_agent.py`
- `agents/subagents/data_analysis_agent.py`
- `agents/subagents/visualization_agent.py`
- `middleware/subagent.py`

**交付物**：
- 3 个专业化子 Agent
- 任务派发机制

---

### 阶段 4：记忆管理（2-3 天）

**目标**：实现记忆摘要和上下文管理

**任务**：
1. ✅ 集成 SummarizationMiddleware
2. ✅ 集成 ContextEditingMiddleware
3. ✅ 配置触发条件
4. ✅ 测试记忆压缩效果

**代码文件**：
- `middleware/summarization.py`
- `middleware/context_edit.py`

**交付物**：
- 自动记忆摘要
- 上下文自动清理

---

### 阶段 5：TODO List 集成（1-2 天）

**目标**：启用任务规划能力

**任务**：
1. ✅ 集成 TodoListMiddleware
2. ✅ 测试任务分解
3. ✅ 测试进度跟踪

**代码文件**：
- `middleware/todo_list.py`

**交付物**：
- 任务规划能力

---

### 阶段 6：主 Agent 重构（2-3 天）

**目标**：重构 Supervisor Agent

**任务**：
1. ✅ 创建 Supervisor Agent
2. ✅ 编写 Supervisor Prompt
3. ✅ 集成所有中间件
4. ✅ 端到端测试

**代码文件**：
- `agents/supervisor.py`
- `agents/prompts/supervisor_prompt.py`
- `graph.py`（更新主入口）

**交付物**：
- 完整的 Deep Agent 系统

---

### 阶段 7：测试与优化（2-3 天）

**目标**：全面测试和性能优化

**任务**：
1. ✅ 单元测试
2. ✅ 集成测试
3. ✅ 性能测试
4. ✅ 文档编写

**交付物**：
- 测试报告
- 性能优化报告
- 完整文档

---

## 📊 改造对比

### 功能对比

| 功能 | 改造前 | 改造后 | 提升 |
|------|--------|--------|------|
| 任务规划 | ❌ | ✅ TODO List | +100% |
| 文件系统 | ❌ | ✅ 4 个工具 | +100% |
| 子 Agent | ❌ | ✅ 3 个专家 | +100% |
| 短期记忆 | ⚠️ globals() | ✅ State Backend | 规范化 |
| 长期记忆 | ❌ | ✅ Store Backend | +100% |
| 记忆摘要 | ❌ | ✅ 自动压缩 | +100% |
| 上下文管理 | ❌ | ✅ 自动清理 | +100% |

### 性能指标

| 指标 | 改造前 | 改造后 | 改进 |
|------|--------|--------|------|
| 上下文利用率 | 低（易溢出） | 高（自动管理） | +200% |
| 复杂任务处理 | 弱 | 强（子 Agent） | +300% |
| 跨会话记忆 | 无 | 完整支持 | +100% |
| Token 成本 | 高（无压缩） | 低（摘要） | -40% |
| 可维护性 | 中 | 高（模块化） | +150% |

---

## ⚠️ 风险与缓解

### 技术风险

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| Deep Agents 不兼容 | 低 | 高 | 提前测试，保留回滚方案 |
| 性能下降 | 中 | 中 | 性能基准测试，优化热点 |
| 学习曲线 | 中 | 低 | 提供文档和培训 |
| Store 持久化问题 | 低 | 中 | 使用 InMemoryStore 先测试 |

### 迁移风险

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 现有功能失效 | 低 | 高 | 保留 graph.py 兼容层 |
| 数据丢失 | 低 | 高 | 备份现有数据 |
| 用户习惯改变 | 中 | 低 | 提供迁移指南 |

---

## 📈 预期收益

### 开发效率
- **新功能开发**：2 天 → 0.5 天（-75%）
- **Bug 定位**：4 小时 → 1 小时（-75%）
- **代码复用**：30% → 80%（+167%）
- **工具集成**：1 天 → 2 小时（-75%）

### 系统能力
- **复杂任务处理**：支持 10 步骤 + 任务
- **上下文管理**：自动压缩，节省 40% token
- **跨会话记忆**：完整支持持久化
- **专业化分工**：3 个子 Agent 各司其职
- **动态工具加载**：按需加载，节省 70% token
- **表语义准确率**：从 60% → 95%（+58%）

### Token 优化
| 项目 | 优化前 | 优化后 | 节省 |
|------|--------|--------|------|
| 工具描述 | 5000 tokens | 1500 tokens | -70% |
| 表结构 | 3000 tokens | 800 tokens | -73% |
| 上下文历史 | 10000 tokens | 4000 tokens | -60% |
| **总计** | **18000 tokens** | **6300 tokens** | **-65%** |

### 性能提升
- **工具调用准确率**：75% → 95%（+27%）
- **表结构理解准确率**：60% → 95%（+58%）
- **平均响应时间**：8 秒 → 4 秒（-50%）
- **缓存命中率**：0% → 40%（新增）
- **权限检查延迟**：< 50ms

### 用户体验
- **任务可视化**：TODO List 实时跟踪
- **响应速度**：子 Agent 并行执行
- **记忆连续性**：跨会话记住用户偏好
- **准确性**：基于准确表语义的 SQL 生成

---

## 📚 参考资源

### 官方文档
1. [Deep Agents Overview](https://langchain-doc.cn/v1/python/deepagents/overview.html)
2. [Deep Agents Middleware](https://docs.langchain.com/oss/javascript/deepagents/middleware)
3. [GitHub - langchain-ai/deepagents](https://github.com/langchain-ai/deepagents)

### 技术参考
1. [LangGraph 状态管理](https://langchain-ai.github.io/langgraph/)
2. [LangChain Store](https://python.langchain.com/docs/langgraph/stores)
3. [Context Engineering](https://docs.langchain.com/oss/python/deepagents/context_engineering)

---

## ✅ 验收标准

### 功能验收
- [ ] TODO List 正常工作
- [ ] 文件系统 4 个工具可用
- [ ] 3 个子 Agent 可正常派发
- [ ] 短期记忆会话内持久化
- [ ] 长期记忆跨会话持久化
- [ ] 记忆摘要自动触发
- [ ] 上下文自动清理
- [ ] **双层工具架构正常工作**
  - [ ] Loader Tools 动态加载工具
  - [ ] Content Tools 按需注册
  - [ ] 表语义动态加载准确
- [ ] **状态驱动中间件生效**
  - [ ] beforeModel 工具选择正确
  - [ ] wrapModelCall 语义注入成功
  - [ ] wrapToolCall 权限拦截有效
  - [ ] 缓存短路命中率 > 30%

### 性能验收
- [ ] 复杂任务分解时间 < 5 秒
- [ ] 子 Agent 派发延迟 < 2 秒
- [ ] 记忆摘要压缩率 > 60%
- [ ] Token 使用量减少 > 60%
- [ ] **工具加载延迟 < 100ms**
- [ ] **表语义加载延迟 < 200ms**
- [ ] **权限检查延迟 < 50ms**
- [ ] **缓存命中率 > 40%**

### 质量验收
- [ ] 单元测试覆盖率 > 80%
- [ ] 集成测试全部通过
- [ ] 文档完整
- [ ] 代码审查通过
- [ ] **中间件独立测试通过**
- [ ] **状态 Schema 验证通过**

### 业务验收
- [ ] SQL 生成准确率 > 95%
- [ ] 工具调用准确率 > 95%
- [ ] 表结构理解准确率 > 95%
- [ ] 用户满意度 > 4.5/5.0
- [ ] 系统稳定性 > 99.5%

---

**审批签字**：________________  
**日期**：________________
