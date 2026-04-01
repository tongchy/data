"""
Long Term Memory - 长期记忆

基于 Store 的跨会话持久化记忆
"""

from typing import Any, Dict, List, Optional
from datetime import datetime


class LongTermMemory:
    """
    长期记忆管理器
    
    管理跨会话的持久化数据：
    - 用户偏好
    - 历史模式
    - 学习到的知识
    """
    
    def __init__(self, store=None, namespace: tuple = ("long_term_memory",)):
        """
        初始化长期记忆
        
        Args:
            store: LangGraph Store 实例
            namespace: 命名空间
        """
        self.store = store
        self.namespace = namespace
        
    def set(self, key: str, value: Any, user_id: Optional[str] = None) -> bool:
        """
        设置长期记忆
        
        Args:
            key: 记忆键
            value: 记忆值
            user_id: 用户ID（用于用户隔离）
            
        Returns:
            是否成功
        """
        if self.store is None:
            return False
        
        try:
            full_key = f"{user_id}_{key}" if user_id else key
            
            # 包装值，添加元数据
            wrapped_value = {
                "value": value,
                "updated_at": datetime.now().isoformat(),
                "user_id": user_id
            }
            
            self.store.put(self.namespace, full_key, wrapped_value)
            return True
        except Exception as e:
            print(f"Error saving long-term memory: {e}")
            return False
    
    def get(self, key: str, user_id: Optional[str] = None, default: Any = None) -> Any:
        """
        获取长期记忆
        
        Args:
            key: 记忆键
            user_id: 用户ID
            default: 默认值
            
        Returns:
            记忆值或默认值
        """
        if self.store is None:
            return default
        
        try:
            full_key = f"{user_id}_{key}" if user_id else key
            
            item = self.store.get(self.namespace, full_key)
            if item is None:
                return default
            
            # 解包值
            wrapped = item.value
            return wrapped.get("value", default)
        except Exception as e:
            print(f"Error retrieving long-term memory: {e}")
            return default
    
    def search(self, query: str, user_id: Optional[str] = None) -> List[Dict]:
        """
        搜索长期记忆
        
        Args:
            query: 搜索查询
            user_id: 用户ID
            
        Returns:
            匹配的记忆列表
        """
        if self.store is None:
            return []
        
        try:
            items = self.store.search(self.namespace, query=query)
            
            results = []
            for item in items:
                wrapped = item.value
                # 用户过滤
                if user_id and wrapped.get("user_id") != user_id:
                    continue
                
                results.append({
                    "key": item.key,
                    "value": wrapped.get("value"),
                    "updated_at": wrapped.get("updated_at")
                })
            
            return results
        except Exception as e:
            print(f"Error searching long-term memory: {e}")
            return []
    
    def delete(self, key: str, user_id: Optional[str] = None) -> bool:
        """
        删除长期记忆
        
        Args:
            key: 记忆键
            user_id: 用户ID
            
        Returns:
            是否成功
        """
        if self.store is None:
            return False
        
        try:
            full_key = f"{user_id}_{key}" if user_id else key
            self.store.put(self.namespace, full_key, {"__deleted__": True})
            return True
        except Exception as e:
            print(f"Error deleting long-term memory: {e}")
            return False
