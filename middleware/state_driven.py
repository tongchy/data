"""状态驱动运行时组件

提供最小可用的状态驱动能力：
1. 基于任务类型动态加载工具
2. 按需加载表结构语义并注入系统提示
3. 记录加载统计，供运行时观测
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import logging
import re

from tools.loader.tool_loader import ToolLoader, TaskType
from tools.loader.schema_loader import SchemaLoader

logger = logging.getLogger(__name__)


@dataclass
class RuntimeContext:
    """运行时上下文数据"""

    task_type: str
    mentioned_tables: List[str]
    loaded_tools: List[str]
    schema_prompt: str


class StateDrivenRuntime:
    """状态驱动运行时协调器"""

    def __init__(self):
        self.tool_loader = ToolLoader()
        self.schema_loader = SchemaLoader()

    def _extract_candidate_tables(self, message: str) -> List[str]:
        """从用户消息中提取候选表名。"""
        if not message:
            return []

        # 匹配类似 t_xxx 或常见英文表名片段
        matches = re.findall(r"\b(t_[a-zA-Z0-9_]+|[a-zA-Z]+_[a-zA-Z0-9_]+)\b", message)
        unique = []
        for m in matches:
            if m not in unique:
                unique.append(m)
        return unique[:8]

    def build_runtime_context(self, message: str) -> RuntimeContext:
        """根据消息构建运行时上下文。"""
        task_type = self.tool_loader.detect_task_type(message)
        mentioned_tables = self._extract_candidate_tables(message)

        loaded_tools = self.tool_loader.load_tools(
            task_type=task_type,
            mentioned_tables=mentioned_tables,
            include_base=True,
        )

        schema_prompt = ""
        if mentioned_tables:
            schema_prompt = self.schema_loader.generate_schema_prompt(mentioned_tables)

        ctx = RuntimeContext(
            task_type=task_type.value if isinstance(task_type, TaskType) else str(task_type),
            mentioned_tables=mentioned_tables,
            loaded_tools=[t.name if hasattr(t, "name") else str(t) for t in loaded_tools],
            schema_prompt=schema_prompt,
        )

        logger.info(
            "Runtime context built: task_type=%s, tools=%s, tables=%s",
            ctx.task_type,
            len(ctx.loaded_tools),
            ctx.mentioned_tables,
        )
        return ctx

    def resolve_tools(self, message: str) -> List[Any]:
        """按消息动态解析工具列表。"""
        task_type = self.tool_loader.detect_task_type(message)
        mentioned_tables = self._extract_candidate_tables(message)
        return self.tool_loader.load_tools(task_type=task_type, mentioned_tables=mentioned_tables, include_base=True)

    def prepare(self, message: str) -> tuple[RuntimeContext, List[Any]]:
        """一次性准备运行时上下文与工具列表，避免重复加载。"""
        ctx = self.build_runtime_context(message)
        tools = self.tool_loader.get_loaded_tools()
        return ctx, tools

    def build_prompt(self, base_prompt: str, message: str = "", context: Optional[RuntimeContext] = None) -> str:
        """构造注入了表语义的系统提示词。"""
        ctx = context or self.build_runtime_context(message)
        if not ctx.schema_prompt:
            return base_prompt

        return f"{base_prompt}\n\n{ctx.schema_prompt}"

    def get_stats(self) -> Dict[str, Any]:
        """返回运行时加载统计。"""
        return {
            "tool_loader": self.tool_loader.get_load_stats(),
            "schema_loader": self.schema_loader.get_cache_stats(),
        }
