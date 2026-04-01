"""数据库初始化脚本"""
import argparse
import logging
from database.connection import DatabaseManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_database():
    """初始化数据库"""
    logger.info("Initializing database...")
    
    with DatabaseManager() as db:
        # 测试连接
        result = db.execute_query("SELECT VERSION()")
        version = result[0] if result else "Unknown"
        logger.info(f"MySQL version: {version}")
        
        # 列出所有表
        tables = db.execute_query("SHOW TABLES")
        logger.info(f"Found {len(tables)} tables")
        for table in tables:
            logger.info(f"  - {list(table.values())[0]}")
    
    logger.info("Database initialization completed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Database setup script")
    parser.add_argument("--init", action="store_true", help="Initialize database")
    args = parser.parse_args()
    
    if args.init:
        init_database()
    else:
        parser.print_help()
