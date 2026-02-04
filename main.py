"""Entry point for running the Chitai server."""

import uvicorn

from chitai.settings import settings

LOG_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s - %(levelname)s - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
        },
    },
    "loggers": {
        "uvicorn": {"handlers": ["default"], "level": "INFO"},
        "uvicorn.error": {"level": "INFO"},
        "uvicorn.access": {
            "handlers": ["default"],
            "level": "INFO",
            "propagate": False,
        },
        "chitai": {"handlers": ["default"], "level": "INFO"},
    },
}


def main() -> None:
    """Run the FastAPI server with uvicorn."""
    uvicorn.run(
        "chitai.server.app:app",
        host="0.0.0.0",  # noqa: S104
        port=8000,
        reload=settings.reload,
        ssl_certfile=settings.ssl_certfile,
        ssl_keyfile=settings.ssl_keyfile,
        ws_ping_timeout=settings.ws_ping_timeout_seconds,
        log_config=LOG_CONFIG,
    )


if __name__ == "__main__":
    main()
