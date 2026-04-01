"""Base repository primitives."""

from typing import Any, Dict, List, Optional, Tuple

from database.connection import DatabaseManager


class BaseRepository:
    """Minimal repository wrapper around DatabaseManager."""

    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db or DatabaseManager()

    def fetch_all(self, sql: str, params: Optional[Tuple[Any, ...]] = None) -> List[Dict[str, Any]]:
        return self.db.execute_query(sql, params)

    def fetch_scalar(self, sql: str, params: Optional[Tuple[Any, ...]] = None) -> Any:
        return self.db.execute_scalar(sql, params)
