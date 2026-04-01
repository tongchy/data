"""
Composite Backend - 复合后端

组合 State Backend（短期记忆）和 Store Backend（长期记忆）
根据路径自动路由到相应的后端
"""

from typing import Any, Dict, List, Optional
from .backends.state_backend import StateBackend
from .backends.store_backend import StoreBackend


class CompositeBackend:
    """
    复合后端 - 统一管理短期和长期记忆
    
    路由规则：
    - /files/* -> State Backend (短期记忆)
    - /memories/* -> Store Backend (长期记忆)
    """
    
    def __init__(
        self,
        state_backend: StateBackend,
        store_backends: Dict[str, StoreBackend]
    ):
        """
        初始化复合后端
        
        Args:
            state_backend: State Backend 实例
            store_backends: Store Backend 字典，键为路径前缀
        """
        self.state_backend = state_backend
        self.store_backends = store_backends
        
    def _get_backend(self, path: str):
        """根据路径获取对应的后端"""
        # 检查是否匹配 Store Backend
        for prefix, backend in self.store_backends.items():
            if path.startswith(prefix):
                return backend, prefix
        
        # 默认使用 State Backend
        return self.state_backend, self.state_backend.base_path
    
    def ls(self, path: Optional[str] = None) -> Dict[str, Any]:
        """列出目录内容"""
        if path is None:
            # 列出根目录，显示所有后端
            result = {
                "path": "/",
                "files": [],
                "directories": ["files", "memories"],
                "total": 2,
                "success": True
            }
            
            # 添加 State Backend 的内容
            state_result = self.state_backend.ls()
            if state_result.get("success"):
                result["files_in_files"] = state_result.get("files", [])
                result["dirs_in_files"] = state_result.get("directories", [])
            
            # 添加 Store Backend 的内容
            for prefix, backend in self.store_backends.items():
                store_result = backend.ls()
                if store_result.get("success"):
                    key = f"files_in_{prefix.strip('/')}"
                    result[key] = store_result.get("files", [])
            
            return result
        
        backend, _ = self._get_backend(path)
        return backend.ls(path)
    
    def read_file(self, path: str, limit: Optional[int] = None) -> Dict[str, Any]:
        """读取文件"""
        backend, _ = self._get_backend(path)
        return backend.read_file(path, limit)
    
    def write_file(self, path: str, content: Any, append: bool = False) -> Dict[str, Any]:
        """写入文件"""
        backend, _ = self._get_backend(path)
        return backend.write_file(path, content, append)
    
    def edit_file(self, path: str, old_str: str, new_str: str) -> Dict[str, Any]:
        """编辑文件"""
        backend, _ = self._get_backend(path)
        return backend.edit_file(path, old_str, new_str)
    
    def delete_file(self, path: str) -> Dict[str, Any]:
        """删除文件"""
        backend, _ = self._get_backend(path)
        return backend.delete_file(path)
    
    def exists(self, path: str) -> bool:
        """检查文件是否存在"""
        backend, _ = self._get_backend(path)
        return backend.exists(path)
    
    def get_backend_info(self) -> Dict[str, Any]:
        """获取后端信息"""
        return {
            "state_backend": {
                "base_path": self.state_backend.base_path,
                "file_count": len(self.state_backend.get_all_files())
            },
            "store_backends": {
                prefix: {
                    "base_path": backend.base_path,
                    "initialized": backend.store is not None
                }
                for prefix, backend in self.store_backends.items()
            }
        }
