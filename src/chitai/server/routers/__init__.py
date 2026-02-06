"""API routers for REST endpoints."""

from chitai.server.routers.illustrations import router as illustrations_router
from chitai.server.routers.items import router as items_router
from chitai.server.routers.logs import router as logs_router
from chitai.server.routers.sessions import router as sessions_router

__all__ = ["illustrations_router", "items_router", "logs_router", "sessions_router"]
