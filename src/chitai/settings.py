"""Application settings loaded from environment variables."""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration.

    All settings can be overridden via environment variables prefixed with CHITAI_.
    For example, CHITAI_RELOAD=1 sets reload=True.
    """

    reload: bool = False
    cert_dir: str = "data/certs"
    database_url: str = "sqlite:///data/chitai.db"

    class Config:
        """Pydantic configuration."""

        env_prefix = "CHITAI_"

    @property
    def ssl_certfile(self) -> str:
        """Path to SSL certificate file."""
        return str(Path(self.cert_dir) / "cert.pem")

    @property
    def ssl_keyfile(self) -> str:
        """Path to SSL private key file."""
        return str(Path(self.cert_dir) / "key.pem")


settings = Settings()
