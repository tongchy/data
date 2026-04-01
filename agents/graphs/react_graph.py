"""ReAct Agent 图定义

创建基于 ReAct 模式的 LangGraph Agent。
"""
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage
from typing import List
import os
import logging

from config.settings import get_settings
from tools.registry import registry

logger = logging.getLogger(__name__)


# 系统提示词
SYSTEM_PROMPT = """
你是一名经验丰富的智能数据分析助手，擅长帮助用户高效完成以下任务：

1. **数据库查询：**
   - 当用户需要获取数据库中某些数据或进行 SQL 查询时，请调用 `sql_inter` 工具。
   - 你需要准确根据用户请求生成 SQL 语句。

2. **数据表提取：**
   - 当用户希望将数据库中的表格导入 Python 环境进行后续分析时，请调用 `extract_data` 工具。
   - 你需要根据用户提供的表名或查询条件生成 SQL 查询语句，并将数据保存到指定的 pandas 变量中。

3. **非绘图类任务的 Python 代码执行：**
   - 当用户需要执行 Python 脚本或进行数据处理、统计计算时，请调用 `python_inter` 工具。
   - 仅限执行非绘图类代码，例如变量定义、数据分析等。

4. **绘图类 Python 代码执行：**
   - 当用户需要进行可视化展示（如生成图表、绘制分布等）时，请调用 `fig_inter` 工具。
   - 你应根据用户需求编写绘图代码，并正确指定绘图对象变量名（如 `fig`）。
   - 当你生成 Python 绘图代码时必须指明图像的名称，如 `fig = plt.figure()` 或 `fig = plt.subplots()` 创建图像对象。
   - 不要调用 `plt.show()`，否则图像将无法保存。

**工具使用优先级：**
- 如需数据库数据，请先使用 `sql_inter` 或 `extract_data` 获取，再执行 Python 分析或绘图。
- 如需绘图，请先确保数据已加载为 pandas 对象。

**回答要求：**
- 所有回答均使用**简体中文**，清晰、礼貌、简洁。
- 如果调用工具返回结构化数据，你应提取其中的关键信息简要说明，并展示主要结果。
- 若需要用户提供更多信息，请主动提出明确的问题。
- 如果有生成的图片文件，请务必在回答中使用 Markdown 格式插入图片，如：`![图表描述](images/fig.png)`
- 不要仅输出图片路径文字。

**风格：**
- 专业、简洁、以数据驱动。
- 不要编造不存在的工具或数据。

请根据以上原则为用户提供精准、高效的协助。
"""


def create_data_agent_graph(
    tools: List = None,
    prompt: str = None,
    model=None
):
    """创建数据分析 Agent 图
    
    创建基于 ReAct 模式的 LangGraph Agent。
    
    Args:
        tools: 工具列表，如果不指定则使用注册中心中的所有工具
        prompt: 系统提示词，如果不指定则使用默认提示词
        model: 语言模型，如果不指定则使用配置中的默认模型
        
    Returns:
        CompiledGraph: 编译后的 LangGraph 图
    """
    settings = get_settings()
    
    # 获取工具
    if tools is None:
        tools = registry.get_all()
        logger.info(f"Using {len(tools)} registered tools")
    
    # 获取提示词
    if prompt is None:
        prompt = SYSTEM_PROMPT
    
    # 创建模型
    if model is None:
        model = ChatOpenAI(
            model=settings.model.model_name,
            api_key=settings.model.api_key or os.getenv("SILICONFLOW_API_KEY"),
            base_url=settings.model.base_url,
            temperature=settings.model.temperature,
            max_tokens=settings.model.max_tokens,
            timeout=settings.model.timeout
        )
    
    # 创建 ReAct Agent
    graph = create_react_agent(
        model=model,
        tools=tools,
        prompt=prompt,
        name="data_agent"
    )
    
    logger.info("Data agent graph created successfully")
    
    return graph
