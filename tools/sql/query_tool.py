"""SQL 查询工具

提供安全的数据库查询功能，支持空结果诊断。
"""
from typing import Type
from pydantic import BaseModel, Field
from tools.base import BaseCustomTool, ToolResult
from database.connection import DatabaseManager
from tools.registry import registry
import logging
import re

logger = logging.getLogger(__name__)


class SQLQueryInput(BaseModel):
    """SQL 查询输入参数"""
    sql_query: str = Field(
        ...,
        description="SQL 查询语句，例如：SELECT * FROM table_name WHERE condition"
    )


class SQLQueryTool(BaseCustomTool):
    """SQL 查询工具
    
    用于在 MySQL 数据库中执行 SQL 查询，支持空结果诊断。
    
    Features:
        - 只支持 SELECT 查询，防止数据修改
        - 自动截断超过 1000 条的结果
        - 空结果时提供详细诊断信息
    """
    
    name: str = "sql_inter"
    description: str = """
    用于在 MySQL 数据库中执行 SQL 查询。
    适用场景：
    - 查询数据库表中的数据
    - 执行统计分析
    - 获取元数据信息
    
    注意事项：
    - 只支持 SELECT 查询，不支持修改数据的操作
    - 查询结果超过 1000 条时会自动截断
    """
    category: str = "sql"
    args_schema: Type[BaseModel] = SQLQueryInput
    
    max_results: int = 1000  # 最大返回结果数
    
    def _execute(self, sql_query: str) -> ToolResult:
        """执行 SQL 查询
        
        Args:
            sql_query: SQL 查询语句
            
        Returns:
            ToolResult: 查询结果
        """
        # SQL 安全检查
        if not self._is_safe_query(sql_query):
            return ToolResult(
                success=False,
                error="SQL 语句包含危险操作，只允许 SELECT 查询"
            )
        
        try:
            with DatabaseManager() as db:
                # 执行查询
                results = db.execute_query(sql_query)
                
                # 处理空结果
                if not results:
                    diagnosis = self._diagnose_empty_result(sql_query, db)
                    return ToolResult(
                        success=True,
                        data=[],
                        message=f"查询执行成功，但未找到匹配记录。\n{diagnosis}",
                        metadata={"diagnosis": diagnosis}
                    )
                
                # 限制结果数量
                total_count = len(results)
                if total_count > self.max_results:
                    results = results[:self.max_results]
                    message = f"查询到 {total_count} 条记录，返回前 {self.max_results} 条"
                    truncated = True
                else:
                    message = f"查询成功，共返回 {total_count} 条记录"
                    truncated = False
                
                return ToolResult(
                    success=True,
                    data=results,
                    message=message,
                    metadata={
                        "total_count": total_count,
                        "returned_count": len(results),
                        "truncated": truncated
                    }
                )
        
        except Exception as e:
            logger.error(f"SQL query failed: {e}")
            return ToolResult(
                success=False,
                error=f"SQL 执行失败：{str(e)}"
            )
    
    def _is_safe_query(self, sql: str) -> bool:
        """SQL 安全检查：只允许 SELECT
        
        Args:
            sql: SQL 语句
            
        Returns:
            bool: 是否安全
        """
        sql_upper = sql.strip().upper()
        
        # 禁止的操作
        forbidden_keywords = ['INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER', 'TRUNCATE']
        
        # 检查是否包含禁止操作
        for keyword in forbidden_keywords:
            if re.search(rf'\b{keyword}\b', sql_upper):
                logger.warning(f"Forbidden SQL operation detected: {keyword}")
                return False
        
        # 检查是否以 SELECT 或 WITH 开头
        if not (sql_upper.startswith('SELECT') or sql_upper.startswith('WITH')):
            return False
        
        return True
    
    def _diagnose_empty_result(self, sql_query: str, db: DatabaseManager) -> str:
        """诊断空结果原因
        
        分析为什么查询返回空结果，提供详细的诊断信息。
        
        Args:
            sql_query: 原始 SQL 查询
            db: 数据库管理器
            
        Returns:
            str: 诊断信息
        """
        diagnosis = []
        
        # 提取表名
        table_match = re.search(r'FROM\s+`?(\w+)`?', sql_query, re.IGNORECASE)
        if table_match:
            table_name = table_match.group(1)
            
            # 检查表是否存在
            if not db.table_exists(table_name):
                return f"原因：表 '{table_name}' 不存在，请检查表名是否正确。"
            
            diagnosis.append(f"✓ 表 '{table_name}' 存在")
            
            # 检查表总记录数
            total = db.get_table_count(table_name)
            diagnosis.append(f"✓ 表 '{table_name}' 共有 {total} 条记录")
            
            # 如果有 WHERE 条件，分析条件
            where_match = re.search(r'WHERE\s+(.+?)(?:ORDER|GROUP|LIMIT|$)', sql_query, re.IGNORECASE | re.DOTALL)
            if where_match and total > 0:
                where_clause = where_match.group(1).strip()
                diagnosis.append(f"\nWHERE 条件分析：")
                diagnosis.append(f"  条件: {where_clause}")
                
                # 尝试分别检查每个 LIKE 条件
                like_conditions = re.findall(r'(\w+)\s+LIKE\s+[\'\"]([^\'\"]+)[\'\"]', where_clause, re.IGNORECASE)
                if like_conditions:
                    diagnosis.append("\n  各字段匹配情况：")
                    for field, pattern in like_conditions:
                        try:
                            match_count = db.execute_scalar(
                                f"SELECT COUNT(*) FROM `{table_name}` WHERE `{field}` LIKE %s",
                                (f'%{pattern}%',)
                            )
                            if match_count == 0:
                                diagnosis.append(f"    ✗ 字段 '{field}' 包含 '{pattern}' 的记录: 0 条（无匹配）")
                            else:
                                diagnosis.append(f"    ✓ 字段 '{field}' 包含 '{pattern}' 的记录: {match_count} 条")
                        except Exception as e:
                            diagnosis.append(f"    ? 字段 '{field}' 检查失败：{str(e)}")
                
                diagnosis.append("\n建议：")
                diagnosis.append("  - 检查 WHERE 条件中的值是否正确")
                diagnosis.append("  - 尝试使用更宽泛的条件（如减少 AND 条件）")
                field_name = list(like_conditions)[0][0] if like_conditions else "字段名"
                diagnosis.append(f"  - 使用 'SELECT DISTINCT {field_name} FROM {table_name}' 查看可用值")
        
        return "\n".join(diagnosis)


# 全局工具实例（兼容旧版导入）
sql_inter = SQLQueryTool()
registry.register(sql_inter)
