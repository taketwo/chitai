"""Application settings loaded from environment variables."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration.

    All settings can be overridden via environment variables prefixed with CHITAI_.
    For example, CHITAI_RELOAD=1 sets reload=True.
    """

    model_config = SettingsConfigDict(env_prefix="CHITAI_")

    reload: bool = False
    cert_dir: str = "data/certs"
    database_url: str = "sqlite:///data/chitai.db"
    grace_period_seconds: int = 3600
    ws_ping_timeout_seconds: int | None = 300

    @property
    def ssl_certfile(self) -> str:
        """Path to SSL certificate file."""
        return str(Path(self.cert_dir) / "cert.pem")

    @property
    def ssl_keyfile(self) -> str:
        """Path to SSL private key file."""
        return str(Path(self.cert_dir) / "key.pem")


settings = Settings()
