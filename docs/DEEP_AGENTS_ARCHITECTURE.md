# Deep Agents 架构文档

## 概述

本项目基于 LangChain Deep Agents 框架重构，实现了具备任务规划、子 Agent 派发、记忆管理等高级功能的深度智能 Agent。

## 架构图

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
│  ┌──────────────┐  ┌──────────────┐                          │
│  │ Summarization│  │ Context Edit │                          │
│  │ Middleware   │  │ Middleware   │                          │
│  └──────────────┘  └──────────────┘                          │
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
│                    Sub Agents Layer                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │ SQL Agent    │  │ Data Agent   │  │ Viz Agent        │   │
│  │ (SQL 查询)    │  │ (数据分析)   │  │ (可视化)         │   │
│  └──────────────┘  └──────────────┘  └──────────────────┘   │
└───────────────────────────────────────────────────────────────┘
```

## 核心组件

### 1. Supervisor Agent

主 Agent，负责协调所有子系统和子 Agent。

**文件**: `agents/supervisor.py`

**职责**:
- 接收用户请求
- 任务分解和规划
- 子 Agent 派发
- 结果汇总

### 2. 中间件层

#### 2.1 Filesystem Middleware

提供文件操作工具，支持短期和长期记忆。

**文件**: `middleware/filesystem.py`

**工具**:
- `ls` - 列出目录
- `read_file` - 读取文件
- `write_file` - 写入文件
- `edit_file` - 编辑文件

**路径规范**:
- `/files/` - 短期记忆（会话内）
- `/memories/` - 长期记忆（跨会话）

#### 2.2 SubAgent Middleware

子 Agent 派发机制。

**文件**: `middleware/subagent.py`

**子 Agent**:
- `sql_specialist` - SQL 查询专家
- `data_analyst` - 数据分析专家
- `visualization_specialist` - 可视化专家

#### 2.3 Todo List Middleware

任务规划和管理。

**文件**: `middleware/todo_list.py`

**工具**:
- `create_todo` - 创建任务
- `update_todo` - 更新任务状态
- `list_todos` - 列出任务
- `get_todo` - 获取任务详情

#### 2.4 Summarization Middleware

记忆摘要和上下文管理。

**文件**: `memory/summarization.py`

**功能**:
- 自动触发摘要
- 压缩历史消息
- 上下文管理

### 3. 后端层

#### 3.1 State Backend

短期记忆后端，基于内存存储。

**文件**: `filesystem/backends/state_backend.py`

**特点**:
- 会话内持久化
- 自动清理
- 适合临时数据

#### 3.2 Store Backend

长期记忆后端，基于 LangGraph Store。

**文件**: `filesystem/backends/store_backend.py`

**特点**:
- 跨会话持久化
- 支持搜索
- 适合用户偏好

#### 3.3 Composite Backend

复合后端，统一路由到相应后端。

**文件**: `filesystem/composite.py`

### 4. 子 Agent 层

#### 4.1 SQL Agent

**文件**: `agents/subagents/sql_agent.py`

**职责**:
- 生成 SQL 查询
- 执行数据库操作
- 保存查询结果

#### 4.2 Data Analysis Agent

**文件**: `agents/subagents/data_analysis_agent.py`

**职责**:
- 统计分析
- 数据清洗
- 生成洞察

#### 4.3 Visualization Agent

**文件**: `agents/subagents/visualization_agent.py`

**职责**:
- 创建图表
- 可视化设计
- 保存图像

## 工作流程

### 典型任务流程

```
用户: "分析设备告警趋势并生成报告"
    ↓
Supervisor Agent
    ↓
1. 任务分解 (create_todo)
   - [ ] 查询告警数据
   - [ ] 分析告警趋势
   - [ ] 创建可视化图表
   - [ ] 生成分析报告
    ↓
2. 委派子 Agent
   - delegate_to_sql_specialist: 查询告警数据
   - delegate_to_data_analyst: 分析趋势
   - delegate_to_visualization_specialist: 创建图表
    ↓
3. 收集结果
   - read_file("/files/sql_result_xxx.json")
   - read_file("/files/analysis_xxx.json")
   - read_file("images/chart_xxx.png")
    ↓
4. 汇总输出
   - 生成综合分析报告
   - 返回给用户
```

## 配置

### 环境变量

```bash
# API 配置
SILICONFLOW_API_KEY=your_api_key
SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1

# 模型配置
DEFAULT_MODEL=deepseek-ai/DeepSeek-V3

# 数据库配置
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=password
DB_NAME=test

# LangSmith 配置（可选）
LANGSMITH_API_KEY=your_key
LANGSMITH_PROJECT=data-agent
```

### LangGraph 配置

```json
{
  "dependencies": ["./"],
  "graphs": {
    "data_agent": "./graph.py:data_agent"
  },
  "env": ".env"
}
```

## 使用方法

### 1. LangGraph CLI

```bash
# 安装依赖
pip install -r requirements.txt

# 启动开发服务器
langgraph dev
```

### 2. 直接导入使用

```python
from graph import get_supervisor_agent

agent = get_supervisor_agent()
response = await agent.invoke("分析设备数据", thread_id="session_1")
```

### 3. 查看 Agent 状态

```python
from graph import get_agent_status

status = get_agent_status()
print(status)
```

## 功能对比

| 功能 | 改造前 | 改造后 | 提升 |
|------|--------|--------|------|
| 任务规划 | ❌ | ✅ TODO List | +100% |
| 文件系统 | ❌ | ✅ 4 个工具 | +100% |
| 子 Agent | ❌ | ✅ 3 个专家 | +100% |
| 短期记忆 | ⚠️ | ✅ State Backend | 规范化 |
| 长期记忆 | ❌ | ✅ Store Backend | +100% |
| 记忆摘要 | ❌ | ✅ 自动压缩 | +100% |
| 上下文管理 | ❌ | ✅ 自动清理 | +100% |

## 目录结构

```
project/
├── agents/
│   ├── supervisor.py              # 主 Agent
│   ├── subagents/                 # 子 Agent
│   │   ├── sql_agent.py
│   │   ├── data_analysis_agent.py
│   │   └── visualization_agent.py
│   └── prompts/                   # 提示词
├── middleware/                    # 中间件层
│   ├── filesystem.py
│   ├── subagent.py
│   └── todo_list.py
├── memory/                        # 记忆管理
│   ├── short_term.py
│   ├── long_term.py
│   └── summarization.py
├── filesystem/                    # 文件系统后端
│   ├── backends/
│   │   ├── state_backend.py
│   │   └── store_backend.py
│   └── composite.py
├── config/                        # 配置
├── tools/                         # 工具层
├── api/                           # API 层
├── graph.py                       # 主入口
└── langgraph.json                 # LangGraph 配置
```

## 扩展指南

### 添加新的子 Agent

1. 在 `agents/subagents/` 创建新文件
2. 定义 SubAgent 实例
3. 在 `agents/supervisor.py` 中注册

### 添加新的中间件

1. 在 `middleware/` 创建新文件
2. 实现中间件类
3. 在 `agents/supervisor.py` 中集成

### 自定义后端

1. 继承 `StateBackend` 或 `StoreBackend`
2. 实现必要的方法
3. 在 `CompositeBackend` 中注册
