"""绘图工具

执行 Python 绘图代码并保存图像。
"""
from typing import Type
from pydantic import BaseModel, Field
from tools.base import BaseCustomTool, ToolResult
from tools.registry import registry
from config.settings import get_settings
import matplotlib
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import os
import logging

logger = logging.getLogger(__name__)


class PlotInput(BaseModel):
    """绘图输入参数"""
    py_code: str = Field(
        ...,
        description="要执行的 Python 绘图代码，必须使用 matplotlib/seaborn 创建图像并赋值给变量"
    )
    fname: str = Field(
        ...,
        description="图像对象的变量名，例如 'fig'，用于从代码中提取并保存为图片"
    )


class PlotTool(BaseCustomTool):
    """绘图工具
    
    执行 Python 绘图代码并将图像保存到磁盘。
    
    Features:
        - 支持 matplotlib 和 seaborn
        - 自动保存图像到指定目录
        - 返回相对路径供前端使用
    """
    
    name: str = "fig_inter"
    description: str = """
    当用户需要使用 Python 进行可视化绘图任务时，请调用该函数。
    
    注意事项：
    1. 所有绘图代码必须创建一个图像对象，并将其赋值为指定变量名（例如 `fig`）。
    2. 必须使用 `fig = plt.figure()` 或 `fig = plt.subplots()`。
    3. 不要使用 `plt.show()`。
    4. 请确保代码最后调用 `fig.tight_layout()`。
    5. 所有绘图代码中，坐标轴标签（xlabel、ylabel）、标题（title）、图例（legend）等文本内容，必须使用英文描述。
    
    示例代码：
    fig = plt.figure(figsize=(10,6))
    plt.plot([1,2,3], [4,5,6])
    fig.tight_layout()
    """
    category: str = "visualization"
    args_schema: Type[BaseModel] = PlotInput
    
    def _execute(self, py_code: str, fname: str) -> ToolResult:
        """执行绘图代码
        
        Args:
            py_code: Python 绘图代码
            fname: 图像变量名
            
        Returns:
            ToolResult: 执行结果，包含图片路径
        """
        # 保存当前后端并切换到非交互式后端
        current_backend = matplotlib.get_backend()
        matplotlib.use('Agg')
        
        # 准备执行环境
        local_vars = {
            "plt": plt,
            "pd": pd,
            "sns": sns,
        }
        
        # 添加已存储的 DataFrame
        import builtins
        store = getattr(builtins, '_agent_data_store', {})
        local_vars.update(store)
        
        # 获取图像保存路径
        settings = get_settings()
        base_dir = settings.image_base_dir
        images_dir = os.path.join(base_dir, "images")
        os.makedirs(images_dir, exist_ok=True)
        
        try:
            # 执行绘图代码
            exec(py_code, local_vars)
            
            # 获取图像对象
            fig = local_vars.get(fname)
            if not fig:
                return ToolResult(
                    success=False,
                    error=f"图像对象 '{fname}' 未找到，请确认变量名正确并为 matplotlib 图对象。"
                )
            
            # 保存图像
            image_filename = f"{fname}.png"
            abs_path = os.path.join(images_dir, image_filename)
            rel_path = os.path.join("images", image_filename)
            
            fig.savefig(abs_path, bbox_inches='tight', dpi=100)
            
            logger.info(f"Image saved: {abs_path}")
            
            return ToolResult(
                success=True,
                data={"path": rel_path, "abs_path": abs_path},
                message=f"图片已保存，路径为: {rel_path}",
                metadata={
                    "image_path": rel_path,
                    "absolute_path": abs_path,
                    "filename": image_filename
                }
            )
            
        except Exception as e:
            logger.error(f"Plot execution failed: {e}")
            return ToolResult(
                success=False,
                error=f"绘图执行失败：{str(e)}"
            )
        finally:
            # 清理
            plt.close('all')
            matplotlib.use(current_backend)


# 全局工具实例（兼容旧版导入）
fig_inter = PlotTool()
registry.register(fig_inter)
