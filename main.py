"""Entry point for running the Chitai server."""

import uvicorn

from chitai.settings import settings


def main() -> None:
    """Run the FastAPI server with uvicorn."""
    uvicorn.run(
        "chitai.server.app:app",
        host="0.0.0.0",  # noqa: S104
        port=8000,
        reload=settings.reload,
        ssl_certfile=settings.ssl_certfile,
        ssl_keyfile=settings.ssl_keyfile,
    )


if __name__ == "__main__":
    main()
