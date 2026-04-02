# LangChain 数据分析 Agent 架构级重构计划

## 📋 文档版本

- **版本**: v2.1
- **创建时间**: 2026-03-30
- **重点**: 架构级重构（方案二）
- **状态**: 主体已落地（文档持续对齐中）

---

## 🎯 重构目标

**核心目标**：通过架构级重构，将当前单体 script 重构为模块化、可扩展、易维护的企业级 Agent 系统。

**预期成果**：
- ✅ 模块化设计，各组件职责清晰
- ✅ 支持多数据源、多模型、多 Agent
- ✅ 完善的错误处理和日志记录
- ✅ 高测试覆盖率（>80%）
- ✅ 支持水平扩展和部署

### 当前实现快照（2026-04-02）

- ✅ 主入口为 `langgraph dev`（`langgraph.json` + `graph.py`）
- ✅ 中间件体系已运行：todo/filesystem/subagent/context_edit/tool_cache/tool_auth/state_driven
- ✅ 子 Agent 体系稳定：SQL/数据分析/可视化三类专家
- ✅ SQL 链路已接入语义层缓存与向量召回（`BAAI/bge-m3`）
- ✅ 工具标识统一：`sql_inter`、`extract_data`、`python_inter`、`fig_inter`

---

## 🏗️ 架构设计总览

### 1. 系统架构图

```
┌─────────────────────────────────────────────────────────────┐
│                      Application Layer                       │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │   CLI Interface │  │   REST API      │  │  Web UI      │ │
│  └────────┬────────┘  └────────┬────────┘  └──────┬───────┘ │
└───────────┼────────────────────┼───────────────────┼─────────┘
            │                    │                   │
┌───────────▼────────────────────▼───────────────────▼─────────┐
│                      Agent Orchestration Layer                │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │              LangGraph State Machine                     │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │  │
│  │  │  Planner │─▶│  Tools   │─▶│ Executor │─▶│ Review  │ │  │
│  │  └──────────┘  └──────────┘  └──────────┘  └─────────┘ │  │
│  └─────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────┘
            │                    │                   │
┌───────────▼────────────────────▼───────────────────▼─────────┐
│                      Core Services Layer                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │  Config  │  │ Database │  │  Models  │  │  Execution   │  │
│  │  Manager │  │ Manager  │  │ Manager  │  │  Sandbox     │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────┘  │
└───────────────────────────────────────────────────────────────┘
            │                    │                   │
┌───────────▼────────────────────▼───────────────────▼─────────┐
│                      Infrastructure Layer                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │  MySQL   │  │SiliconFl.│  │  LangS.  │  │  File System │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────┘  │
└───────────────────────────────────────────────────────────────┘
```

---

## 📁 详细目录结构

