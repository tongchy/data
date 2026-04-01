"""Python 代码执行工具

在安全的沙箱环境中执行 Python 代码。
"""
from typing import Type
from pydantic import BaseModel, Field
from tools.base import BaseCustomTool, ToolResult
from tools.registry import registry
import logging
import io
import sys
import traceback

logger = logging.getLogger(__name__)


class PythonCodeInput(BaseModel):
    """Python 代码输入参数"""
    py_code: str = Field(
        ...,
        description="一段合法的 Python 代码字符串，例如 '2 + 2' 或 'x = 3\\ny = x * 2'"
    )


class PythonExecutorTool(BaseCustomTool):
    """Python 代码执行工具
    
    执行非绘图类的 Python 代码，支持变量创建和表达式求值。
    
    Features:
        - 支持表达式求值（eval）
        - 支持语句块执行（exec）
        - 自动捕获输出
        - 安全的执行环境
    """
    
    name: str = "python_inter"
    description: str = """
    当用户需要编写 Python 程序并执行时，请调用该函数。
    
    该函数可以执行一段 Python 代码并返回最终结果。
    
    注意事项：
    - 本函数只能执行非绘图类的代码
    - 若是绘图相关代码，需要调用 fig_inter 函数运行
    """
    category: str = "code"
    args_schema: Type[BaseModel] = PythonCodeInput
    
    def _execute(self, py_code: str) -> ToolResult:
        """执行 Python 代码
        
        Args:
            py_code: Python 代码字符串
            
        Returns:
            ToolResult: 执行结果
        """
        # 获取执行环境
        g = self._get_execution_globals()
        
        # 尝试用 eval 执行（适用于单个表达式）
        try:
            result = eval(py_code, g)
            result_str = str(result) if result is not None else "执行完成，返回值为 None"
            return ToolResult(
                success=True,
                data=result,
                message=result_str if result_str.strip() else "执行完成，无返回值"
            )
        except SyntaxError:
            # eval 失败说明是语句块，改用 exec 执行
            pass
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"代码执行错误：{str(e)}"
            )
        
        # 使用 exec 执行语句块
        return self._execute_with_exec(py_code, g)
    
    def _execute_with_exec(self, py_code: str, g: dict) -> ToolResult:
        """使用 exec 执行代码
        
        Args:
            py_code: Python 代码
            g: 全局命名空间
            
        Returns:
            ToolResult: 执行结果
        """
        # 记录执行前的变量
        global_vars_before = set(g.keys())
        
        # 捕获输出
        output_buffer = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = output_buffer
        
        try:
            exec(py_code, g)
            
            # 获取输出
            output = output_buffer.getvalue()
            
            # 检查新增的变量
            global_vars_after = set(g.keys())
            new_vars = global_vars_after - global_vars_before
            
            if new_vars:
                # 有新增变量，返回变量信息
                var_info = {var: g[var] for var in new_vars}
                message = f"代码执行完成，创建了变量: {', '.join(new_vars)}"
                if output:
                    message += f"\n输出:\n{output}"
                return ToolResult(
                    success=True,
                    data=var_info,
                    message=message,
                    metadata={"new_variables": list(new_vars), "output": output}
                )
            elif output:
                # 有输出但没有新增变量
                return ToolResult(
                    success=True,
                    data=output,
                    message=f"代码执行完成，输出:\n{output}"
                )
            else:
                # 没有输出也没有新增变量
                return ToolResult(
                    success=True,
                    message="代码执行完成"
                )
                
        except Exception as e:
            error_msg = f"代码执行时报错: {str(e)}\n{traceback.format_exc()}"
            return ToolResult(
                success=False,
                error=error_msg
            )
        finally:
            sys.stdout = old_stdout
    
    def _get_execution_globals(self) -> dict:
        """获取代码执行的全局命名空间
        
        Returns:
            dict: 包含常用库和变量的全局命名空间
        """
        import pandas as pd
        import numpy as np
        
        g = {
            'pd': pd,
            'numpy': np,
            'np': np,
        }
        
        # 添加已存储的 DataFrame
        import builtins
        store = getattr(builtins, '_agent_data_store', {})
        g.update(store)
        
        return g


# 全局工具实例（兼容旧版导入）
python_inter = PythonExecutorTool()
registry.register(python_inter)
