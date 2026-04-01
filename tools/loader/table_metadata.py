"""表元数据查询工具

查询 MySQL/MariaDB INFORMATION_SCHEMA 获取指定表的统计信息：
  - 估算行数（TABLE_ROWS）
  - 数据体积（DATA_LENGTH）
  - 索引体积（INDEX_LENGTH）
  - 最后更新时间（UPDATE_TIME）

若数据库不可用，返回 success=False 且不抛出异常（安全降级）。
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from tools.base import BaseCustomTool, ToolResult
from tools.registry import registry

logger = logging.getLogger(__name__)


class TableMetadataTool(BaseCustomTool):
    """查询数据库表的元数据与统计信息

    用法::

        tool = TableMetadataTool()
        result = tool._run(table_name="orders")
    """

    name: str = "table_metadata"
    description: str = (
        "查询数据库表的统计信息和元数据。\n"
        "返回：行数估算、数据大小、索引大小、最后更新时间。\n"
        "参数：table_name（必填，表名）。"
    )
    category: str = "loader"
    version: str = "1.0.0"

    # ------------------------------------------------------------------ execute

    def _execute(self, table_name: str, **_kwargs: Any) -> ToolResult:  # type: ignore[override]
        """查询指定表的 INFORMATION_SCHEMA 统计数据

        Args:
            table_name: 目标表名

        Returns:
            ToolResult: 包含表统计信息的结果对象
        """
        if not table_name or not table_name.strip():
            return ToolResult(
                success=False,
                error="table_name 不能为空",
                message="查询失败：未提供表名",
            )

        try:
            from database.connection import DatabaseManager  # 延迟导入，避免启动时依赖数据库

            with DatabaseManager() as db:
                rows = db.execute_query(
                    """
                    SELECT
                        TABLE_NAME,
                        TABLE_ROWS,
                        DATA_LENGTH,
                        INDEX_LENGTH,
                        UPDATE_TIME
                    FROM INFORMATION_SCHEMA.TABLES
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = %s
                    """,
                    (table_name,),
                )

            if not rows:
                return ToolResult(
                    success=False,
                    error=f"表 `{table_name}` 不存在，或尚无统计信息",
                    message=f"未在 INFORMATION_SCHEMA 中找到表 `{table_name}`",
                )

            stats = rows[0]
            msg = (
                f"表 `{table_name}` 元数据：\n"
                f"- 行数（估算）：{stats.get('TABLE_ROWS') or 0:,}\n"
                f"- 数据大小：{self._fmt_bytes(stats.get('DATA_LENGTH', 0))}\n"
                f"- 索引大小：{self._fmt_bytes(stats.get('INDEX_LENGTH', 0))}\n"
                f"- 最后更新：{stats.get('UPDATE_TIME') or '未知'}"
            )
            return ToolResult(success=True, data=dict(stats), message=msg)

        except Exception as exc:  # pragma: no cover
            logger.warning("table_metadata query failed for %s: %s", table_name, exc)
            return ToolResult(
                success=False,
                error=str(exc),
                message=f"查询表 `{table_name}` 元数据时出错：{exc}",
            )

    # ------------------------------------------------------------------ utils

    @staticmethod
    def _fmt_bytes(size: Any) -> str:
        """将字节数格式化为可读字符串"""
        try:
            size_b = int(size or 0)
        except (TypeError, ValueError):
            return "N/A"

        if size_b >= 1 << 30:
            return f"{size_b / (1 << 30):.2f} GB"
        if size_b >= 1 << 20:
            return f"{size_b / (1 << 20):.2f} MB"
        if size_b >= 1 << 10:
            return f"{size_b / (1 << 10):.2f} KB"
        return f"{size_b} B"


table_metadata = TableMetadataTool()
registry.register(table_metadata)