```
project/
├── README.md                          # 项目说明
├── requirements.txt                   # Python 依赖
├── pyproject.toml                     # 项目配置（Poetry/Flit）
├── setup.py                           # （可选）安装脚本
├── .env.example                       # 环境变量示例
├── .gitignore
├── Dockerfile                         # 容器化部署
├── docker-compose.yml                 # 多服务编排
│
├── config/                            # 配置管理
│   ├── __init__.py
│   ├── settings.py                    # 主配置类
│   ├── database.py                    # 数据库配置
│   ├── models.py                      # 模型配置
│   └── logging.py                     # 日志配置
│
├── core/                              # 核心业务逻辑
│   ├── __init__.py
│   ├── exceptions.py                  # 自定义异常
│   ├── types.py                       # 类型定义
│   ├── constants.py                   # 常量定义
│   └── interfaces.py                  # 接口定义
│
├── database/                          # 数据库层
│   ├── __init__.py
│   ├── connection.py                  # 数据库连接管理
│   ├── query_builder.py               # SQL 查询构建器
│   ├── validators.py                  # SQL 验证器
│   └── repositories/                  # 数据仓库层
│       ├── __init__.py
│       ├── base.py                    # 基础仓库
│       └── device_repository.py       # 设备数据仓库
│
├── models/                            # 模型层
│   ├── __init__.py
│   ├── base.py                        # 基础模型类
│   ├── siliconflow.py                 # 硅基流动模型
│   ├── deepseek.py                    # DeepSeek 模型
│   └── factory.py                     # 模型工厂
│
├── tools/                             # 工具层（重点重构）
│   ├── __init__.py
│   ├── base.py                        # 工具基类
│   ├── registry.py                    # 工具注册中心
│   ├── decorators.py                  # （规划）工具装饰器
│   │
│   ├── sql/                           # SQL 相关工具
│   │   ├── __init__.py
│   │   ├── query_tool.py              # SQL 查询工具（tool name: sql_inter）
│   │   ├── analyzer.py                # SQL 分析器
│   │   └── formatter.py               # 结果格式化
│   │
│   ├── data/                          # 数据处理工具
│   │   ├── __init__.py
│   │   ├── extract_tool.py            # 数据提取工具（tool name: extract_data）
│   │   ├── transform_tool.py          # 数据转换工具
│   │   └── analysis_tool.py           # 数据分析工具
│   │
│   ├── code/                          # 代码执行工具
│   │   ├── __init__.py
│   │   ├── python_executor.py         # Python 执行器（tool name: python_inter）
│   │   ├── sandbox.py                 # 沙箱环境
│   │   └── security.py                # 安全检查
│   │
│   └── visualization/                 # 可视化工具
│       ├── __init__.py
│       ├── plot_tool.py               # 绘图工具（tool name: fig_inter）
│       ├── chart_factory.py           # 图表工厂
│       └── templates/                 # 图表模板
│           ├── line_chart.py
│           ├── bar_chart.py
│           └── scatter_chart.py
│
├── agents/                            # Agent 层
│   ├── __init__.py
│   ├── base.py                        # Agent 基类
│   ├── data_agent.py                  # 数据分析 Agent
│   ├── states.py                      # Agent 状态定义
│   ├── graphs/                        # LangGraph 图定义
│   │   ├── __init__.py
│   │   ├── react_graph.py             # ReAct 图
│   │   ├── plan_execute_graph.py      # 规划 - 执行图
│   │   └── custom_graph.py            # 自定义图
│   └── prompts/                       # 提示词管理
│       ├── __init__.py
│       ├── system_prompts.py          # 系统提示词
│       ├── tool_prompts.py            # 工具提示词
│       └── templates/                 # 提示词模板
│
├── services/                          # 服务层
│   ├── __init__.py
│   ├── logger.py                      # 日志服务
│   ├── monitor.py                     # 监控服务
│   ├── cache.py                       # 缓存服务
│   └── metrics.py                     # 指标收集
│
├── api/                               # API 层
│   ├── __init__.py
│   ├── main.py                        # FastAPI 应用
│   ├── routes/                        # 路由
│   │   ├── __init__.py
│   │   ├── chat.py                    # 聊天接口
│   │   ├── tools.py                   # 工具接口
│   │   └── health.py                  # 健康检查
│   ├── schemas/                       # Pydantic 模型
│   │   ├── __init__.py
│   │   ├── request.py                 # 请求模型
│   │   └── response.py                # 响应模型
│   └── middleware/                    # 中间件
│       ├── __init__.py
│       ├── auth.py                    # 认证中间件
│       └── logging.py                 # 日志中间件
│
├── utils/                             # 工具函数
│   ├── __init__.py
│   ├── helpers.py                     # 辅助函数
│   ├── validators.py                  # 验证函数
│   ├── formatters.py                  # 格式化函数
│   └── security.py                    # 安全工具
│
├── tests/                             # 测试目录
│   ├── __init__.py
│   ├── conftest.py                    # pytest 配置
│   ├── fixtures/                      # 测试固件
│   │   ├── __init__.py
│   │   ├── database.py                # 数据库固件
│   │   └── models.py                  # 模型固件
│   ├── unit/                          # 单元测试
│   │   ├── __init__.py
│   │   ├── test_tools/                # 工具测试
│   │   ├── test_agents/               # Agent 测试
│   │   └── test_services/             # 服务测试
│   ├── integration/                   # 集成测试
│   │   ├── __init__.py
│   │   ├── test_workflow.py           # 工作流测试
│   │   └── test_api.py                # API 测试
│   └── e2e/                           # 端到端测试
│       ├── __init__.py
│       └── test_scenarios.py          # 场景测试
│
├── scripts/                           # 脚本目录
│   ├── __init__.py
│   ├── setup_db.py                    # 数据库初始化
│   ├── migrate.py                     # 数据迁移
│   └── deploy.py                      # 部署脚本
│
├── docs/                              # 文档目录
│   ├── architecture.md                # 架构文档
│   ├── api.md                         # API 文档
│   ├── deployment.md                  # 部署文档
│   └── development.md                 # 开发指南
│
└── graph.py                           # 主入口（兼容旧版）
```

