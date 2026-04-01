"""
Supervisor Agent - 主 Agent

职责：
1. 接收用户请求
2. 任务分解和规划
3. 子 Agent 派发
4. 结果汇总
"""

from typing import Any, Dict, List, Optional, Callable
from types import SimpleNamespace
from langchain_core.messages import HumanMessage
from langchain_core.messages import ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.prebuilt import create_react_agent
from langgraph.store.base import BaseStore

from config.settings import Settings
from models.llm import create_llm
from middleware.filesystem import FilesystemMiddleware, create_filesystem_tools
from middleware.subagent import SubAgentMiddleware, SubAgent
from middleware.todo_list import TodoListMiddleware, create_todo_middleware
from middleware.state_driven import StateDrivenRuntime
from middleware.tool_runtime import ToolRuntimeMiddleware
from middleware.base import MiddlewareManager
from middleware.tool_auth import ToolAuthMiddleware
from middleware.tool_cache import ToolCacheMiddleware
from middleware.context_edit import ContextEditingMiddleware
from memory.summarization import SummarizationMiddleware, SummarizationConfig
from filesystem import CompositeBackend, StateBackend, StoreBackend
from tools.registry import registry
from agents.states import create_default_runtime_state

# 导入工具模块，触发全局工具实例注册
from tools.sql import query_tool  # noqa: F401
from tools.data import extract_tool  # noqa: F401
from tools.code import python_executor  # noqa: F401
from tools.visualization import plot_tool  # noqa: F401
from tools.loader import table_metadata  # noqa: F401

from agents.subagents import (
    create_sql_agent,
    create_data_analysis_agent,
    create_visualization_agent
)


# Supervisor Agent 系统提示词
SUPERVISOR_PROMPT = """你是数据分析 Supervisor Agent，负责协调多个专业子 Agent 完成复杂的数据分析任务。

## 核心职责

1. **任务理解与分解**
   - 理解用户的自然语言需求
   - 将复杂任务分解为可执行的子任务
   - 使用 TODO List 跟踪任务进度

2. **子 Agent 协调**
   - 根据任务类型选择合适的子 Agent
   - 委派任务并监控执行
   - 汇总各子 Agent 的结果

3. **资源管理**
   - 使用文件系统管理临时数据
   - 维护短期记忆（/files/）和长期记忆（/memories/）
   - 控制上下文大小

## 可用子 Agent

1. **sql_specialist** - SQL 查询专家
   - 职责：生成和执行 SQL 查询
   - 使用场景：需要从数据库提取数据
   - 输出：查询结果保存到 /files/sql_result_*.json

2. **data_analyst** - 数据分析专家
   - 职责：统计分析和数据洞察
   - 使用场景：需要对数据进行深入分析
   - 输出：分析结果保存到 /files/analysis_*.json

3. **visualization_specialist** - 可视化专家
   - 职责：创建图表和可视化
   - 使用场景：需要数据可视化展示
   - 输出：图表保存到 images/chart_*.png

## 工作流程

```
用户请求
    ↓
任务分解 → create_todo
    ↓
委派子 Agent → delegate_to_xxx
    ↓
收集结果 ← read_file
    ↓
汇总输出 → 用户
```

## 文件系统规范

**短期记忆（/files/）**：
- 临时查询结果
- 中间处理数据
- 会话结束后清理

**长期记忆（/memories/）**：
- 用户偏好设置
- 历史分析模式
- 跨会话持久化

## 任务规划示例

用户："分析设备告警趋势并生成报告"

你的执行计划：
1. create_todo: "查询告警数据"
2. create_todo: "分析告警趋势"
3. create_todo: "创建可视化图表"
4. create_todo: "生成分析报告"

然后依次委派给子 Agent：
- delegate_to_sql_specialist: 查询告警数据
- delegate_to_data_analyst: 分析趋势
- delegate_to_visualization_specialist: 创建图表

最后汇总结果并生成报告。

## 注意事项

- 始终先创建 TODO List 再执行
- 子 Agent 的结果会保存到文件系统
- 使用 read_file 读取子 Agent 的输出
- 复杂任务要分步骤执行
- 及时更新任务状态
"""


