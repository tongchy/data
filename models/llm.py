"""
LLM 模型创建模块

统一封装 LLM 创建逻辑，支持多种模型提供商。
"""

from typing import Optional
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from config.settings import Settings, get_settings


def create_llm(settings: Optional[Settings] = None) -> BaseChatModel:
    """
    创建 LLM 模型实例
    
    Args:
        settings: 配置对象，如果为 None 则使用默认配置
        
    Returns:
        BaseChatModel: LangChain 聊天模型实例
    """
    if settings is None:
        settings = get_settings()
    
    model_config = settings.model
    
    # 使用 OpenAI 兼容接口（支持硅基流动、OpenAI 等）
    return ChatOpenAI(
        model=model_config.model_name,
        api_key=model_config.api_key,
        base_url=model_config.base_url,
        temperature=model_config.temperature,
        max_tokens=model_config.max_tokens,
        timeout=model_config.timeout,
    )