---

## 🔧 核心组件详细设计

### 1. 配置管理系统

**文件**: `config/settings.py`

```python
from pydantic import BaseSettings, Field
from typing import Optional, List
from functools import lru_cache

class DatabaseSettings(BaseSettings):
    """数据库配置"""
    host: str = Field(default="localhost", description="数据库主机")
    port: int = Field(default=3306, description="数据库端口")
    user: str = Field(default="root", description="用户名")
    password: str = Field(default="", description="密码")
    database: str = Field(default="alarm", description="数据库名")
    pool_size: int = Field(default=5, description="连接池大小")
    max_overflow: int = Field(default=10, description="最大溢出连接数")
    
    class Config:
        env_prefix = "DB_"

class ModelSettings(BaseSettings):
    """模型配置"""
    provider: str = Field(default="siliconflow", description="模型提供商")
    api_key: str = Field(description="API 密钥")
    base_url: str = Field(default="https://api.siliconflow.cn/v1")
    model_name: str = Field(default="deepseek-ai/DeepSeek-V3")
    temperature: float = Field(default=0.1, ge=0, le=2)
    max_tokens: int = Field(default=4096, gt=0)
    timeout: int = Field(default=60, gt=0)
    
    class Config:
        env_prefix = "MODEL_"

class Settings(BaseSettings):
    """全局配置"""
    # 应用配置
    app_name: str = "Data Analysis Agent"
    debug: bool = False
    version: str = "2.0.0"
    
    # 子配置
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    model: ModelSettings = Field(default_factory=ModelSettings)
    
    # LangSmith 配置
    langsmith_api_key: Optional[str] = None
    langsmith_project: Optional[str] = None
    
    # 日志配置
    log_level: str = "INFO"
    log_file: Optional[str] = None
    
    class Config:
        env_file = ".env"
        case_sensitive = False

@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()
```

**使用示例**:
```python
from config import get_settings

settings = get_settings()
db_host = settings.database.host
api_key = settings.model.api_key
```

---

### 2. 工具基类与注册中心

**文件**: `tools/base.py`

```python
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
import logging

logger = logging.getLogger(__name__)

class ToolResult(BaseModel):
    """工具执行结果标准格式"""
    success: bool = Field(default=False, description="是否成功")
    data: Optional[Any] = Field(default=None, description="返回数据")
    message: str = Field(default="", description="人类可读消息")
    error: Optional[str] = Field(default=None, description="错误信息")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    
    def to_tool_message_content(self) -> str:
        """转换为 ToolMessage 的 content"""
        if self.success:
            return self.message or (str(self.data) if self.data else "执行成功")
        else:
            return f"执行失败：{self.error or '未知错误'}"

class BaseCustomTool(BaseTool, ABC):
    """自定义工具基类"""
    
    # 工具元数据
    category: str = Field(default="general", description="工具类别")
    version: str = Field(default="1.0.0", description="工具版本")
    
    # 执行计数
    execution_count: int = Field(default=0, description="执行次数")
    
    @abstractmethod
    def _run(self, *args, **kwargs) -> ToolResult:
        """同步执行工具（必须实现）"""
        pass
    
    def _arun(self, *args, **kwargs) -> ToolResult:
        """异步执行工具（可选实现）"""
        return self._run(*args, **kwargs)
    
    def post_run_hook(self, result: ToolResult) -> ToolResult:
        """执行后钩子：确保返回值格式正确"""
        # 确保 content 不为空
        if not result.message and not result.data:
            result.message = "工具执行完成"
        
        # 记录执行统计
        self.execution_count += 1
        
        # 记录日志
        logger.info(f"Tool {self.name} executed: success={result.success}")
        
        return result
```

