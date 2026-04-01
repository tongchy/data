"""
State Backend - 短期记忆后端

基于 LangGraph State 的会话内持久化存储
适用于临时数据、中间结果等
"""

import json
import os
from typing import Any, Dict, List, Optional
from pathlib import Path


class StateBackend:
    """
    短期记忆后端 - 会话内持久化
    
    特点：
    - 数据存储在 State 中，会话内共享
    - 会话结束后自动清理
    - 适合临时文件、中间结果
    """
    
    def __init__(self, config: Optional[Dict] = None, base_path: str = "/files/"):
        """
        初始化 State Backend
        
        Args:
            config: 配置字典
            base_path: 虚拟文件系统根路径
        """
        self.config = config or {}
        self.base_path = base_path
        self._files: Dict[str, Any] = {}  # 内存文件存储
        self._working_dir = base_path
        
    def ls(self, path: Optional[str] = None) -> Dict[str, Any]:
        """
        列出目录内容
        
        Args:
            path: 目录路径，默认为当前工作目录
            
        Returns:
            包含文件列表的字典
        """
        target_path = path or self._working_dir
        
        # 确保路径以 base_path 开头
        if not target_path.startswith(self.base_path):
            target_path = os.path.join(self.base_path, target_path.lstrip("/"))
        
        files = []
        directories = []
        
        for file_path in self._files.keys():
            if file_path.startswith(target_path):
                relative = file_path[len(target_path):].lstrip("/")
                if "/" in relative:
                    # 是子目录
                    dir_name = relative.split("/")[0]
                    if dir_name not in directories:
                        directories.append(dir_name)
                else:
                    files.append(relative)
        
        return {
            "path": target_path,
            "files": files,
            "directories": directories,
            "total": len(files) + len(directories)
        }
    
    def read_file(self, path: str, limit: Optional[int] = None) -> Dict[str, Any]:
        """
        读取文件内容
        
        Args:
            path: 文件路径
            limit: 限制读取行数
            
        Returns:
            包含文件内容的字典
        """
        # 确保路径格式正确
        if not path.startswith(self.base_path):
            path = os.path.join(self.base_path, path.lstrip("/"))
        
        if path not in self._files:
            return {
                "success": False,
                "error": f"File not found: {path}",
                "content": None
            }
        
        content = self._files[path]
        
        # 如果是字符串，按行处理
        if isinstance(content, str):
            lines = content.split("\n")
            total_lines = len(lines)
            if limit and limit < total_lines:
                lines = lines[:limit]
                truncated = True
            else:
                truncated = False
            
            return {
                "success": True,
                "content": "\n".join(lines),
                "total_lines": total_lines,
                "truncated": truncated
            }
        
        # 如果是其他类型，直接返回
        return {
            "success": True,
            "content": content,
            "type": type(content).__name__
        }
    
    def write_file(self, path: str, content: Any, append: bool = False) -> Dict[str, Any]:
        """
        写入文件
        
        Args:
            path: 文件路径
            content: 文件内容
            append: 是否追加模式
            
        Returns:
            操作结果字典
        """
        # 确保路径格式正确
        if not path.startswith(self.base_path):
            path = os.path.join(self.base_path, path.lstrip("/"))
        
        try:
            if append and path in self._files:
                # 追加模式
                existing = self._files[path]
                if isinstance(existing, str) and isinstance(content, str):
                    self._files[path] = existing + content
                else:
                    # 非字符串类型，转换为列表
                    if not isinstance(existing, list):
                        existing = [existing]
                    if isinstance(content, list):
                        existing.extend(content)
                    else:
                        existing.append(content)
                    self._files[path] = existing
            else:
                # 覆盖模式
                self._files[path] = content
            
            return {
                "success": True,
                "path": path,
                "size": len(str(self._files[path]))
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def edit_file(self, path: str, old_str: str, new_str: str) -> Dict[str, Any]:
        """
        编辑文件内容（替换字符串）
        
        Args:
            path: 文件路径
            old_str: 要替换的字符串
            new_str: 新字符串
            
        Returns:
            操作结果字典
        """
        # 确保路径格式正确
        if not path.startswith(self.base_path):
            path = os.path.join(self.base_path, path.lstrip("/"))
        
        if path not in self._files:
            return {
                "success": False,
                "error": f"File not found: {path}"
            }
        
        content = self._files[path]
        if not isinstance(content, str):
            return {
                "success": False,
                "error": "Can only edit text files"
            }
        
        if old_str not in content:
            return {
                "success": False,
                "error": f"String not found in file: {old_str[:50]}..."
            }
        
        # 执行替换
        new_content = content.replace(old_str, new_str, 1)
        self._files[path] = new_content
        
        return {
            "success": True,
            "path": path,
            "replacements": 1
        }
    
    def delete_file(self, path: str) -> Dict[str, Any]:
        """
        删除文件
        
        Args:
            path: 文件路径
            
        Returns:
            操作结果字典
        """
        # 确保路径格式正确
        if not path.startswith(self.base_path):
            path = os.path.join(self.base_path, path.lstrip("/"))
        
        if path not in self._files:
            return {
                "success": False,
                "error": f"File not found: {path}"
            }
        
        del self._files[path]
        
        return {
            "success": True,
            "path": path
        }
    
    def exists(self, path: str) -> bool:
        """检查文件是否存在"""
        if not path.startswith(self.base_path):
            path = os.path.join(self.base_path, path.lstrip("/"))
        return path in self._files
    
    def get_size(self, path: str) -> int:
        """获取文件大小"""
        if not path.startswith(self.base_path):
            path = os.path.join(self.base_path, path.lstrip("/"))
        
        if path not in self._files:
            return 0
        
        return len(str(self._files[path]))
    
    def clear(self) -> None:
        """清空所有文件"""
        self._files.clear()
    
    def get_all_files(self) -> Dict[str, Any]:
        """获取所有文件（用于调试）"""
        return dict(self._files)
