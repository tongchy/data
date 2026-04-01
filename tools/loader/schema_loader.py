"""表结构加载器 - L1 层

实现表结构和语义的动态加载，优化 SQL 生成准确率。
"""
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from pydantic import Field
import logging
import json

from tools.base import BaseCustomTool, ToolResult
from database.connection import DatabaseManager

logger = logging.getLogger(__name__)


@dataclass
class ColumnInfo:
    """列信息"""
    name: str
    data_type: str
    description: str = ""
    is_nullable: bool = True
    is_primary_key: bool = False
    foreign_key: Optional[str] = None  # 格式: "table.column"
    sample_values: List[Any] = field(default_factory=list)
    
    def to_prompt_text(self) -> str:
        """转换为提示词文本"""
        constraints = []
        if self.is_primary_key:
            constraints.append("主键")
        if not self.is_nullable:
            constraints.append("非空")
        if self.foreign_key:
            constraints.append(f"外键->{self.foreign_key}")
        
        constraint_str = f" [{', '.join(constraints)}]" if constraints else ""
        desc_str = f" - {self.description}" if self.description else ""
        sample_str = f" 示例值: {self.sample_values[:3]}" if self.sample_values else ""
        
        return f"  - {self.name}: {self.data_type}{constraint_str}{desc_str}{sample_str}"


@dataclass
class TableSchema:
    """表结构信息"""
    name: str
    description: str = ""
    columns: List[ColumnInfo] = field(default_factory=list)
    row_count: int = 0
    related_tables: List[str] = field(default_factory=list)
    common_queries: List[str] = field(default_factory=list)
    
    def to_prompt_text(self, include_columns: bool = True) -> str:
        """转换为提示词文本
        
        Args:
            include_columns: 是否包含列信息
            
        Returns:
            str: 表结构描述文本
        """
        lines = [f"表名: {self.name}"]
        
        if self.description:
            lines.append(f"描述: {self.description}")
        
        lines.append(f"数据量: 约 {self.row_count} 行")
        
        if include_columns and self.columns:
            lines.append("字段:")
            for col in self.columns:
                lines.append(col.to_prompt_text())
        
        if self.related_tables:
            lines.append(f"关联表: {', '.join(self.related_tables)}")
        
        return "\n".join(lines)
    
    def get_column_names(self) -> List[str]:
        """获取所有列名"""
        return [col.name for col in self.columns]
    
    def get_column(self, name: str) -> Optional[ColumnInfo]:
        """获取指定列信息"""
        for col in self.columns:
            if col.name.lower() == name.lower():
                return col
        return None