**文件**: `tools/registry.py`

```python
from typing import Dict, List, Type, Optional
from tools.base import BaseCustomTool
import logging

logger = logging.getLogger(__name__)

class ToolRegistry:
    """工具注册中心（单例模式）"""
    
    _instance: Optional['ToolRegistry'] = None
    _tools: Dict[str, BaseCustomTool] = {}
    
    def __new__(cls) -> 'ToolRegistry':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def register(self, tool: BaseCustomTool) -> None:
        """注册工具"""
        if tool.name in self._tools:
            logger.warning(f"Tool {tool.name} already registered, overwriting")
        self._tools[tool.name] = tool
        logger.info(f"Tool {tool.name} registered successfully")
    
    def get(self, name: str) -> Optional[BaseCustomTool]:
        """获取工具"""
        return self._tools.get(name)
    
    def get_all(self) -> List[BaseCustomTool]:
        """获取所有工具"""
        return list(self._tools.values())
    
    def get_by_category(self, category: str) -> List[BaseCustomTool]:
        """按类别获取工具"""
        return [t for t in self._tools.values() if t.category == category]
    
    def unregister(self, name: str) -> bool:
        """注销工具"""
        if name in self._tools:
            del self._tools[name]
            logger.info(f"Tool {name} unregistered")
            return True
        return False
    
    def clear(self) -> None:
        """清空所有工具"""
        self._tools.clear()
        logger.info("All tools cleared")

# 全局注册中心实例
registry = ToolRegistry()

# 装饰器用于快速注册工具
def register_tool(tool_class: Type[BaseCustomTool]) -> Type[BaseCustomTool]:
    """工具注册装饰器"""
    tool_instance = tool_class()
    registry.register(tool_instance)
    return tool_class
```

---

### 3. 数据库管理层

**文件**: `database/connection.py`

```python
import pymysql
from typing import Optional, List, Tuple, Any
from contextlib import contextmanager
import logging
from config.settings import get_settings

logger = logging.getLogger(__name__)

class DatabaseManager:
    """数据库连接管理器"""
    
    def __init__(self, database: str = None):
        settings = get_settings()
        db_config = settings.database
        
        self.host = db_config.host
        self.port = db_config.port
        self.user = db_config.user
        self.password = db_config.password
        self.database = database or db_config.database
        self.charset = 'utf8'
        
        self._connection: Optional[pymysql.Connection] = None
    
    def connect(self) -> pymysql.Connection:
        """建立数据库连接"""
        try:
            self._connection = pymysql.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                passwd=self.password,
                db=self.database,
                charset=self.charset,
                cursorclass=pymysql.cursors.DictCursor  # 返回字典格式
            )
            logger.info(f"Connected to database: {self.database}")
            return self._connection
        except pymysql.Error as e:
            logger.error(f"Database connection failed: {e}")
            raise
    
    def close(self) -> None:
        """关闭数据库连接"""
        if self._connection:
            self._connection.close()
            logger.info("Database connection closed")
    
    @contextmanager
    def cursor(self):
        """上下文管理器：自动管理 cursor"""
        if not self._connection:
            self.connect()
        
        cursor = self._connection.cursor()
        try:
            yield cursor
            self._connection.commit()
        except Exception as e:
            self._connection.rollback()
            logger.error(f"Database operation failed: {e}")
            raise
        finally:
            cursor.close()
    
    def execute_query(self, sql: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
        """执行查询并返回结果"""
        with self.cursor() as cursor:
            cursor.execute(sql, params or ())
            return cursor.fetchall()
    
    def execute_update(self, sql: str, params: Optional[Tuple] = None) -> int:
        """执行更新操作并返回影响行数"""
        with self.cursor() as cursor:
            affected = cursor.execute(sql, params or ())
            return affected
    
    def __enter__(self):
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
```

