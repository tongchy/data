"""上下文编辑中间件（自动清理旧工具结果，防止 token 溢出）

在 before_model 钩子中估算当前 token 数量，超过阈值时
自动清空早期工具结果，保留最新 keep_tool_results 条。

token 估算方法：len(content) // 4（字符数 / 4，与 GPT 系列模型粗估一致）
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from middleware.base import BaseMiddleware
from middleware.context_editor import ContextEdit, ContextEditor
from middleware.types import MiddlewareCommand

logger = logging.getLogger(__name__)


class ContextEditingMiddleware(BaseMiddleware):
    """上下文编辑中间件

    当消息列表估算 token 数超过 trigger_tokens 时，
    自动在 before_model 钩子中清理早期工具结果，
    并通过 MiddlewareCommand.messages 返回精简后的消息列表。

    Args:
        trigger_tokens:    触发清理的 token 数阈值（默认 100 000）
        keep_tool_results: 清理后保留的工具消息数量（默认 3）
        placeholder:       被清理消息的替换文本（默认 "[已清理]"）

    state 约定：
        state["context_edited"] → True 表示本轮已触发上下文编辑
    """

    name: str = "ContextEditingMiddleware"
    priority: int = 10  # 最低优先级，在所有其他中间件之后执行

    def __init__(
        self,
        trigger_tokens: int = 100_000,
        keep_tool_results: int = 3,
        placeholder: str = "[已清理]",
    ) -> None:
        self.trigger_tokens = trigger_tokens
        self.keep_tool_results = keep_tool_results
        self.placeholder = placeholder
        self._editor = ContextEditor()

    # ------------------------------------------------------------------ hooks

    async def before_model(
        self,
        state: Dict[str, Any],
        messages: List[Any],
    ) -> Optional[MiddlewareCommand]:
        current_tokens = self._count_tokens(messages)
        if current_tokens <= self.trigger_tokens:
            return None

        logger.info(
            "Context too long (~%d tokens > %d), trimming tool results (keep=%d)",
            current_tokens,
            self.trigger_tokens,
            self.keep_tool_results,
        )

        self._editor.clear_edits()
        self._editor.add_edit(
            ContextEdit(
                edit_type="clear",
                target="tool_results",
                params={
                    "keep": self.keep_tool_results,
                    "placeholder": self.placeholder,
                },
            )
        )
        edited = self._editor.apply(messages, state)
        return MiddlewareCommand(
            update={"context_edited": True},
            messages=edited,
        )

    # ------------------------------------------------------------------ utils

    @staticmethod
    def _count_tokens(messages: List[Any]) -> int:
        """粗估 token 数（字符数 // 4）"""
        total = 0
        for msg in messages:
            content = getattr(msg, "content", "")
            if isinstance(content, str):
                total += len(content) // 4
        return total
