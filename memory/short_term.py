"""
Short Term Memory - 短期记忆

基于 State 的会话内记忆管理
"""

from typing import Any, Dict, List, Optional
from datetime import datetime


class ShortTermMemory:
    """
    短期记忆管理器
    
    管理会话内的临时数据：
    - 中间计算结果
    - 临时文件引用
    - 会话状态
    """
    
    def __init__(self):
        """初始化短期记忆"""
        self._data: Dict[str, Any] = {}
        self._metadata: Dict[str, Dict] = {}
        
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        设置记忆
        
        Args:
            key: 记忆键
            value: 记忆值
            ttl: 生存时间（秒），None 表示会话结束
        """
        self._data[key] = value
        self._metadata[key] = {
            "created_at": datetime.now().isoformat(),
            "ttl": ttl,
            "access_count": 0
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取记忆
        
        Args:
            key: 记忆键
            default: 默认值
            
        Returns:
            记忆值或默认值
        """
        if key in self._data:
            self._metadata[key]["access_count"] += 1
            self._metadata[key]["last_accessed"] = datetime.now().isoformat()
            return self._data[key]
        return default
    
    def delete(self, key: str) -> bool:
        """
        删除记忆
        
        Args:
            key: 记忆键
            
        Returns:
            是否成功删除
        """
        if key in self._data:
            del self._data[key]
            del self._metadata[key]
            return True
        return False
    
    def clear(self) -> None:
        """清空所有记忆"""
        self._data.clear()
        self._metadata.clear()
    
    def keys(self) -> List[str]:
        """获取所有键"""
        return list(self._data.keys())
    
    def get_stats(self) -> Dict[str, Any]:
        """获取记忆统计"""
        return {
            "total_items": len(self._data),
            "keys": list(self._data.keys()),
            "metadata": self._metadata
        }
