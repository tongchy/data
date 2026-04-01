"""配置管理模块

使用 Pydantic 进行配置验证和管理，支持从环境变量加载配置。
"""
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
from functools import lru_cache


class DatabaseSettings(BaseSettings):
    """数据库配置"""
    host: str = Field(default="localhost", description="数据库主机")
    port: int = Field(default=3306, description="数据库端口")
    user: str = Field(default="root", description="用户名")
    password: str = Field(default="", description="密码")
    database: str = Field(default="alarm", description="数据库名")
    pool_size: int = Field(default=5, description="连接池大小")
    max_overflow: int = Field(default=10, description="最大溢出连接数")
    
    model_config = SettingsConfigDict(env_prefix="DB_")


class ModelSettings(BaseSettings):
    """模型配置"""
    provider: str = Field(default="siliconflow", description="模型提供商")
    api_key: str = Field(default="", description="API 密钥")
    base_url: str = Field(default="https://api.siliconflow.cn/v1", description="API 基础 URL")
    model_name: str = Field(default="deepseek-ai/DeepSeek-V3", description="模型名称")
    temperature: float = Field(default=0.1, ge=0, le=2, description="温度参数")
    max_tokens: int = Field(default=4096, gt=0, description="最大 token 数")
    timeout: int = Field(default=60, gt=0, description="超时时间")
    
    model_config = SettingsConfigDict(env_prefix="MODEL_")


class Settings(BaseSettings):
    """全局配置"""
    # 应用配置
    app_name: str = Field(default="Data Analysis Agent", description="应用名称")
    debug: bool = Field(default=False, description="调试模式")
    version: str = Field(default="2.0.0", description="版本号")
    
    # 子配置
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    model: ModelSettings = Field(default_factory=ModelSettings)
    
    # LangSmith 配置
    langsmith_api_key: Optional[str] = Field(default=None, description="LangSmith API 密钥")
    langsmith_project: Optional[str] = Field(default=None, description="LangSmith 项目名")
    langsmith_tracing: Optional[str] = Field(default=None, description="LangSmith 追踪开关")
    
    # 兼容旧版环境变量
    siliconflow_api_key: Optional[str] = Field(default=None, description="SiliconFlow API 密钥（兼容旧版）")
    deepseek_api_key: Optional[str] = Field(default=None, description="DeepSeek API 密钥（兼容旧版）")
    
    # 数据库兼容旧版
    host: Optional[str] = Field(default=None, description="数据库主机（兼容旧版）")
    user: Optional[str] = Field(default=None, description="数据库用户名（兼容旧版）")
    mysql_pw: Optional[str] = Field(default=None, description="数据库密码（兼容旧版）")
    db_name: Optional[str] = Field(default=None, description="数据库名（兼容旧版）")
    port: Optional[str] = Field(default=None, description="数据库端口（兼容旧版）")
    
    # 日志配置
    log_level: str = Field(default="INFO", description="日志级别")
    log_file: Optional[str] = Field(default=None, description="日志文件路径")
    
    # 图像保存路径
    image_base_dir: str = Field(
        default=r"D:\Learning\Learning\大模型\LangChain\Python\langgraph_dataanalysis\agent-chat-ui-main\public",
        description="图像保存基础目录"
    )
    
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore"  # 忽略额外的环境变量
    )


def get_settings() -> Settings:
    """获取配置单例
    
    使用 lru_cache 确保配置只被加载一次，提高性能。
    同时处理旧版环境变量的兼容性问题。
    
    Returns:
        Settings: 全局配置对象
    """
    settings = Settings()
    
    # 处理旧版环境变量兼容性
    # 如果新版配置为空，但旧版有值，则使用旧版值
    if not settings.model.api_key:
        if settings.siliconflow_api_key:
            settings.model.api_key = settings.siliconflow_api_key
        elif settings.deepseek_api_key:
            settings.model.api_key = settings.deepseek_api_key
            settings.model.provider = "deepseek"
    
    # 处理数据库旧版配置
    if settings.host and not settings.database.host:
        settings.database.host = settings.host
    if settings.user and not settings.database.user:
        settings.database.user = settings.user
    if settings.mysql_pw and not settings.database.password:
        settings.database.password = settings.mysql_pw
    if settings.db_name and not settings.database.database:
        settings.database.database = settings.db_name
    if settings.port and not settings.database.port:
        try:
            settings.database.port = int(settings.port)
        except ValueError:
            pass
    
    return settings
