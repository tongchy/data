"""工具基类模块

定义所有工具的基类和标准结果格式。
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
import logging

logger = logging.getLogger(__name__)


class ToolResult(BaseModel):
    """工具执行结果标准格式
    
    Attributes:
        success: 是否成功执行
        data: 返回数据
        message: 人类可读的消息
        error: 错误信息（如果有）
        metadata: 元数据
    """
    success: bool = Field(default=False, description="是否成功")
    data: Optional[Any] = Field(default=None, description="返回数据")
    message: str = Field(default="", description="人类可读消息")
    error: Optional[str] = Field(default=None, description="错误信息")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    
    def to_tool_message_content(self) -> str:
        """转换为 ToolMessage 的 content
        
        确保返回的内容符合硅基流动 API 的要求（非空字符串）。
        
        Returns:
            str: 适合作为 ToolMessage content 的字符串
        """
        if self.success:
            content = self.message or (str(self.data) if self.data is not None else "执行成功")
        else:
            content = f"执行失败：{self.error or '未知错误'}"
        
        # 确保不为空
        return content if content.strip() else "工具执行完成"


class BaseCustomTool(BaseTool, ABC):
    """自定义工具基类
    
    所有自定义工具都应该继承此类，以获得统一的执行结果格式和日志记录。
    
    Attributes:
        category: 工具类别
        version: 工具版本
        execution_count: 执行次数统计
    """
    
    # 工具元数据
    category: str = Field(default="general", description="工具类别")
    version: str = Field(default="1.0.0", description="工具版本")
    
    # 执行计数
    execution_count: int = Field(default=0, description="执行次数")
    
    def _run(self, *args, **kwargs) -> str:
        """同步执行工具
        
        子类应该实现 _execute 方法而不是直接覆盖此方法。
        
        Returns:
            str: 工具执行结果字符串
        """
        try:
            result = self._execute(*args, **kwargs)
            result = self.post_run_hook(result)
            return result.to_tool_message_content()
        except Exception as e:
            logger.error(f"Tool {self.name} execution failed: {e}")
            result = ToolResult(
                success=False,
                error=str(e),
                message=f"工具执行失败：{str(e)}"
            )
            return result.to_tool_message_content()
    
    async def _arun(self, *args, **kwargs) -> str:
        """异步执行工具
        
        默认实现调用同步版本，子类可以覆盖以实现真正的异步执行。
        """
        return self._run(*args, **kwargs)
    
    @abstractmethod
    def _execute(self, *args, **kwargs) -> ToolResult:
        """实际执行工具逻辑
        
        子类必须实现此方法。
        
        Returns:
            ToolResult: 工具执行结果
        """
        pass
    
    def post_run_hook(self, result: ToolResult) -> ToolResult:
        """执行后钩子
        
        确保返回值格式正确，记录执行统计。
        
        Args:
            result: 原始执行结果
            
        Returns:
            ToolResult: 处理后的结果
        """
        # 确保 content 不为空
        if not result.message and result.data is None:
            result.message = "工具执行完成"
        
        # 记录执行统计
        self.execution_count += 1
        
        # 记录日志
        logger.info(f"Tool {self.name} executed: success={result.success}")
        
        return result
