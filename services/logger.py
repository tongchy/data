"""日志服务"""
import logging
import sys
from typing import Optional
from config.settings import get_settings


def setup_logger(
    name: str = "data_agent",
    level: Optional[str] = None,
    log_file: Optional[str] = None
) -> logging.Logger:
    """设置日志记录器
    
    Args:
        name: 日志记录器名称
        level: 日志级别
        log_file: 日志文件路径
        
    Returns:
        logging.Logger: 配置好的日志记录器
    """
    settings = get_settings()
    
    # 获取日志级别
    log_level = level or settings.log_level
    level_enum = getattr(logging, log_level.upper(), logging.INFO)
    
    # 创建日志记录器
    logger = logging.getLogger(name)
    logger.setLevel(level_enum)
    
    # 清除现有处理器
    logger.handlers = []
    
    # 创建格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level_enum)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 文件处理器（如果指定了日志文件）
    file_path = log_file or settings.log_file
    if file_path:
        file_handler = logging.FileHandler(file_path, encoding='utf-8')
        file_handler.setLevel(level_enum)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger
