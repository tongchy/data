"""数据提取工具

从 MySQL 数据库提取数据到 pandas DataFrame。
"""
from typing import Type
from pydantic import BaseModel, Field
from tools.base import BaseCustomTool, ToolResult
from database.connection import DatabaseManager
from tools.registry import registry
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class ExtractDataInput(BaseModel):
    """数据提取输入参数"""
    sql_query: str = Field(
        ...,
        description="用于从 MySQL 提取数据的 SQL 查询语句。"
    )
    df_name: str = Field(
        ...,
        description="指定用于保存结果的 pandas 变量名称（字符串形式）。"
    )


class DataExtractTool(BaseCustomTool):
    """数据提取工具
    
    将 MySQL 数据库中的数据提取到 Python 环境中的 pandas DataFrame。
    
    Features:
        - 自动将数据转换为 pandas DataFrame
        - 支持复杂的 SQL 查询
        - 数据存储在全局命名空间中供后续使用
    """
    
    name: str = "extract_data"
    description: str = """
    用于在 MySQL 数据库中提取一张表到当前 Python 环境中。
    
    适用场景：
    - 将数据库数据加载到 pandas 进行后续分析
    - 提取特定条件的数据子集
    
    注意事项：
    - 本函数只负责数据表的提取，并不负责数据查询
    - 若需要在 MySQL 中进行数据查询，请使用 sql_inter 函数
    """
    category: str = "data"
    args_schema: Type[BaseModel] = ExtractDataInput
    
    def _execute(self, sql_query: str, df_name: str) -> ToolResult:
        """执行数据提取
        
        Args:
            sql_query: SQL 查询语句
            df_name: DataFrame 变量名
            
        Returns:
            ToolResult: 提取结果
        """
        try:
            with DatabaseManager() as connection:
                # pandas.read_sql：直接将 SQL 查询结果读取为 DataFrame
                df = pd.read_sql(sql_query, connection._connection)
                
                # 将 DataFrame 以指定名称存入全局变量
                import builtins
                if not hasattr(builtins, '_agent_data_store'):
                    builtins._agent_data_store = {}
                builtins._agent_data_store[df_name] = df
                
                # 同时存入 globals() 以保持向后兼容
                import __main__
                setattr(__main__, df_name, df)
                
                message = f"成功创建 pandas 对象 '{df_name}'，形状为 {df.shape}，包含从 MySQL 提取的数据。"
                
                logger.info(f"Data extracted: {df_name} with shape {df.shape}")
                
                return ToolResult(
                    success=True,
                    data={"shape": df.shape, "columns": list(df.columns)},
                    message=message,
                    metadata={
                        "df_name": df_name,
                        "row_count": len(df),
                        "column_count": len(df.columns),
                        "columns": list(df.columns)
                    }
                )
                
        except Exception as e:
            logger.error(f"Data extraction failed: {e}")
            return ToolResult(
                success=False,
                error=f"数据提取失败：{str(e)}"
            )


def get_dataframe(name: str) -> pd.DataFrame:
    """获取已存储的 DataFrame
    
    Args:
        name: DataFrame 变量名
        
    Returns:
        pd.DataFrame: DataFrame 对象
        
    Raises:
        KeyError: 如果不存在该 DataFrame
    """
    import builtins
    store = getattr(builtins, '_agent_data_store', {})
    if name not in store:
        raise KeyError(f"DataFrame '{name}' not found")
    return store[name]


# 全局工具实例（兼容旧版导入）
extract_data = DataExtractTool()
registry.register(extract_data)
