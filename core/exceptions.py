"""自定义异常类"""


class AgentException(Exception):
    """Agent 基础异常"""
    
    def __init__(self, message: str, code: str = "AGENT_ERROR"):
        self.message = message
        self.code = code
        super().__init__(self.message)


class DatabaseException(AgentException):
    """数据库相关异常"""
    
    def __init__(self, message: str, original_error: Exception = None):
        self.original_error = original_error
        super().__init__(message, code="DB_ERROR")


class ToolExecutionException(AgentException):
    """工具执行异常"""
    
    def __init__(self, tool_name: str, message: str, original_error: Exception = None):
        self.tool_name = tool_name
        self.original_error = original_error
        super().__init__(f"工具 '{tool_name}' 执行失败: {message}", code="TOOL_ERROR")


class ConfigurationException(AgentException):
    """配置异常"""
    
    def __init__(self, message: str):
        super().__init__(message, code="CONFIG_ERROR")


class ModelAPIException(AgentException):
    """模型 API 调用异常"""
    
    def __init__(self, message: str, status_code: int = None, original_error: Exception = None):
        self.status_code = status_code
        self.original_error = original_error
        super().__init__(message, code=f"MODEL_ERROR_{status_code}" if status_code else "MODEL_ERROR")