---

### 4. 工具实现示例

**文件**: `tools/sql/query_tool.py`

```python
from typing import Optional
from pydantic import BaseModel, Field
from tools.base import BaseCustomTool, ToolResult
from database.connection import DatabaseManager
import json
import logging
import re

logger = logging.getLogger(__name__)

class SQLQueryInput(BaseModel):
    """SQL 查询输入参数"""
    sql_query: str = Field(
        ...,
        description="SQL 查询语句，例如：SELECT * FROM table_name WHERE condition"
    )

class SQLQueryTool(BaseCustomTool):
    """SQL 查询工具"""
    
    name: str = "sql_inter"
    description: str = """
    用于在 MySQL 数据库中执行 SQL 查询。
    适用场景：
    - 查询数据库表中的数据
    - 执行统计分析
    - 获取元数据信息
    
    注意事项：
    - 只支持 SELECT 查询，不支持修改数据的操作
    - 查询结果超过 1000 条时会自动截断
    """
    category: str = "sql"
    args_schema: Type[BaseModel] = SQLQueryInput
    
    max_results: int = 1000  # 最大返回结果数
    
    def _run(self, sql_query: str) -> ToolResult:
        """执行 SQL 查询"""
        # SQL 安全检查
        if not self._is_safe_query(sql_query):
            return ToolResult(
                success=False,
                error="SQL 语句包含危险操作，只允许 SELECT 查询"
            )
        
        try:
            with DatabaseManager() as db:
                # 执行查询
                results = db.execute_query(sql_query)
                
                # 处理空结果
                if not results:
                    diagnosis = self._diagnose_empty_result(sql_query, db)
                    return ToolResult(
                        success=True,
                        data=[],
                        message=f"查询执行成功，但未找到匹配记录。\n{diagnosis}"
                    )
                
                # 限制结果数量
                total_count = len(results)
                if total_count > self.max_results:
                    results = results[:self.max_results]
                    message = f"查询到 {total_count} 条记录，返回前 {self.max_results} 条"
                else:
                    message = f"查询成功，共返回 {total_count} 条记录"
                
                return ToolResult(
                    success=True,
                    data=results,
                    message=message,
                    metadata={
                        "total_count": total_count,
                        "returned_count": len(results),
                        "truncated": total_count > self.max_results
                    }
                )
        
        except Exception as e:
            logger.error(f"SQL query failed: {e}")
            return ToolResult(
                success=False,
                error=f"SQL 执行失败：{str(e)}"
            )
    
    def _is_safe_query(self, sql: str) -> bool:
        """SQL 安全检查：只允许 SELECT"""
        sql_upper = sql.strip().upper()
        
        # 允许的操作
        allowed_keywords = ['SELECT', 'WITH', 'FROM', 'WHERE', 'JOIN', 'GROUP', 'ORDER', 'LIMIT']
        
        # 禁止的操作
        forbidden_keywords = ['INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER', 'TRUNCATE']
        
        # 检查是否包含禁止操作
        for keyword in forbidden_keywords:
            if re.search(rf'\b{keyword}\b', sql_upper):
                logger.warning(f"Forbidden SQL operation detected: {keyword}")
                return False
        
        # 检查是否以 SELECT 或 WITH 开头
        if not (sql_upper.startswith('SELECT') or sql_upper.startswith('WITH')):
            return False
        
        return True
    
    def _diagnose_empty_result(self, sql_query: str, db: DatabaseManager) -> str:
        """诊断空结果原因"""
        diagnosis = []
        
        # 提取表名
        table_match = re.search(r'FROM\s+`?(\w+)`?', sql_query, re.IGNORECASE)
        if table_match:
            table_name = table_match.group(1)
            
            # 检查表是否存在
            table_exists = db.execute_query(
                f"SHOW TABLES LIKE '{table_name}'"
            )
            if not table_exists:
                return f"原因：表 '{table_name}' 不存在"
            
            # 检查表总记录数
            count_result = db.execute_query(
                f"SELECT COUNT(*) as cnt FROM `{table_name}`"
            )
            total = count_result[0]['cnt'] if count_result else 0
            diagnosis.append(f"表 '{table_name}' 共有 {total} 条记录")
            
            # 如果有 WHERE 条件，检查条件
            where_match = re.search(r'WHERE\s+(.+?)(?:ORDER|GROUP|LIMIT|$)', sql_query, re.IGNORECASE | re.DOTALL)
            if where_match and total > 0:
                where_clause = where_match.group(1).strip()
                diagnosis.append(f"WHERE 条件：{where_clause}")
                diagnosis.append("建议：检查 WHERE 条件是否正确")
        
        return "\n".join(diagnosis)
```

