"""Model configuration helpers."""

from config.settings import ModelSettings, get_settings


def get_model_settings() -> ModelSettings:
    """Return model settings singleton view."""
    return get_settings().model
