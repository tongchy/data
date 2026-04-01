"""
Store Backend - 长期记忆后端

基于 LangGraph Store 的跨会话持久化存储
适用于用户偏好、历史模式等
"""

import json
from typing import Any, Dict, List, Optional
from datetime import datetime


class StoreBackend:
    """
    长期记忆后端 - 跨会话持久化
    
    特点：
    - 数据存储在 Store 中，跨会话共享
    - 支持用户级别的记忆隔离
    - 适合用户偏好、历史分析模式
    """
    
    def __init__(self, config: Optional[Dict] = None, store=None, base_path: str = "/memories/"):
        """
        初始化 Store Backend
        
        Args:
            config: 配置字典
            store: LangGraph Store 实例
            base_path: 虚拟文件系统根路径
        """
        self.config = config or {}
        self.store = store
        self.base_path = base_path
        self._namespace = ("memories",)
        
    def _get_key(self, path: str) -> str:
        """将路径转换为 store key"""
        # 移除 base_path 前缀
        if path.startswith(self.base_path):
            path = path[len(self.base_path):]
        return path.lstrip("/").replace("/", "_")
    
    def ls(self, path: Optional[str] = None) -> Dict[str, Any]:
        """
        列出目录内容
        
        Args:
            path: 目录路径
            
        Returns:
            包含文件列表的字典
        """
        if self.store is None:
            return {
                "success": False,
                "error": "Store not initialized",
                "files": [],
                "directories": []
            }
        
        target_path = path or self.base_path
        if not target_path.startswith(self.base_path):
            target_path = self.base_path + target_path.lstrip("/")
        
        try:
            # 从 store 搜索
            prefix = self._get_key(target_path)
            items = self.store.search(self._namespace, query=prefix)
            
            files = []
            directories = set()
            
            for item in items:
                key = item.key
                if key.startswith(prefix):
                    relative = key[len(prefix):].lstrip("_")
                    if "_" in relative:
                        dir_name = relative.split("_")[0]
                        directories.add(dir_name)
                    else:
                        files.append(relative)
            
            return {
                "path": target_path,
                "files": files,
                "directories": list(directories),
                "total": len(files) + len(directories),
                "success": True
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "files": [],
                "directories": []
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
        if self.store is None:
            return {
                "success": False,
                "error": "Store not initialized",
                "content": None
            }
        
        if not path.startswith(self.base_path):
            path = self.base_path + path.lstrip("/")
        
        key = self._get_key(path)
        
        try:
            item = self.store.get(self._namespace, key)
            if item is None:
                return {
                    "success": False,
                    "error": f"File not found: {path}",
                    "content": None
                }
            
            content = item.value
            
            # 处理内容
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
                    "truncated": truncated,
                    "created_at": getattr(item, 'created_at', None),
                    "updated_at": getattr(item, 'updated_at', None)
                }
            
            return {
                "success": True,
                "content": content,
                "type": type(content).__name__,
                "created_at": getattr(item, 'created_at', None),
                "updated_at": getattr(item, 'updated_at', None)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "content": None
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
        if self.store is None:
            return {
                "success": False,
                "error": "Store not initialized"
            }
        
        if not path.startswith(self.base_path):
            path = self.base_path + path.lstrip("/")
        
        key = self._get_key(path)
        
        try:
            if append:
                # 读取现有内容
                existing_item = self.store.get(self._namespace, key)
                if existing_item:
                    existing = existing_item.value
                    if isinstance(existing, str) and isinstance(content, str):
                        content = existing + content
                    elif isinstance(existing, list):
                        if isinstance(content, list):
                            content = existing + content
                        else:
                            content = existing + [content]
                    else:
                        content = [existing, content]
            
            # 写入 store
            self.store.put(self._namespace, key, content)
            
            return {
                "success": True,
                "path": path,
                "key": key,
                "size": len(str(content))
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def edit_file(self, path: str, old_str: str, new_str: str) -> Dict[str, Any]:
        """
        编辑文件内容
        
        Args:
            path: 文件路径
            old_str: 要替换的字符串
            new_str: 新字符串
            
        Returns:
            操作结果字典
        """
        if self.store is None:
            return {
                "success": False,
                "error": "Store not initialized"
            }
        
        if not path.startswith(self.base_path):
            path = self.base_path + path.lstrip("/")
        
        key = self._get_key(path)
        
        try:
            item = self.store.get(self._namespace, key)
            if item is None:
                return {
                    "success": False,
                    "error": f"File not found: {path}"
                }
            
            content = item.value
            if not isinstance(content, str):
                return {
                    "success": False,
                    "error": "Can only edit text files"
                }
            
            if old_str not in content:
                return {
                    "success": False,
                    "error": f"String not found in file"
                }
            
            # 执行替换
            new_content = content.replace(old_str, new_str, 1)
            self.store.put(self._namespace, key, new_content)
            
            return {
                "success": True,
                "path": path,
                "replacements": 1
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def delete_file(self, path: str) -> Dict[str, Any]:
        """
        删除文件
        
        Args:
            path: 文件路径
            
        Returns:
            操作结果字典
        """
        if self.store is None:
            return {
                "success": False,
                "error": "Store not initialized"
            }
        
        if not path.startswith(self.base_path):
            path = self.base_path + path.lstrip("/")
        
        key = self._get_key(path)
        
        try:
            # 检查是否存在
            item = self.store.get(self._namespace, key)
            if item is None:
                return {
                    "success": False,
                    "error": f"File not found: {path}"
                }
            
            # 删除（通过设置空值或特殊标记）
            self.store.put(self._namespace, key, {"__deleted__": True})
            
            return {
                "success": True,
                "path": path
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def exists(self, path: str) -> bool:
        """检查文件是否存在"""
        if self.store is None:
            return False
        
        if not path.startswith(self.base_path):
            path = self.base_path + path.lstrip("/")
        
        key = self._get_key(path)
        
        try:
            item = self.store.get(self._namespace, key)
            return item is not None
        except:
            return False
    
    def search(self, query: str) -> List[Dict[str, Any]]:
        """
        搜索记忆
        
        Args:
            query: 搜索查询
            
        Returns:
            匹配的记忆列表
        """
        if self.store is None:
            return []
        
        try:
            items = self.store.search(self._namespace, query=query)
            return [
                {
                    "key": item.key,
                    "value": item.value,
                    "score": getattr(item, 'score', None)
                }
                for item in items
            ]
        except Exception as e:
            return []