---

### 5. Agent 状态管理

**文件**: `agents/states.py`

```python
from typing import TypedDict, List, Dict, Any, Optional
from langchain_core.messages import BaseMessage
import pandas as pd

class AgentState(TypedDict):
    """Agent 状态定义"""
    # 消息历史
    messages: List[BaseMessage]
    
    # 数据上下文
    dataframes: Dict[str, pd.DataFrame]  # DataFrame 存储
    query_results: Dict[str, List[Dict]]  # 查询结果
    
    # 执行上下文
    current_step: str  # 当前执行步骤
    errors: List[str]  # 错误列表
    metadata: Dict[str, Any]  # 元数据
    
    # 可视化
    images: Dict[str, str]  # 图片路径映射

class DataAgentState(AgentState):
    """数据分析 Agent 专用状态"""
    # 扩展特定字段
    analysis_type: Optional[str]  # 分析类型
    target_tables: List[str]  # 目标表列表
    generated_sql: Optional[str]  # 生成的 SQL
```

---

### 6. LangGraph 图定义

**文件**: `agents/graphs/react_graph.py`

```python
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import SystemMessage
from typing import List

def create_data_agent_graph(tools: List, prompt: str, model):
    """创建数据分析 Agent 图"""
    
    # 创建 ReAct Agent
    graph = create_react_agent(
        model=model,
        tools=tools,
        prompt=prompt,
        state_schema=None,  # 可选：自定义状态 schema
        name="data_agent"
    )
    
    return graph
```

---

## 🚀 部署方案

### 1. Docker 容器化

**文件**: `Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY . .

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**文件**: `docker-compose.yml`

```yaml
version: '3.8'

services:
  agent-api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DB_HOST=mysql
      - DB_PORT=3306
      - DB_USER=root
      - DB_PASSWORD=secret
    - DB_DATABASE=alarm
      - MODEL_API_KEY=${MODEL_API_KEY}
    depends_on:
      - mysql
    volumes:
      - ./logs:/app/logs
  
  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: secret
      MYSQL_DATABASE: alarm
      MYSQL_USER: myuser
      MYSQL_PASSWORD: mypass
    ports:
      - "3306:3306"
    volumes:
      - mysql_data:/var/lib/mysql

volumes:
  mysql_data:
```

### 2. 启动命令

```bash
# 开发环境
docker-compose up -d

# 生产环境
docker-compose -f docker-compose.prod.yml up -d

