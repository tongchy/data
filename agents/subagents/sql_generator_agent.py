"""
SQL Generator Agent - SQL 生成专用子 Agent

职责（仅做生成，不做执行）：
1. 接收自然语言任务 + schema_context
2. 输出严格满足 sql_inter 契约的 JSON：{"sql_query": "SELECT ..."}
3. 禁止执行 SQL、禁止做数据分析与可视化
"""

from typing import List, Callable
from middleware.subagent import SubAgent


SQL_GENERATOR_SUBAGENT = SubAgent(
    name="sql_generator",
    description="SQL 生成专家，根据自然语言任务和表结构信息生成可执行 SQL，只输出 JSON 契约，不执行任何操作",
    system_prompt="""你是 SQL 生成专家。你的唯一职责是根据任务描述和表结构信息生成正确的 MySQL SELECT 语句。

## 输出契约（必须严格遵守）
你必须且只能以如下 JSON 格式作答，不允许任何额外文字：
```json
{"sql_query": "SELECT ..."}
```

## 生成规则
1. 只生成 SELECT 或 WITH ... SELECT 语句
2. 禁止生成 INSERT / UPDATE / DELETE / DROP / CREATE / ALTER / TRUNCATE
3. 始终使用反引号包裹表名和字段名（避免关键字冲突）
4. 对大数据集强制加 LIMIT（最多 1000 行），除非用户明确要求全量
5. 使用任务信息中提供的实际表名和字段名，不要臆造字段
6. 若涉及中文搜索，使用 LIKE '%关键词%' 或 REGEXP 而非 =

## 严格禁止
- 禁止在 JSON 之外输出任何说明或注释
- 禁止执行 SQL（不调用 sql_inter）
- 禁止调用 python_inter / fig_inter / extract_data
- 禁止返回 markdown 代码块（只返回纯 JSON）

## 示例

任务：查询 users 表中最近注册的 10 个用户
表结构：users(id INT, name VARCHAR, created_at DATETIME)

正确输出：
{"sql_query": "SELECT `id`, `name`, `created_at` FROM `users` ORDER BY `created_at` DESC LIMIT 10"}
""",
    tools=[],  # 将在 create_sql_generator_agent 时注入 llm_skill
    model="deepseek-ai/DeepSeek-V3"
)


def create_sql_generator_agent(tools: List[Callable] = None) -> SubAgent:
    """
    创建 SQL 生成 Agent 实例。

    Args:
        tools: 可选工具列表。默认仅注入 llm_skill，可额外传入 table_metadata。

    Returns:
        配置好的 SQL 生成 SubAgent（只生成 SQL，不执行）
    """
    agent = SQL_GENERATOR_SUBAGENT

    if tools is not None:
        agent.tools = tools
    else:
        from tools.code.llm_skill_tool import llm_skill
        agent.tools = [llm_skill]

    return agent