class SchemaLoader(BaseCustomTool):
    """表结构加载器 - L1 层核心组件
    
    动态加载表结构和语义信息，实现：
    1. 按需加载：只加载查询中提到的表
    2. 语义丰富：包含列描述、示例值、关联关系
    3. 缓存优化：缓存已加载的 schema
    
    Attributes:
        name: 工具名称
        description: 工具描述
        category: 工具类别
    """
    
    name: str = "schema_loader"
    description: str = """加载表结构和语义信息。用于获取数据库表的字段定义、数据类型、关联关系等。
    
    使用此工具来：
    1. 获取指定表的完整结构信息
    2. 了解表之间的关联关系
    3. 获取字段的示例值和描述
    
    参数：
    - table_names: 表名列表（字符串或列表）
    - include_sample: 是否包含示例值（默认 True）
    - refresh: 是否刷新缓存（默认 False）
    """
    category: str = "loader"
    version: str = "1.0.0"
    
    # Schema 缓存
    _schema_cache: Dict[str, TableSchema] = {}
    # 加载统计
    _load_count: int = 0
    _cache_hit_count: int = 0
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 预定义一些常见表结构（实际项目中应从数据库读取）
        self._init_default_schemas()
    
    def _init_default_schemas(self):
        """初始化默认表结构（示例数据）"""
        # 示例：订单表
        self._schema_cache["orders"] = TableSchema(
            name="orders",
            description="订单主表，存储所有订单信息",
            columns=[
                ColumnInfo(name="order_id", data_type="INT", description="订单ID", is_primary_key=True),
                ColumnInfo(name="customer_id", data_type="INT", description="客户ID", foreign_key="customers.customer_id"),
                ColumnInfo(name="order_date", data_type="DATETIME", description="订单日期"),
                ColumnInfo(name="total_amount", data_type="DECIMAL(10,2)", description="订单总金额"),
                ColumnInfo(name="status", data_type="VARCHAR(20)", description="订单状态", sample_values=["pending", "paid", "shipped", "completed"]),
            ],
            row_count=100000,
            related_tables=["customers", "order_items"],
            common_queries=[
                "SELECT * FROM orders WHERE order_date > '2024-01-01'",
                "SELECT status, COUNT(*) FROM orders GROUP BY status"
            ]
        )
        
        # 示例：客户表
        self._schema_cache["customers"] = TableSchema(
            name="customers",
            description="客户信息表",
            columns=[
                ColumnInfo(name="customer_id", data_type="INT", description="客户ID", is_primary_key=True),
                ColumnInfo(name="name", data_type="VARCHAR(100)", description="客户姓名"),
                ColumnInfo(name="email", data_type="VARCHAR(100)", description="邮箱地址"),
                ColumnInfo(name="phone", data_type="VARCHAR(20)", description="电话号码"),
                ColumnInfo(name="created_at", data_type="DATETIME", description="注册时间"),
            ],
            row_count=50000,
            related_tables=["orders"]
        )
        
        # 示例：订单明细表
        self._schema_cache["order_items"] = TableSchema(
            name="order_items",
            description="订单明细表，存储订单中的商品信息",
            columns=[
                ColumnInfo(name="item_id", data_type="INT", description="明细ID", is_primary_key=True),
                ColumnInfo(name="order_id", data_type="INT", description="订单ID", foreign_key="orders.order_id"),
                ColumnInfo(name="product_id", data_type="INT", description="商品ID", foreign_key="products.product_id"),
                ColumnInfo(name="quantity", data_type="INT", description="数量"),
                ColumnInfo(name="unit_price", data_type="DECIMAL(10,2)", description="单价"),
            ],
            row_count=300000,
            related_tables=["orders", "products"]
        )
        
        # 示例：商品表
        self._schema_cache["products"] = TableSchema(
            name="products",
            description="商品信息表",
            columns=[
                ColumnInfo(name="product_id", data_type="INT", description="商品ID", is_primary_key=True),
                ColumnInfo(name="name", data_type="VARCHAR(200)", description="商品名称"),
                ColumnInfo(name="category", data_type="VARCHAR(50)", description="商品分类", sample_values=["电子产品", "服装", "食品", "家居"]),
                ColumnInfo(name="price", data_type="DECIMAL(10,2)", description="商品价格"),
                ColumnInfo(name="stock", data_type="INT", description="库存数量"),
            ],
            row_count=10000,
            related_tables=["order_items"]
        )
    
    def load_schema(
        self,
        table_name: str,
        include_sample: bool = True,
        refresh: bool = False
    ) -> Optional[TableSchema]:
        """加载表结构
        
        Args:
            table_name: 表名
            include_sample: 是否包含示例值
            refresh: 是否刷新缓存
            
        Returns:
            Optional[TableSchema]: 表结构信息
        """
        self._load_count += 1
        
        # 检查缓存
        if not refresh and table_name in self._schema_cache:
            self._cache_hit_count += 1
            logger.debug(f"Schema cache hit for table: {table_name}")
            return self._schema_cache[table_name]
        
        # 尝试从数据库加载
        try:
            schema = self._load_from_database(table_name, include_sample)
            if schema:
                self._schema_cache[table_name] = schema
                logger.info(f"Loaded schema for table: {table_name}")
                return schema
        except Exception as e:
            logger.warning(f"Failed to load schema from database for {table_name}: {e}")
        
        # 如果缓存中有，返回缓存版本
        if table_name in self._schema_cache:
            return self._schema_cache[table_name]
        
        return None
    
    def _load_from_database(
        self,
        table_name: str,
        include_sample: bool
    ) -> Optional[TableSchema]:
        """从数据库加载表结构
        
        Args:
            table_name: 表名
            include_sample: 是否包含示例值
            
        Returns:
            Optional[TableSchema]: 表结构信息
        """
        try:
            with DatabaseManager() as db:
                # 获取列信息
                columns_query = """
                    SELECT 
                        COLUMN_NAME,
                        DATA_TYPE,
                        IS_NULLABLE,
                        COLUMN_COMMENT
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME = %s
                    ORDER BY ORDINAL_POSITION
                """
                columns_data = db.execute_query(columns_query, (table_name,))
                
                if not columns_data:
                    return None
                
                columns = []
                for col_data in columns_data:
                    col = ColumnInfo(
                        name=col_data['COLUMN_NAME'],
                        data_type=col_data['DATA_TYPE'],
                        description=col_data.get('COLUMN_COMMENT', ''),
                        is_nullable=col_data['IS_NULLABLE'] == 'YES'
                    )
                    
                    # 获取示例值
                    if include_sample:
                        sample_query = f"""
                            SELECT DISTINCT {col.name} 
                            FROM {table_name} 
                            WHERE {col.name} IS NOT NULL 
                            LIMIT 5
                        """
                        try:
                            samples = db.execute_query(sample_query)
                            col.sample_values = [s[col.name] for s in samples if col.name in s]
                        except:
                            pass
                    
                    columns.append(col)
                
                # 获取表信息
                table_query = """
                    SELECT 
                        TABLE_ROWS,
                        TABLE_COMMENT
                    FROM INFORMATION_SCHEMA.TABLES
                    WHERE TABLE_NAME = %s
                """
                table_data = db.execute_query(table_query, (table_name,))
                
                row_count = table_data[0]['TABLE_ROWS'] if table_data else 0
                description = table_data[0]['TABLE_COMMENT'] if table_data else ""
                
                return TableSchema(
                    name=table_name,
                    description=description,
                    columns=columns,
                    row_count=row_count
                )
                
        except Exception as e:
            logger.error(f"Database schema loading failed: {e}")
            return None
    
    def load_schemas(
        self,
        table_names: List[str],
        include_sample: bool = True,
        refresh: bool = False
    ) -> Dict[str, TableSchema]:
        """批量加载表结构
        
        Args:
            table_names: 表名列表
            include_sample: 是否包含示例值
            refresh: 是否刷新缓存
            
        Returns:
            Dict[str, TableSchema]: 表结构字典
        """
        result = {}
        for name in table_names:
            schema = self.load_schema(name, include_sample, refresh)
            if schema:
                result[name] = schema
        return result
    
    def get_related_tables(self, table_name: str, depth: int = 1) -> List[str]:
        """获取关联表
        
        Args:
            table_name: 起始表名
            depth: 递归深度
            
        Returns:
            List[str]: 关联表名列表
        """
        schema = self._schema_cache.get(table_name)
        if not schema:
            return []
        
        related = set(schema.related_tables)
        
        if depth > 1:
            for rel_table in list(related):
                rel_schema = self._schema_cache.get(rel_table)
                if rel_schema:
                    related.update(rel_schema.related_tables)
        
        return list(related - {table_name})
    
    def generate_schema_prompt(
        self,
        table_names: List[str],
        include_related: bool = True
    ) -> str:
        """生成 Schema 提示词
        
        将表结构信息转换为适合注入到 System Message 的文本。
        
        Args:
            table_names: 表名列表
            include_related: 是否包含关联表
            
        Returns:
            str: Schema 提示词文本
        """
        all_tables = set(table_names)
        
        if include_related:
            for table in table_names:
                all_tables.update(self.get_related_tables(table))
        
        schemas = self.load_schemas(list(all_tables))
        
        if not schemas:
            return ""
        
        sections = ["## 数据库表结构信息\n"]
        
        for name in sorted(schemas.keys()):
            schema = schemas[name]
            sections.append(schema.to_prompt_text())
            sections.append("")  # 空行分隔
        
        # 添加使用提示
        sections.append("## SQL 编写提示")
        sections.append("- 使用表名和字段名时请参考上述结构")
        sections.append("- 注意字段的数据类型和约束条件")
        sections.append("- 关联查询时使用正确的外键关系")
        
        return "\n".join(sections)
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        total = self._load_count
        hits = self._cache_hit_count
        hit_rate = (hits / total * 100) if total > 0 else 0
        
        return {
            "total_loads": total,
            "cache_hits": hits,
            "cache_misses": total - hits,
            "hit_rate": round(hit_rate, 1),
            "cached_tables": list(self._schema_cache.keys())
        }
    
    def clear_cache(self):
        """清空缓存"""
        self._schema_cache.clear()
        self._init_default_schemas()
        logger.info("Schema cache cleared")
    
    def _execute(
        self,
        table_names: Any,  # 可以是字符串或列表
        include_sample: bool = True,
        refresh: bool = False
    ) -> ToolResult:
        """执行 schema 加载
        
        Args:
            table_names: 表名（字符串或列表）
            include_sample: 是否包含示例值
            refresh: 是否刷新缓存
            
        Returns:
            ToolResult: 加载结果
        """
        try:
            # 统一处理为列表
            if isinstance(table_names, str):
                table_names = [t.strip() for t in table_names.split(',')]
            elif not isinstance(table_names, list):
                table_names = [str(table_names)]
            
            # 加载 schema
            schemas = self.load_schemas(table_names, include_sample, refresh)
            
            if not schemas:
                return ToolResult(
                    success=False,
                    error=f"无法加载表结构: {table_names}",
                    message=f"未找到以下表的结构信息: {', '.join(table_names)}"
                )
            
            # 生成提示词
            prompt_text = self.generate_schema_prompt(list(schemas.keys()))
            
            # 获取统计
            stats = self.get_cache_stats()
            
            message = f"""成功加载 {len(schemas)} 个表的 schema：

{prompt_text}

缓存统计：
- 缓存命中率: {stats['hit_rate']}%
- 已缓存表: {', '.join(stats['cached_tables'])}
"""
            
            return ToolResult(
                success=True,
                data={
                    "schemas": {name: schema.to_prompt_text() for name, schema in schemas.items()},
                    "cache_stats": stats
                },
                message=message
            )
            
        except Exception as e:
            logger.error(f"Schema loading failed: {e}")
            return ToolResult(
                success=False,
                error=str(e),
                message=f"表结构加载失败: {str(e)}"
            )


# 全局 schema 加载器实例
schema_loader = SchemaLoader()