# 查看日志
docker-compose logs -f agent-api
```

---

## 📊 实施路线图

### 阶段 1：基础架构搭建（2-3 天）

**目标**：完成目录结构、配置管理、数据库层

**任务**：
1. ✅ 创建目录结构
2. ✅ 实现配置管理系统
3. ✅ 实现数据库连接管理
4. ✅ 编写基础单元测试

**交付物**：
- 完整的目录结构
- 可运行的配置系统
- 数据库连接管理器及测试

### 阶段 2：工具层重构（3-4 天）

**目标**：重构 4 个核心工具

**任务**：
1. ✅ 实现工具基类和注册中心
2. ✅ 重构 sql_inter 工具
3. ✅ 重构 extract_data 工具
4. ✅ 重构 python_inter 工具
5. ✅ 重构 fig_inter 工具
6. ✅ 编写工具单元测试

**交付物**：
- 工具基类和注册中心
- 4 个重构后的工具
- 完整的工具测试

### 阶段 3：Agent 层重构（2-3 天）

**目标**：实现 Agent 状态管理和图定义

**任务**：
1. ✅ 定义 Agent 状态
2. ✅ 实现 LangGraph 图
3. ✅ 管理提示词系统
4. ✅ 集成测试

**交付物**：
- Agent 状态定义
- LangGraph 图实现
- 集成测试用例

### 阶段 4：API 层和部署（2-3 天）

**目标**：实现 REST API 和容器化部署

**任务**：
1. ✅ 实现 FastAPI 应用
2. ✅ 编写 API 文档
3. ✅ 创建 Docker 配置
4. ✅ 编写部署文档

**交付物**：
- REST API 服务
- Docker 镜像
- 部署文档

### 阶段 5：优化和文档（1-2 天）

**目标**：性能优化和文档完善

**任务**：
1. ✅ 性能测试和优化
2. ✅ 编写开发文档
3. ✅ 编写用户手册
4. ✅ 代码审查和清理

**交付物**：
- 性能测试报告
- 完整文档
- 清理后的代码

---

## 📈 预期收益

### 代码质量提升

| 指标 | 当前 | 目标 | 提升 |
|------|------|------|------|
| 类型覆盖率 | 0% | 95% | +95% |
| 测试覆盖率 | 0% | 85% | +85% |
| 代码重复率 | 40% | <10% | -75% |
| 平均函数复杂度 | 15 | <8 | -47% |

### 开发效率提升

| 指标 | 当前 | 目标 | 提升 |
|------|------|------|------|
| 新功能开发时间 | 2 天 | 0.5 天 | -75% |
| Bug 修复时间 | 4 小时 | 1 小时 | -75% |
| 代码审查时间 | 2 小时 | 0.5 小时 | -75% |

### 系统稳定性提升

| 指标 | 当前 | 目标 | 提升 |
|------|------|------|------|
| API 错误率 | 15% | <2% | -87% |
| 平均故障间隔 | 1 天 | 30 天 | +2900% |
| 恢复时间 | 30 分钟 | 5 分钟 | -83% |

---

## ⚠️ 风险与缓解

### 技术风险

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 架构过于复杂 | 中 | 高 | 分阶段实施，每阶段 review |
| 性能下降 | 低 | 中 | 性能测试，优化热点代码 |
| 兼容性问题 | 中 | 中 | 保留旧版入口，逐步迁移 |

### 项目风险

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 进度延期 | 中 | 中 | 设置缓冲时间，优先级管理 |
| 人员不足 | 低 | 高 | 合理分工，必要时寻求支持 |
| 需求变更 | 中 | 高 | 敏捷开发，快速迭代 |

---

## 📚 参考资源

### 技术文档
1. [LangGraph 官方文档](https://langchain-ai.github.io/langgraph/)
2. [LangChain 最佳实践](https://python.langchain.com/docs/guides/best_practices)
3. [FastAPI 文档](https://fastapi.tiangolo.com/)
4. [硅基流动 API 文档](https://docs.siliconflow.cn/)

### 架构参考
1. [Clean Architecture - Robert C. Martin](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
2. [12-Factor App](https://12factor.net/)
3. [Microservices Architecture](https://microservices.io/)

### 工具推荐
1. **代码质量**: black, flake8, mypy
2. **测试框架**: pytest, pytest-asyncio
3. **API 文档**: Swagger/OpenAPI
4. **监控**: Prometheus, Grafana

---

## ✅ 验收标准

### 功能验收
- [ ] 所有现有功能正常工作
- [ ] API 响应时间 < 500ms
- [ ] 支持并发用户数 >= 10
- [ ] 错误率 < 2%

### 代码质量验收
- [ ] 类型覆盖率 >= 90%
- [ ] 测试覆盖率 >= 80%
- [ ] 无严重代码异味
- [ ] 文档完整

### 部署验收
- [ ] Docker 镜像构建成功
- [ ] 一键部署脚本可用
- [ ] 监控告警配置完成
- [ ] 回滚方案验证通过

---

**审批签字**：________________  
**日期**：________________
