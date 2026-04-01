# 架构文档

## 系统架构

Data Analysis Agent 2.0 采用分层架构设计，各层职责清晰，便于维护和扩展。

## 分层架构

### 1. 应用层 (Application Layer)

提供多种交互方式：
- **CLI Interface**: 命令行界面
- **REST API**: HTTP API 接口
- **Web UI**: 网页界面

### 2. 编排层 (Orchestration Layer)

基于 LangGraph 的状态机：
- **Planner**: 规划执行步骤
- **Tools**: 工具调用
- **Executor**: 执行逻辑
- **Review**: 结果审查

### 3. 核心服务层 (Core Services Layer)

提供基础服务：
- **Config Manager**: 配置管理
- **Database Manager**: 数据库连接管理
- **Model Manager**: LLM 模型管理
- **Execution Sandbox**: 代码执行沙箱

### 4. 基础设施层 (Infrastructure Layer)

外部依赖：
- **MySQL**: 数据存储
- **SiliconFlow**: LLM API
- **LangSmith**: 监控和追踪
- **File System**: 文件存储

## 核心组件

### 配置管理

使用 Pydantic 进行配置验证，支持从环境变量加载。

```python
from config import get_settings

settings = get_settings()
db_host = settings.database.host
```

### 工具系统

基于基类和注册中心实现：

```python
from tools.base import BaseCustomTool, ToolResult
from tools.registry import register_tool

@register_tool
class MyTool(BaseCustomTool):
    name = "my_tool"
    
    def _execute(self, **kwargs) -> ToolResult:
        return ToolResult(success=True, data=data)
```

### 数据库访问

使用上下文管理器管理连接：

```python
from database import DatabaseManager

with DatabaseManager() as db:
    results = db.execute_query("SELECT * FROM users")
```

## 数据流

```
用户请求 → API 层 → Agent 编排 → 工具执行 → 结果返回
                ↓
            状态管理（LangGraph State）
                ↓
            消息历史、DataFrame、图像
```

## 扩展点

1. **添加新工具**: 继承 `BaseCustomTool` 并注册
2. **添加新 Agent**: 创建新的图定义
3. **添加新 API**: 在 `api/routes/` 添加路由
4. **添加新模型**: 在 `models/` 添加模型支持
