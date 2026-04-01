"""Database configuration helpers."""

from config.settings import DatabaseSettings, get_settings


def get_database_settings() -> DatabaseSettings:
    """Return database settings singleton view."""
    return get_settings().database
