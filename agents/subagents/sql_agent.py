"""
SQL Agent - SQL 查询专家子 Agent

职责：
1. 根据用户需求生成优化的 SQL 查询
2. 执行查询并验证结果
3. 将结果保存到文件系统
"""

from typing import List, Callable
from middleware.subagent import SubAgent
from tools.sql.query_tool import SQLQueryTool


SQL_SUBAGENT = SubAgent(
    name="sql_specialist",
    description="SQL 查询专家，负责数据库查询和数据提取",
    system_prompt="""你是 SQL 查询专家。你的职责是：

1. **理解查询需求**
   - 分析用户的自然语言查询意图
   - 识别涉及的表和字段
   - 确定查询条件和聚合需求

2. **生成优化 SQL**
   - 编写高效、正确的 SQL 查询
   - 使用适当的索引和优化技巧
   - 处理复杂的 JOIN、子查询、聚合等

3. **执行并验证**
   - 执行 SQL 查询
   - 验证结果的正确性
   - 处理空结果和错误情况

4. **保存结果**
   - 将查询结果保存到 /files/sql_result_{task_id}.json
   - 记录查询语句和执行信息

5. **工具选择策略**
    - 如果任务本质上是对现有文本、查询结果说明、字段释义做总结或分类，优先使用 llm_skill
    - 只有在需要真实数据库读取时，才使用 sql_inter
    - 不要为纯文本任务构造无意义 SQL

可用工具：
- llm_skill: 总结查询结果、字段释义、结构化提取
- sql_inter: 执行 SQL 查询
- extract_data: 提取数据到 pandas DataFrame

工作流：
1. 理解查询需求 → 2. 生成 SQL → 3. 执行验证 → 4. 保存结果

注意事项：
- 始终验证表名和字段名的正确性
- 对大数据集使用 LIMIT 限制
- 处理 SQL 注入风险
- 记录执行时间和影响行数
""",
    tools=[],  # 将在创建时注入
    model="deepseek-ai/DeepSeek-V3"
)


def create_sql_agent(tools: List[Callable] = None) -> SubAgent:
    """
    创建 SQL Agent 实例
    
    Args:
        tools: 可选的工具列表，默认使用 SQLQueryTool
        
    Returns:
        配置好的 SQL SubAgent
    """
    agent = SQL_SUBAGENT
    
    if tools:
        agent.tools = tools
    else:
        # 默认工具
        from tools.code.llm_skill_tool import llm_skill
        from tools.sql.query_tool import sql_inter
        from tools.data.extract_tool import extract_data
        agent.tools = [llm_skill, sql_inter, extract_data]
    
    return agent
