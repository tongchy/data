"""
Filesystem Middleware - 文件系统中间件

提供文件操作工具，支持短期和长期记忆
"""

from typing import Any, Dict, List, Optional, Callable
from langchain_core.runnables import RunnableConfig

from filesystem import CompositeBackend, StateBackend, StoreBackend
from core.tool_compat import compatible_tool


class FilesystemMiddleware:
    """
    文件系统中间件
    
    提供 4 个文件操作工具：
    - ls: 列出目录
    - read_file: 读取文件
    - write_file: 写入文件
    - edit_file: 编辑文件
    """
    
    def __init__(
        self,
        backend: CompositeBackend,
        custom_descriptions: Optional[Dict[str, str]] = None
    ):
        """
        初始化文件系统中间件
        
        Args:
            backend: 复合后端实例
            custom_descriptions: 自定义工具描述
        """
        self.backend = backend
        self.descriptions = custom_descriptions or {}
        
    def get_tools(self) -> List[Callable]:
        """获取文件系统工具列表"""
        return [
            self._create_ls_tool(),
            self._create_read_file_tool(),
            self._create_write_file_tool(),
            self._create_edit_file_tool(),
        ]
    
    def _create_ls_tool(self) -> Callable:
        """创建 ls 工具"""
        description = self.descriptions.get(
            "ls",
            "列出指定目录的文件和子目录。支持短期记忆(/files/)和长期记忆(/memories/)路径。"
        )
        
        @compatible_tool(name="ls", description=description)
        def ls(path: Optional[str] = None) -> str:
            """
            列出目录内容
            
            Args:
                path: 目录路径，默认为当前工作目录
                      /files/ - 短期记忆目录
                      /memories/ - 长期记忆目录
            """
            result = self.backend.ls(path)
            
            if not result.get("success", True):
                return f"错误: {result.get('error', 'Unknown error')}"
            
            lines = [f"目录: {result['path']}", "=" * 40]
            
            if result.get("directories"):
                lines.append("\n[子目录]")
                for d in result["directories"]:
                    lines.append(f"  📁 {d}/")
            
            if result.get("files"):
                lines.append("\n[文件]")
                for f in result["files"]:
                    lines.append(f"  📄 {f}")
            
            lines.append(f"\n总计: {result.get('total', 0)} 项")
            
            return "\n".join(lines)
        
        return ls
    
    def _create_read_file_tool(self) -> Callable:
        """创建 read_file 工具"""
        description = self.descriptions.get(
            "read_file",
            "读取文件内容。支持文本文件和JSON文件。可以指定读取行数限制。"
        )
        
        @compatible_tool(name="read_file", description=description)
        def read_file(path: str, limit: Optional[int] = None) -> str:
            """
            读取文件内容
            
            Args:
                path: 文件路径
                      /files/filename.txt - 短期记忆文件
                      /memories/filename.json - 长期记忆文件
                limit: 限制读取的行数（可选）
            """
            result = self.backend.read_file(path, limit)
            
            if not result.get("success"):
                return f"错误: {result.get('error', 'Unknown error')}"
            
            content = result.get("content", "")
            
            # 格式化输出
            lines = [f"文件: {path}", "=" * 40, ""]
            
            if isinstance(content, str):
                lines.append(content)
            else:
                # JSON 格式化
                import json
                lines.append(json.dumps(content, indent=2, ensure_ascii=False))
            
            if result.get("truncated"):
                lines.append(f"\n... (已截断，共 {result.get('total_lines', '?')} 行)")
            
            return "\n".join(lines)
        
        return read_file
    
    def _create_write_file_tool(self) -> Callable:
        """创建 write_file 工具"""
        description = self.descriptions.get(
            "write_file",
            "写入文件内容。如果文件存在则覆盖，不存在则创建。支持短期记忆和长期记忆路径。"
        )
        
        @compatible_tool(name="write_file", description=description)
        def write_file(path: str, content: str, append: bool = False) -> str:
            """
            写入文件
            
            Args:
                path: 文件路径
                      /files/filename.txt - 短期记忆（会话内）
                      /memories/filename.json - 长期记忆（跨会话）
                content: 文件内容
                append: 是否追加到现有文件（默认覆盖）
            """
            result = self.backend.write_file(path, content, append)
            
            if not result.get("success"):
                return f"错误: {result.get('error', 'Unknown error')}"
            
            action = "追加到" if append else "写入"
            size = result.get("size", 0)
            
            return f"✅ 成功{action}文件: {path}\n大小: {size} 字符"
        
        return write_file
    
    def _create_edit_file_tool(self) -> Callable:
        """创建 edit_file 工具"""
        description = self.descriptions.get(
            "edit_file",
            "编辑文件内容，替换指定的字符串。用于修改现有文件。"
        )
        
        @compatible_tool(name="edit_file", description=description)
        def edit_file(path: str, old_string: str, new_string: str) -> str:
            """
            编辑文件内容（替换字符串）
            
            Args:
                path: 文件路径
                old_string: 要替换的字符串
                new_string: 新字符串
            """
            result = self.backend.edit_file(path, old_string, new_string)
            
            if not result.get("success"):
                return f"错误: {result.get('error', 'Unknown error')}"
            
            return f"✅ 成功编辑文件: {path}\n替换次数: {result.get('replacements', 0)}"
        
        return edit_file


def create_filesystem_tools(
    state_backend: Optional[StateBackend] = None,
    store_backends: Optional[Dict[str, StoreBackend]] = None,
    custom_descriptions: Optional[Dict[str, str]] = None
) -> List[Callable]:
    """
    创建文件系统工具（便捷函数）
    
    Args:
        state_backend: State Backend 实例
        store_backends: Store Backend 字典
        custom_descriptions: 自定义工具描述
        
    Returns:
        文件系统工具列表
    """
    # 创建默认后端
    if state_backend is None:
        state_backend = StateBackend(base_path="/files/")
    
    if store_backends is None:
        store_backends = {}
    
    # 创建复合后端
    backend = CompositeBackend(state_backend, store_backends)
    
    # 创建中间件
    middleware = FilesystemMiddleware(backend, custom_descriptions)
    
    return middleware.get_tools()
