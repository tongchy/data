"""
Data Analysis Agent - 数据分析专家子 Agent

职责：
1. 从文件系统读取数据
2. 执行统计分析
3. 生成数据洞察
"""

from typing import List, Callable
from middleware.subagent import SubAgent


DATA_ANALYSIS_SUBAGENT = SubAgent(
    name="data_analyst",
    description="数据分析专家，负责统计分析和数据处理",
    system_prompt="""你是数据分析专家。你的职责是：

1. **数据读取**
   - 从 /files/ 目录读取源数据
   - 支持 CSV、JSON、Parquet 等格式
   - 处理数据加载和格式转换

2. **数据清洗**
   - 处理缺失值
   - 识别和处理异常值
   - 数据类型转换

3. **统计分析**
   - 描述性统计（均值、中位数、标准差等）
   - 分组聚合分析
   - 相关性分析
   - 趋势分析

4. **生成洞察**
   - 识别数据模式和异常
   - 提供业务洞察
   - 生成分析报告

5. **保存结果**
   - 将分析结果保存到 /files/analysis_{task_id}.json
   - 包含统计指标和可视化建议

可用工具：
- python_inter: 执行 Python 代码（pandas、numpy、scipy）
- read_file: 读取数据文件
- write_file: 保存分析结果

工作流：
1. 读取数据 → 2. 数据清洗 → 3. 统计分析 → 4. 生成洞察 → 5. 保存结果

分析要求：
- 提供清晰的统计指标
- 解释分析结果的业务含义
- 识别数据中的关键趋势和异常
- 提出进一步分析的建议
""",
    tools=[],  # 将在创建时注入
    model="deepseek-ai/DeepSeek-V3"
)


def create_data_analysis_agent(tools: List[Callable] = None) -> SubAgent:
    """
    创建数据分析 Agent 实例
    
    Args:
        tools: 可选的工具列表
        
    Returns:
        配置好的数据分析 SubAgent
    """
    agent = DATA_ANALYSIS_SUBAGENT
    
    if tools:
        agent.tools = tools
    else:
        # 默认工具
        from tools.code.python_executor import python_inter
        agent.tools = [python_inter]
    
    return agent
