"""
Summarization Middleware - 记忆摘要中间件

自动压缩历史对话，防止上下文溢出
"""

from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass
from core.tool_compat import compatible_tool


@dataclass
class SummarizationConfig:
    """摘要配置"""
    trigger_tokens: int = 4000  # 触发摘要的 token 数
    trigger_messages: int = 10   # 触发摘要的消息数
    keep_messages: int = 20      # 保留的最近消息数
    summary_model: str = "deepseek-ai/DeepSeek-V3"  # 用于摘要的模型


class SummarizationMiddleware:
    """
    记忆摘要中间件
    
    自动管理对话历史：
    - 监控 token 使用量
    - 自动触发摘要
    - 压缩历史消息
    """
    
    def __init__(self, config: Optional[SummarizationConfig] = None):
        """
        初始化摘要中间件
        
        Args:
            config: 摘要配置
        """
        self.config = config or SummarizationConfig()
        self._conversation_history: List[Dict] = []
        self._summaries: List[str] = []
        self._total_tokens = 0
        
    def add_message(self, role: str, content: str, tokens: int = 0) -> None:
        """
        添加消息到历史
        
        Args:
            role: 角色（user/assistant/system）
            content: 消息内容
            tokens: token 数（估算）
        """
        self._conversation_history.append({
            "role": role,
            "content": content,
            "tokens": tokens
        })
        self._total_tokens += tokens
        
        # 检查是否需要触发摘要
        self._check_and_trigger_summarization()
    
    def _check_and_trigger_summarization(self) -> bool:
        """
        检查并触发摘要
        
        Returns:
            是否触发了摘要
        """
        message_count = len(self._conversation_history)
        
        # 检查触发条件
        should_trigger = (
            self._total_tokens >= self.config.trigger_tokens or
            message_count >= self.config.trigger_messages
        )
        
        if should_trigger and message_count > self.config.keep_messages:
            self._summarize()
            return True
        
        return False
    
    def _summarize(self) -> str:
        """
        执行摘要
        
        Returns:
            摘要内容
        """
        # 保留最近的消息
        keep_count = self.config.keep_messages
        to_summarize = self._conversation_history[:-keep_count]
        self._conversation_history = self._conversation_history[-keep_count:]
        
        # 生成摘要（简化版本）
        summary = self._generate_summary(to_summarize)
        self._summaries.append(summary)
        
        # 重新计算 token
        self._total_tokens = sum(m.get("tokens", 0) for m in self._conversation_history)
        
        return summary
    
    def _generate_summary(self, messages: List[Dict]) -> str:
        """
        生成摘要（实际实现应该调用 LLM）
        
        Args:
            messages: 需要摘要的消息列表
            
        Returns:
            摘要文本
        """
        # 提取关键信息
        user_goals = []
        completed_tasks = []
        key_findings = []
        
        for msg in messages:
            content = msg.get("content", "")
            role = msg.get("role", "")
            
            if role == "user":
                # 提取用户目标
                if len(content) < 200:
                    user_goals.append(content[:100])
            elif role == "assistant":
                # 提取完成的任务
                if "✅" in content or "完成" in content:
                    completed_tasks.append(content[:100])
                # 提取关键发现
                if "发现" in content or "分析" in content:
                    key_findings.append(content[:100])
        
        # 构建摘要
        summary_parts = ["📋 对话摘要"]
        
        if user_goals:
            summary_parts.append(f"\n用户目标: {user_goals[-1]}")
        
        if completed_tasks:
            summary_parts.append(f"\n已完成: {len(completed_tasks)} 项任务")
        
        if key_findings:
            summary_parts.append(f"\n关键发现: {len(key_findings)} 条")
        
        summary_parts.append(f"\n(已压缩 {len(messages)} 条历史消息)")
        
        return "\n".join(summary_parts)
    
    def get_context(self) -> Dict[str, Any]:
        """
        获取当前上下文
        
        Returns:
            包含摘要和最近消息的字典
        """
        return {
            "summaries": self._summaries,
            "recent_messages": self._conversation_history,
            "total_tokens": self._total_tokens,
            "message_count": len(self._conversation_history)
        }
    
    def get_tools(self) -> List[Callable]:
        """获取摘要相关工具"""
        return [
            self._create_summarize_tool(),
            self._create_get_context_tool(),
        ]
    
    def _create_summarize_tool(self) -> Callable:
        """创建手动触发摘要工具"""
        
        @compatible_tool(
            name="summarize_conversation",
            description="手动触发对话摘要，压缩历史消息"
        )
        def summarize_conversation() -> str:
            """手动触发摘要"""
            if len(self._conversation_history) <= self.config.keep_messages:
                return "消息数量较少，无需摘要"
            
            summary = self._summarize()
            
            return f"""
✅ 摘要已完成

{summary}

当前状态:
- 历史摘要数: {len(self._summaries)}
- 保留消息数: {len(self._conversation_history)}
- 预估 tokens: {self._total_tokens}
""".strip()
        
        return summarize_conversation
    
    def _create_get_context_tool(self) -> Callable:
        """创建获取上下文工具"""
        
        @compatible_tool(
            name="get_conversation_context",
            description="获取当前对话上下文和统计信息"
        )
        def get_conversation_context() -> str:
            """获取对话上下文"""
            ctx = self.get_context()
            
            lines = [
                "📊 对话上下文统计",
                "=" * 40,
                f"历史摘要数: {len(ctx['summaries'])}",
                f"最近消息数: {ctx['message_count']}",
                f"预估 tokens: {ctx['total_tokens']}",
                f"触发阈值: {self.config.trigger_tokens} tokens / {self.config.trigger_messages} 消息",
            ]
            
            if ctx['summaries']:
                lines.append("\n📋 历史摘要:")
                for i, summary in enumerate(ctx['summaries'][-3:], 1):
                    lines.append(f"\n摘要 {i}:")
                    lines.append(summary[:200] + "..." if len(summary) > 200 else summary)
            
            return "\n".join(lines)
        
        return get_conversation_context
    
    def clear(self) -> None:
        """清空所有历史"""
        self._conversation_history.clear()
        self._summaries.clear()
        self._total_tokens = 0
