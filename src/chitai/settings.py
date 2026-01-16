"""Application settings loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration.

    All settings can be overridden via environment variables prefixed with CHITAI_.
    For example, CHITAI_RELOAD=1 sets reload=True.
    """

    reload: bool = False

    class Config:
        env_prefix = "CHITAI_"


settings = Settings()
