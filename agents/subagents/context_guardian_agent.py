"""
Context Guardian Agent - 上下文治理子 Agent

职责（仅做压缩与保真，不做业务执行）：
1. 接收当前任务上下文和工具输出
2. 输出结构化压缩结果，保留关键线索
3. 禁止执行 SQL / Python / 可视化工具
"""

from typing import List, Callable

from middleware.subagent import SubAgent


CONTEXT_GUARDIAN_SUBAGENT = SubAgent(
    name="context_guardian",
    description="上下文治理专家，负责压缩上下文并保留高价值信息，不执行业务工具",
    system_prompt="""你是上下文治理专家。你的唯一职责是压缩上下文并保留关键信息。

你必须输出 JSON 对象，推荐结构：
{"compact_context":"...","kept_items":["..."],"dropped_items":["..."]}

治理原则：
1. 保留：任务目标、最近可执行 SQL、最近错误、schema 摘要、下一步动作
2. 丢弃：重复日志、大型原始 payload、历史冗余失败细节
3. 不要输出 markdown，不要输出额外解释

严格禁止：
- 禁止调用 sql_inter / python_inter / fig_inter
- 禁止执行数据库查询和绘图
- 禁止生成与上下文治理无关内容
""",
    tools=[],
    model="deepseek-ai/DeepSeek-V3",
)


def create_context_guardian_agent(tools: List[Callable] = None) -> SubAgent:
    """创建 Context Guardian Agent。默认仅注入 llm_skill。"""
    agent = CONTEXT_GUARDIAN_SUBAGENT

    if tools is not None:
        agent.tools = tools
    else:
        from tools.code.llm_skill_tool import llm_skill

        agent.tools = [llm_skill]

    return agent
