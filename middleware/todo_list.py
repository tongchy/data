"""
TODO List Middleware - 任务规划中间件

提供任务分解和进度跟踪能力
"""

from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import json

from core.tool_compat import compatible_tool


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """任务定义"""
    id: str
    title: str
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    dependencies: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[Any] = None
    error: Optional[str] = None


class TodoListMiddleware:
    """
    TODO List 中间件
    
    提供任务规划和管理能力：
    - 任务分解
    - 进度跟踪
    - 依赖管理
    - 状态更新
    """
    
    def __init__(self):
        """初始化 TODO List 中间件"""
        self.tasks: Dict[str, Task] = {}
        self._counter = 0
        
    def get_tools(self) -> List[Callable]:
        """获取 TODO List 工具"""
        return [
            self._create_create_todo_tool(),
            self._create_update_todo_tool(),
            self._create_list_todos_tool(),
            self._create_get_todo_tool(),
        ]
    
    def _generate_id(self) -> str:
        """生成任务 ID"""
        self._counter += 1
        return f"task_{self._counter:03d}"
    
    def _create_create_todo_tool(self) -> Callable:
        """创建添加任务工具"""
        
        @compatible_tool(
            name="create_todo",
            description="创建新任务或分解复杂任务为子任务"
        )
        def create_todo(
            title: str,
            description: str = "",
            dependencies: Optional[List[str]] = None
        ) -> str:
            """
            创建新任务
            
            Args:
                title: 任务标题
                description: 任务描述（可选）
                dependencies: 依赖的任务ID列表（可选）
            """
            task_id = self._generate_id()
            
            task = Task(
                id=task_id,
                title=title,
                description=description,
                dependencies=dependencies or []
            )
            
            self.tasks[task_id] = task
            
            deps_str = f" (依赖: {', '.join(dependencies)})" if dependencies else ""
            
            return f"""
✅ 任务已创建

ID: {task_id}
标题: {title}
描述: {description or '无'}{deps_str}
状态: {task.status.value}
""".strip()
        
        return create_todo
    
    def _create_update_todo_tool(self) -> Callable:
        """创建更新任务工具"""
        
        @compatible_tool(
            name="update_todo",
            description="更新任务状态（开始、完成、失败等）"
        )
        def update_todo(
            task_id: str,
            status: str,
            result: Optional[str] = None,
            error: Optional[str] = None
        ) -> str:
            """
            更新任务状态
            
            Args:
                task_id: 任务ID
                status: 新状态 (pending/in_progress/completed/failed/cancelled)
                result: 任务结果（可选）
                error: 错误信息（可选）
            """
            if task_id not in self.tasks:
                return f"❌ 未找到任务: {task_id}"
            
            task = self.tasks[task_id]
            
            try:
                new_status = TaskStatus(status)
            except ValueError:
                return f"❌ 无效的状态: {status}"
            
            task.status = new_status
            
            if new_status == TaskStatus.IN_PROGRESS and not task.started_at:
                task.started_at = datetime.now().isoformat()
            
            if new_status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                task.completed_at = datetime.now().isoformat()
            
            if result:
                task.result = result
            
            if error:
                task.error = error
            
            status_emoji = {
                TaskStatus.PENDING: "⏳",
                TaskStatus.IN_PROGRESS: "🔄",
                TaskStatus.COMPLETED: "✅",
                TaskStatus.FAILED: "❌",
                TaskStatus.CANCELLED: "🚫"
            }
            
            return f"""
{status_emoji[new_status]} 任务已更新

ID: {task_id}
标题: {task.title}
新状态: {new_status.value}
{f"结果: {result}" if result else ""}
{f"错误: {error}" if error else ""}
""".strip()
        
        return update_todo
    
    def _create_list_todos_tool(self) -> Callable:
        """创建列出任务工具"""
        
        @compatible_tool(
            name="list_todos",
            description="列出所有任务及其状态"
        )
        def list_todos(status_filter: Optional[str] = None) -> str:
            """
            列出所有任务
            
            Args:
                status_filter: 按状态过滤（可选）
            """
            if not self.tasks:
                return "暂无任务"
            
            tasks_list = list(self.tasks.values())
            
            if status_filter:
                try:
                    filter_status = TaskStatus(status_filter)
                    tasks_list = [t for t in tasks_list if t.status == filter_status]
                except ValueError:
                    return f"❌ 无效的状态过滤: {status_filter}"
            
            # 按状态分组
            status_emoji = {
                TaskStatus.PENDING: "⏳",
                TaskStatus.IN_PROGRESS: "🔄",
                TaskStatus.COMPLETED: "✅",
                TaskStatus.FAILED: "❌",
                TaskStatus.CANCELLED: "🚫"
            }
            
            lines = ["📋 任务列表", "=" * 40]
            
            for status in TaskStatus:
                status_tasks = [t for t in tasks_list if t.status == status]
                if status_tasks:
                    lines.append(f"\n{status_emoji[status]} {status.value.upper()} ({len(status_tasks)})")
                    for task in status_tasks:
                        deps = f" [依赖: {', '.join(task.dependencies)}]" if task.dependencies else ""
                        lines.append(f"  • {task.id}: {task.title}{deps}")
            
            # 统计
            total = len(self.tasks)
            completed = len([t for t in self.tasks.values() if t.status == TaskStatus.COMPLETED])
            progress = (completed / total * 100) if total > 0 else 0
            
            lines.append(f"\n{'=' * 40}")
            lines.append(f"进度: {completed}/{total} ({progress:.1f}%)")
            
            return "\n".join(lines)
        
        return list_todos
    
    def _create_get_todo_tool(self) -> Callable:
        """创建获取任务详情工具"""
        
        @compatible_tool(
            name="get_todo",
            description="获取单个任务的详细信息"
        )
        def get_todo(task_id: str) -> str:
            """
            获取任务详情
            
            Args:
                task_id: 任务ID
            """
            if task_id not in self.tasks:
                return f"❌ 未找到任务: {task_id}"
            
            task = self.tasks[task_id]
            
            status_emoji = {
                TaskStatus.PENDING: "⏳",
                TaskStatus.IN_PROGRESS: "🔄",
                TaskStatus.COMPLETED: "✅",
                TaskStatus.FAILED: "❌",
                TaskStatus.CANCELLED: "🚫"
            }
            
            lines = [
                f"{status_emoji[task.status]} 任务详情",
                "=" * 40,
                f"ID: {task.id}",
                f"标题: {task.title}",
                f"描述: {task.description or '无'}",
                f"状态: {task.status.value}",
            ]
            
            if task.dependencies:
                lines.append(f"依赖: {', '.join(task.dependencies)}")
            
            lines.extend([
                f"创建时间: {task.created_at}",
                f"开始时间: {task.started_at or '未开始'}",
                f"完成时间: {task.completed_at or '未完成'}",
            ])
            
            if task.result:
                lines.append(f"\n结果:\n{task.result}")
            
            if task.error:
                lines.append(f"\n错误:\n{task.error}")
            
            return "\n".join(lines)
        
        return get_todo
    
    def get_progress(self) -> Dict[str, Any]:
        """获取整体进度"""
        total = len(self.tasks)
        if total == 0:
            return {"total": 0, "completed": 0, "progress": 0}
        
        completed = len([t for t in self.tasks.values() if t.status == TaskStatus.COMPLETED])
        
        return {
            "total": total,
            "completed": completed,
            "pending": len([t for t in self.tasks.values() if t.status == TaskStatus.PENDING]),
            "in_progress": len([t for t in self.tasks.values() if t.status == TaskStatus.IN_PROGRESS]),
            "failed": len([t for t in self.tasks.values() if t.status == TaskStatus.FAILED]),
            "progress": (completed / total * 100)
        }


def create_todo_middleware() -> TodoListMiddleware:
    """
    创建 TODO List 中间件（便捷函数）
    
    Returns:
        TodoListMiddleware 实例
    """
    return TodoListMiddleware()
