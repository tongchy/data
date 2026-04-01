"""数据库连接管理模块

提供数据库连接池管理和上下文管理器支持。
"""
import pymysql
from typing import Optional, List, Dict, Any, Tuple
from contextlib import contextmanager
import logging
from config.settings import get_settings

logger = logging.getLogger(__name__)


class DatabaseManager:
    """数据库连接管理器
    
    使用上下文管理器模式管理数据库连接，确保资源正确释放。
    
    Example:
        >>> with DatabaseManager() as db:
        ...     results = db.execute_query("SELECT * FROM users")
        ...     print(results)
    """
    
    def __init__(self, database: str = None):
        """初始化数据库管理器
        
        Args:
            database: 数据库名称，如果不指定则使用配置中的默认数据库
        """
        settings = get_settings()
        db_config = settings.database
        
        self.host = db_config.host
        self.port = db_config.port
        self.user = db_config.user
        self.password = db_config.password
        self.database = database or db_config.database
        self.charset = 'utf8'
        
        self._connection: Optional[pymysql.Connection] = None
    
    def connect(self) -> pymysql.Connection:
        """建立数据库连接
        
        Returns:
            pymysql.Connection: 数据库连接对象
            
        Raises:
            pymysql.Error: 连接失败时抛出
        """
        try:
            self._connection = pymysql.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                passwd=self.password,
                db=self.database,
                charset=self.charset,
                cursorclass=pymysql.cursors.DictCursor  # 返回字典格式
            )
            logger.debug(f"Connected to database: {self.database}")
            return self._connection
        except pymysql.Error as e:
            logger.error(f"Database connection failed: {e}")
            raise
    
    def close(self) -> None:
        """关闭数据库连接"""
        if self._connection:
            self._connection.close()
            self._connection = None
            logger.debug("Database connection closed")
    
    @contextmanager
    def cursor(self):
        """上下文管理器：自动管理 cursor
        
        Yields:
            pymysql.cursors.DictCursor: 数据库游标
            
        Example:
            >>> with db.cursor() as cursor:
            ...     cursor.execute("SELECT * FROM users")
            ...     results = cursor.fetchall()
        """
        if not self._connection:
            self.connect()
        
        cursor = self._connection.cursor()
        try:
            yield cursor
            self._connection.commit()
        except Exception as e:
            self._connection.rollback()
            logger.error(f"Database operation failed: {e}")
            raise
        finally:
            cursor.close()
    
    def execute_query(self, sql: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
        """执行查询并返回结果
        
        Args:
            sql: SQL 查询语句
            params: 查询参数（用于参数化查询）
            
        Returns:
            List[Dict[str, Any]]: 查询结果列表，每条记录是一个字典
        """
        with self.cursor() as cursor:
            cursor.execute(sql, params or ())
            return cursor.fetchall()
    
    def execute_update(self, sql: str, params: Optional[Tuple] = None) -> int:
        """执行更新操作并返回影响行数
        
        Args:
            sql: SQL 更新语句
            params: 查询参数
            
        Returns:
            int: 受影响的行数
        """
        with self.cursor() as cursor:
            affected = cursor.execute(sql, params or ())
            return affected
    
    def execute_scalar(self, sql: str, params: Optional[Tuple] = None) -> Any:
        """执行查询并返回单个值
        
        Args:
            sql: SQL 查询语句
            params: 查询参数
            
        Returns:
            Any: 查询结果的第一个字段值
        """
        with self.cursor() as cursor:
            cursor.execute(sql, params or ())
            result = cursor.fetchone()
            if result:
                return list(result.values())[0]
            return None
    
    def table_exists(self, table_name: str) -> bool:
        """检查表是否存在
        
        Args:
            table_name: 表名
            
        Returns:
            bool: 表是否存在
        """
        try:
            result = self.execute_query(
                f"SHOW TABLES LIKE %s",
                (table_name,)
            )
            return len(result) > 0
        except Exception:
            return False
    
    def get_table_count(self, table_name: str) -> int:
        """获取表的总记录数
        
        Args:
            table_name: 表名
            
        Returns:
            int: 记录数
        """
        try:
            count = self.execute_scalar(f"SELECT COUNT(*) FROM `{table_name}`")
            return count or 0
        except Exception:
            return 0
    
    def __enter__(self):
        """上下文管理器入口"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()
