"""
SubAgent Middleware - 子 Agent 中间件

提供子 Agent 派发机制，实现专业化分工和上下文隔离
"""

from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from langchain_core.runnables import RunnableConfig
import asyncio

from core.tool_compat import compatible_tool


@dataclass
class SubAgent:
    """
    子 Agent 定义
    
    Attributes:
        name: 子 Agent 名称
        description: 子 Agent 描述
        system_prompt: 系统提示词
        tools: 可用工具列表
        model: 使用的模型
    """
    name: str
    description: str
    system_prompt: str
    tools: List[Callable] = field(default_factory=list)
    model: str = "deepseek-ai/DeepSeek-V3"
    
    def to_tool_description(self) -> str:
        """转换为工具描述"""
        return f"""
{self.name}: {self.description}

职责:
{self.system_prompt[:200]}...

可用工具: {', '.join([t.__name__ if hasattr(t, '__name__') else str(t) for t in self.tools[:3]])}
""".strip()


class SubAgentMiddleware:
    """
    子 Agent 中间件
    
    管理子 Agent 的注册和派发，实现：
    - 专业化分工
    - 上下文隔离
    - 任务委派
    """
    
    def __init__(self, subagents: List[SubAgent]):
        """
        初始化子 Agent 中间件
        
        Args:
            subagents: 子 Agent 列表
        """
        self.subagents = {sa.name: sa for sa in subagents}
        self._results_cache: Dict[str, Any] = {}
        
    def get_tools(self) -> List[Callable]:
        """获取子 Agent 派发工具"""
        tools = []
        
        for name, subagent in self.subagents.items():
            tool_func = self._create_subagent_tool(subagent)
            tools.append(tool_func)
        
        # 添加任务管理工具
        tools.append(self._create_task_status_tool())
        
        return tools
    
    def _create_subagent_tool(self, subagent: SubAgent) -> Callable:
        """为子 Agent 创建派发工具"""
        
        @compatible_tool(
            name=f"delegate_to_{subagent.name}",
            description=f"""
委派任务给 {subagent.name}

{subagent.description}

使用场景:
- {subagent.name} 专门处理其专业领域的问题
- 需要将复杂任务分解给专业 Agent
- 需要隔离上下文环境

返回值:
- 子 Agent 的执行结果
- 结果通常保存在 /files/ 目录下
""".strip()
        )
        def delegate_task(
            task: str,
            context: Optional[Dict[str, Any]] = None,
            save_result_to: Optional[str] = None
        ) -> str:
            """
            委派任务给子 Agent
            
            Args:
                task: 任务描述
                context: 上下文信息（如相关文件路径、历史数据等）
                save_result_to: 结果保存路径（可选）
            """
            # 这里实际应该调用子 Agent 的执行逻辑
            # 简化版本：返回任务委派确认
            
            task_id = f"{subagent.name}_{hash(task) % 10000}"
            
            result = {
                "task_id": task_id,
                "subagent": subagent.name,
                "task": task,
                "status": "delegated",
                "context": context or {},
                "save_result_to": save_result_to
            }
            
            self._results_cache[task_id] = result
            
            # 模拟子 Agent 执行结果
            execution_result = self._simulate_subagent_execution(subagent, task, context)
            result["status"] = "completed"
            result["result"] = execution_result
            
            return f"""
✅ 任务已委派给 {subagent.name}

任务ID: {task_id}
任务: {task[:100]}...

执行结果:
{execution_result}

{f"结果已保存到: {save_result_to}" if save_result_to else ""}
""".strip()
        
        return delegate_task
    
    def _simulate_subagent_execution(
        self,
        subagent: SubAgent,
        task: str,
        context: Optional[Dict[str, Any]]
    ) -> str:
        """模拟子 Agent 执行（实际实现中应该调用真实的 Agent）"""
        
        # 根据子 Agent 类型返回不同的模拟结果
        if "sql" in subagent.name.lower():
            return f"""
SQL 查询专家已处理任务:
- 分析了查询需求
- 生成了优化 SQL
- 执行并验证结果
- 数据已保存到 /files/sql_result_*.json
""".strip()
        
        elif "data" in subagent.name.lower() or "analyst" in subagent.name.lower():
            return f"""
数据分析专家已处理任务:
- 读取了源数据
- 执行统计分析
- 生成数据洞察
- 结果已保存到 /files/analysis_*.json
""".strip()
        
        elif "viz" in subagent.name.lower() or "visual" in subagent.name.lower():
            return f"""
可视化专家已处理任务:
- 读取了分析结果
- 创建专业图表
- 保存为 PNG 格式
- 图表路径: images/chart_*.png
""".strip()
        
        else:
            return f"子 Agent {subagent.name} 已完成任务处理"
    
    def _create_task_status_tool(self) -> Callable:
        """创建任务状态查询工具"""
        
        @compatible_tool(
            name="check_task_status",
            description="查询已委派任务的状态和结果"
        )
        def check_task_status(task_id: str) -> str:
            """
            查询任务状态
            
            Args:
                task_id: 任务ID
            """
            if task_id not in self._results_cache:
                return f"❌ 未找到任务: {task_id}"
            
            result = self._results_cache[task_id]
            
            return f"""
任务状态: {result['status']}
任务ID: {task_id}
子 Agent: {result['subagent']}
任务: {result['task'][:100]}...

结果:
{result.get('result', '暂无结果')}
""".strip()
        
        return check_task_status
    
    def get_subagent_info(self) -> Dict[str, Any]:
        """获取所有子 Agent 信息"""
        return {
            name: {
                "description": sa.description,
                "tool_count": len(sa.tools),
                "model": sa.model
            }
            for name, sa in self.subagents.items()
        }


def create_subagent_middleware(subagents: List[SubAgent]) -> SubAgentMiddleware:
    """
    创建子 Agent 中间件（便捷函数）
    
    Args:
        subagents: 子 Agent 列表
        
    Returns:
        SubAgentMiddleware 实例
    """
    return SubAgentMiddleware(subagents)
