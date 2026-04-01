"""上下文编辑器核心逻辑

以声明式 ContextEdit 描述编辑操作，ContextEditor.apply() 按顺序执行：
  - clear:    清空旧的工具结果（保留最近 N 条，用占位符替换其余）
  - truncate: 截断消息列表（保留最后 N 条）
  - replace:  将一段旧消息替换为单条新消息
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ContextEdit:
    """一次编辑操作的描述

    Attributes:
        edit_type: "clear" | "truncate" | "replace"
        target:    操作目标标识（当前仅作说明用，如 "tool_results"）
        params:    操作参数字典，各 edit_type 的具体参数见实现
    """

    edit_type: str
    target: str
    params: Dict[str, Any] = field(default_factory=dict)


class ContextEditor:
    """将若干 ContextEdit 操作应用到消息列表上

    用法::

        editor = ContextEditor()
        editor.add_edit(ContextEdit("truncate", "messages", {"keep": 20}))
        edited = editor.apply(messages, state)
    """

    def __init__(self) -> None:
        self._edits: List[ContextEdit] = []

    def add_edit(self, edit: ContextEdit) -> None:
        self._edits.append(edit)

    def clear_edits(self) -> None:
        self._edits.clear()

    def apply(self, messages: List[Any], state: Dict[str, Any]) -> List[Any]:
        result = list(messages)
        for edit in self._edits:
            if edit.edit_type == "clear":
                result = self._clear_tool_results(result, edit.params)
            elif edit.edit_type == "truncate":
                result = self._truncate(result, edit.params)
            elif edit.edit_type == "replace":
                result = self._replace(result, edit.params)
            else:
                logger.warning("Unknown edit_type: %s, skipping", edit.edit_type)
        return result

    # ------------------------------------------------------------------ internal

    def _clear_tool_results(
        self, messages: List[Any], params: Dict[str, Any]
    ) -> List[Any]:
        """用占位符替换早期工具结果，保留最近 keep 条

        params:
            keep:        保留的最新工具消息数量（默认 3）
            placeholder: 替换内容（默认 "[已清理]"）
        """
        keep = int(params.get("keep", 3))
        placeholder = str(params.get("placeholder", "[已清理]"))

        tool_indices: List[int] = [
            i for i, m in enumerate(messages) if getattr(m, "type", None) == "tool"
        ]

        if len(tool_indices) <= keep:
            return messages  # 不需要清理

        to_clear = tool_indices[: len(tool_indices) - keep]
        result = list(messages)
        for idx in to_clear:
            msg = result[idx]
            try:
                result[idx] = type(msg)(
                    content=placeholder,
                    tool_call_id=msg.tool_call_id,
                )
            except Exception:
                # 无法重建时直接修改 content（fallback）
                try:
                    object.__setattr__(msg, "content", placeholder)
                except Exception:
                    pass  # 保留原消息
        return result

    def _truncate(self, messages: List[Any], params: Dict[str, Any]) -> List[Any]:
        """保留最后 keep 条消息

        params:
            keep: 保留的消息数量（默认 20）
        """
        keep = int(params.get("keep", 20))
        return messages[-keep:] if len(messages) > keep else messages

    def _replace(self, messages: List[Any], params: Dict[str, Any]) -> List[Any]:
        """将 old_messages 连续段替换为 new_message

        params:
            old_messages: 要替换的消息列表
            new_message:  替换后的单条消息
        """
        old: List[Any] = params.get("old_messages", [])
        new_msg: Optional[Any] = params.get("new_message")
        if not new_msg or not old:
            return messages

        result: List[Any] = []
        i = 0
        while i < len(messages):
            if messages[i : i + len(old)] == old:
                result.append(new_msg)
                i += len(old)
            else:
                result.append(messages[i])
                i += 1
        return result
