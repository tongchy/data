"""Device repository."""

from typing import Any, Dict, List

from database.repositories.base import BaseRepository


class DeviceRepository(BaseRepository):
    """Repository for simple device-table lookups."""

    def list_rows(self, table_name: str, limit: int = 10) -> List[Dict[str, Any]]:
        sql = f"SELECT * FROM `{table_name}` LIMIT %s"
        return self.fetch_all(sql, (limit,))