class SupervisorAgent:
    """
    Supervisor Agent 封装类
    
    整合所有中间件和子 Agent，提供统一的接口
    """
    
    def __init__(
        self,
        settings: Optional[Settings] = None,
        store: Optional[BaseStore] = None
    ):
        """
        初始化 Supervisor Agent
        
        Args:
            settings: 配置设置
            store: LangGraph Store 实例（用于长期记忆）
        """
        self.settings = settings or Settings()
        self.store = store
        
        # 初始化后端
        self._init_backends()
        
        # 初始化中间件
        self._init_middlewares()

        # 线程级运行时状态
        self.thread_states: Dict[str, Dict[str, Any]] = {}

        # 初始化子 Agent
        self._init_subagents()
        
        # 创建主 Agent
        self._create_agent()
    
    def _init_backends(self) -> None:
        """初始化文件系统后端"""
        # 短期记忆后端
        self.state_backend = StateBackend(base_path="/files/")
        
        # 长期记忆后端
        self.store_backends = {}
        if self.store:
            self.store_backends["/memories/"] = StoreBackend(
                store=self.store,
                base_path="/memories/"
            )
        
        # 复合后端
        self.backend = CompositeBackend(
            self.state_backend,
            self.store_backends
        )
    
    def _init_middlewares(self) -> None:
        """初始化中间件"""
        # 文件系统中间件
        self.fs_middleware = FilesystemMiddleware(self.backend)
        
        # TODO List 中间件
        self.todo_middleware = create_todo_middleware()
        
        # 摘要中间件
        self.summary_config = SummarizationConfig(
            trigger_tokens=4000,
            trigger_messages=10,
            keep_messages=20
        )
        self.summarization_middleware = SummarizationMiddleware(self.summary_config)

        # 状态驱动运行时（动态工具加载 + 表语义注入）
        self.state_runtime = StateDrivenRuntime()

        # 工具调用拦截运行时（权限 + 缓存 + 统计）
        self.tool_runtime = ToolRuntimeMiddleware(max_cache_entries=256)

        # 标准中间件管理器（BaseMiddleware 钩子体系）
        self.middleware_manager = MiddlewareManager()
        self.middleware_manager.add(ToolAuthMiddleware())       # priority=80
        self.middleware_manager.add(ToolCacheMiddleware())      # priority=50
        self.middleware_manager.add(ContextEditingMiddleware()) # priority=10

        # 中间件执行顺序（用于观测与审计）
        self.middleware_order = [
            "todo_list",
            "filesystem",
            "subagent",
            "state_driven.before_model",
            *self.middleware_manager.names(),
            "middleware_manager.wrap_tool_call",
            "tool_runtime.wrap_tool_call[fallback]",
            "summarization.after_model",
        ]
    
    def _init_subagents(self) -> None:
        """初始化子 Agent"""
        # 创建子 Agent
        self.sql_agent = create_sql_agent()
        self.data_analysis_agent = create_data_analysis_agent()
        self.visualization_agent = create_visualization_agent()
        
        # 子 Agent 中间件
        self.subagent_middleware = SubAgentMiddleware([
            self.sql_agent,
            self.data_analysis_agent,
            self.visualization_agent
        ])
    
    def _create_agent(self) -> None:
        """创建主 Agent"""
        # 收集所有工具
        tools = []
        
        # 文件系统工具
        tools.extend(self.fs_middleware.get_tools())
        
        # TODO List 工具
        tools.extend(self.todo_middleware.get_tools())
        
        # 子 Agent 派发工具
        tools.extend(self.subagent_middleware.get_tools())
        
        # 摘要工具
        tools.extend(self.summarization_middleware.get_tools())

        # 注册中间件工具到注册中心，供 tool_loader 按需提取
        for t in tools:
            if hasattr(t, "name"):
                registry.register(t)
        
        # 创建 LLM
        llm = create_llm(self.settings)
        self.llm = llm
        self.base_tools = tools
        
        # 创建 ReAct Agent
        self.agent = create_react_agent(
            model=llm,
            tools=tools,
            prompt=SUPERVISOR_PROMPT,
            name="supervisor_agent"
        )
        
        self.tools = tools

    @staticmethod
    def _to_runtime_messages(messages: List[Any]) -> List[Any]:
        """将 BaseMessage 列表转换为 create_react_agent 兼容的消息载荷。"""
        runtime_messages: List[Any] = []
        role_map = {
            "human": "user",
            "ai": "assistant",
            "system": "system",
            "tool": "tool",
        }
        for message in messages:
            msg_type = getattr(message, "type", None)
            content = getattr(message, "content", None)
            if msg_type is not None and content is not None:
                runtime_messages.append(
                    {"role": role_map.get(msg_type, msg_type), "content": content}
                )
            else:
                runtime_messages.append(message)
        return runtime_messages

    @staticmethod
    def _stringify_tool_response(response: Any) -> str:
        """将工具返回值统一转换为字符串。"""
        if isinstance(response, ToolMessage):
            return response.content
        if isinstance(response, str):
            return response
        content = getattr(response, "content", None)
        if isinstance(content, str):
            return content
        return str(response)

    @staticmethod
    def _invoke_original_tool(tool_obj: Any, tool_kwargs: Dict[str, Any]) -> Any:
        """调用原始工具对象，兼容 BaseTool / StructuredTool / 普通可调用对象。"""
        if hasattr(tool_obj, "invoke"):
            return tool_obj.invoke(tool_kwargs)
        if callable(tool_obj):
            return tool_obj(**tool_kwargs)
        raise TypeError(f"Unsupported tool type: {type(tool_obj)}")

    async def _invoke_tool_via_manager(
        self,
        tool_obj: Any,
        tool_kwargs: Dict[str, Any],
        state: Dict[str, Any],
        permissions: Optional[List[str]] = None,
    ) -> str:
        """通过标准 MiddlewareManager 执行一次工具调用。"""
        tool_name = getattr(tool_obj, "name", getattr(tool_obj, "__name__", "unknown_tool"))

        if permissions and "*" not in permissions and tool_name not in permissions:
            state["auth_denials"] = state.get("auth_denials", 0) + 1
            return f"权限拒绝：无权调用工具 {tool_name}"

        tool_call = SimpleNamespace(
            name=tool_name,
            args=tool_kwargs,
            id=f"{tool_name}-{state.get('total_tool_calls', 0) + 1}",
        )

        async def handler(_tool_call: Any) -> Any:
            state["total_tool_calls"] = state.get("total_tool_calls", 0) + 1
            usage = state.setdefault("tool_usage_stats", {})
            usage[tool_name] = usage.get(tool_name, 0) + 1
            return self._invoke_original_tool(tool_obj, tool_kwargs)

        result = await self.middleware_manager.run_wrap_tool_call(state, tool_call, handler)
        await self.middleware_manager.run_after_tool_call(state, tool_call, result)
        return self._stringify_tool_response(result)

    def _wrap_tools_with_manager(
        self,
        tools: List[Any],
        state: Dict[str, Any],
        permissions: Optional[List[str]] = None,
    ) -> List[Any]:
        """生成带标准中间件链的运行时工具列表。"""
        wrapped_tools: List[Any] = []
        legacy_wrapped_tools = self.tool_runtime.wrap_tools(tools, state=state, permissions=permissions)

        for tool_obj, legacy_tool in zip(tools, legacy_wrapped_tools):
            tool_name = getattr(tool_obj, "name", getattr(tool_obj, "__name__", "unknown_tool"))
            description = getattr(tool_obj, "description", f"Wrapped tool: {tool_name}")
            args_schema = getattr(tool_obj, "args_schema", None)

            def sync_func(_legacy_tool=legacy_tool, **tool_kwargs: Any) -> str:
                return _legacy_tool.invoke(tool_kwargs)

            async def async_func(_tool_obj=tool_obj, **tool_kwargs: Any) -> str:
                return await self._invoke_tool_via_manager(_tool_obj, tool_kwargs, state, permissions)

            if args_schema is not None:
                wrapped_tools.append(
                    StructuredTool.from_function(
                        func=sync_func,
                        coroutine=async_func,
                        name=tool_name,
                        description=description,
                        args_schema=args_schema,
                    )
                )
            else:
                wrapped_tools.append(
                    StructuredTool.from_function(
                        func=sync_func,
                        coroutine=async_func,
                        name=tool_name,
                        description=description,
                    )
                )

        return wrapped_tools
    
    async def invoke(
        self,
        message: str,
        thread_id: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        调用 Agent
        
        Args:
            message: 用户消息
            thread_id: 线程ID
            **kwargs: 其他参数
            
        Returns:
            Agent 响应
        """
        effective_thread_id = thread_id or "default"

        config = {
            "configurable": {
                "thread_id": effective_thread_id
            }
        }
        
        if self.store:
            config["store"] = self.store

        # 记录会话消息（简化 token 估算）
        self.summarization_middleware.add_message(
            role="user",
            content=message,
            tokens=max(1, len(message) // 4),
        )

        # 初始化/读取统一线程状态
        state = self.thread_states.setdefault(effective_thread_id, create_default_runtime_state())
        state["current_task"] = message
        context = dict(kwargs.get("context") or {})
        if "role" in kwargs and "role" not in context:
            context["role"] = kwargs["role"]
        if "user_id" in kwargs and "user_id" not in context:
            context["user_id"] = kwargs["user_id"]
        if kwargs.get("permissions") == ["*"] and "role" not in context:
            context["role"] = "admin"
        if context:
            state["context"] = context

        before_agent_cmd = await self.middleware_manager.run_before_agent(state)
        if before_agent_cmd and before_agent_cmd.stop:
            return {
                "messages": before_agent_cmd.messages or [],
                "content": "Agent 在启动阶段被中间件中止。",
                "status": "stopped_before_agent",
            }

        # 按请求动态构建工具和提示词（状态驱动）
        runtime_ctx, runtime_tools = self.state_runtime.prepare(message)
        state["task_type"] = runtime_ctx.task_type
        state["loaded_tools"] = runtime_ctx.loaded_tools
        state["loaded_tables"] = runtime_ctx.mentioned_tables

        if runtime_ctx.schema_prompt:
            state["table_semantics"]["runtime"] = {"prompt": runtime_ctx.schema_prompt}

        runtime_prompt = self.state_runtime.build_prompt(SUPERVISOR_PROMPT, context=runtime_ctx)

        model_messages = [HumanMessage(content=message)]
        before_model_cmd, model_messages = await self.middleware_manager.run_before_model(
            state,
            model_messages,
        )
        if before_model_cmd and before_model_cmd.stop:
            return {
                "messages": before_model_cmd.messages or model_messages,
                "content": "模型调用前被中间件中止。",
                "status": "stopped_before_model",
            }

        if not runtime_tools:
            runtime_tools = self.base_tools

        # wrapToolCall 级别拦截：权限 + 缓存短路
        permissions = kwargs.get("permissions")
        wrapped_tools = self._wrap_tools_with_manager(runtime_tools, state=state, permissions=permissions)

        # 简单跳转策略：连续失败过多时短路结束
        if state.get("consecutive_failures", 0) >= 3:
            state["jump_strategy"] = "end"
            state["last_jump_decision"] = "consecutive_failures>=3"
            return {
                "messages": [],
                "content": "连续 3 次工具调用失败，已中止本轮执行。请检查输入或权限后重试。",
                "status": "short_circuit",
            }
        state["jump_strategy"] = "normal"
        state["last_jump_decision"] = None

        runtime_agent = create_react_agent(
            model=self.llm,
            tools=wrapped_tools,
            prompt=runtime_prompt,
            name="supervisor_agent_runtime"
        )

        response = await runtime_agent.ainvoke(
            {"messages": self._to_runtime_messages(model_messages)},
            config=config
        )

        await self.middleware_manager.run_after_model(state, response)

        assistant_msg = ""
        if isinstance(response, dict) and response.get("messages"):
            last_message = response["messages"][-1]
            assistant_msg = getattr(last_message, "content", "") or str(last_message)

        if assistant_msg:
            self.summarization_middleware.add_message(
                role="assistant",
                content=assistant_msg,
                tokens=max(1, len(assistant_msg) // 4),
            )

        # 运行时统计回写
        state["runtime_stats"] = {
            "middleware_order": self.middleware_order,
            "state_runtime": self.state_runtime.get_stats(),
            "tool_runtime": {
                "cache_hits": state.get("cache_hits", 0),
                "cache_misses": state.get("cache_misses", 0),
                "auth_denials": state.get("auth_denials", 0),
                "consecutive_failures": state.get("consecutive_failures", 0),
                "context_edited": state.get("context_edited", False),
            },
        }

        await self.middleware_manager.run_after_agent(state, response)
        
        return response
    
    def get_tools_info(self) -> Dict[str, List[str]]:
        """获取工具信息"""
        return {
            "filesystem": [t.name if hasattr(t, 'name') else str(t) for t in self.fs_middleware.get_tools()],
            "todo_list": [t.name if hasattr(t, 'name') else str(t) for t in self.todo_middleware.get_tools()],
            "subagents": [t.name if hasattr(t, 'name') else str(t) for t in self.subagent_middleware.get_tools()],
            "summarization": [t.name if hasattr(t, 'name') else str(t) for t in self.summarization_middleware.get_tools()],
        }
    
    def get_status(self) -> Dict[str, Any]:
        """获取 Agent 状态"""
        return {
            "backends": self.backend.get_backend_info(),
            "todo_progress": self.todo_middleware.get_progress(),
            "subagents": self.subagent_middleware.get_subagent_info(),
            "tools": self.get_tools_info(),
            "middleware_order": self.middleware_order,
            "middleware_manager": {
                "middlewares": [m.name for m in self.middleware_manager.middlewares],
            },
            "active_threads": len(self.thread_states),
            "runtime_stats": self.state_runtime.get_stats(),
        }


def create_supervisor_agent(
    settings: Optional[Settings] = None,
    store: Optional[BaseStore] = None
) -> SupervisorAgent:
    """
    创建 Supervisor Agent（便捷函数）
    
    Args:
        settings: 配置设置
        store: Store 实例
        
    Returns:
        SupervisorAgent 实例
    """
    return SupervisorAgent(settings, store)
