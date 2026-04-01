"""Logging configuration helpers."""

import logging
from config.settings import get_settings


def setup_logging() -> None:
    """Configure root logging from settings."""
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
