"""FastAPI application entry point."""

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from chitai.server.grace_timer import GraceTimer
from chitai.server.routers import items_router, logs_router, sessions_router
from chitai.server.session import SessionState
from chitai.server.websocket.handlers import end_session, handle_message
from chitai.server.websocket.state import broadcast_state
from chitai.settings import settings

if TYPE_CHECKING:
    from datetime import datetime

logger = logging.getLogger(__name__)


app = FastAPI(title="Chitai")


@dataclass
class AppStateContext:
    """Typed container for global application state.

    This is a pure data holder for server infrastructure that persists across WebSocket
    connections. It exists to provide typed access to global state that would otherwise
    be scattered or untyped.

    Design constraints:
    - No methods (except trivial property accessors) — logic belongs elsewhere
    - Never pass this object as a whole to functions; pass individual fields explicitly
      to keep APIs clear about their dependencies

    """

    session: SessionState = field(default_factory=SessionState)
    clients: set[WebSocket] = field(default_factory=set)
    grace_timer: GraceTimer = field(default=None)  # type: ignore[assignment]


async def _on_grace_timer_expire(ended_at: datetime) -> None:
    """Auto-end the session on grace timer expire."""
    await end_session(
        app.state.context.session,
        app.state.context.clients,
        ended_at=ended_at,
    )


# Initialize application state
app.state.context = AppStateContext(
    grace_timer=GraceTimer(
        grace_period_seconds=settings.grace_period_seconds,
        on_expire=_on_grace_timer_expire,
    ),
)

# Include REST API routers
app.include_router(items_router)
app.include_router(logs_router)
app.include_router(sessions_router)

# Mount static files
app.mount("/web", StaticFiles(directory="web", html=True), name="web")


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    role: str = Query(..., description="Client role: 'controller' or 'display'"),
) -> None:
    """WebSocket endpoint for controller and display clients.

    Parameters
    ----------
    websocket : WebSocket
        The WebSocket connection
    role : str
        Client role: 'controller' or 'display'

    """
    await websocket.accept()
    session_state = websocket.app.state.context.session
    clients = websocket.app.state.context.clients
    grace_timer = websocket.app.state.context.grace_timer

    if role not in ("controller", "display"):
        logger.warning("Unknown role: %s", role)
        await websocket.close()
        return

    clients.add(websocket)
    logger.info("%s connected; total clients: %d", role.capitalize(), len(clients))

    # Send current state to newly connected client
    await broadcast_state(session_state, {websocket})

    try:
        while True:
            data = await websocket.receive_json()
            logger.info("Received from %s: %s", role, data)
            await handle_message(websocket, data)

            if session_state.session_id is None:
                grace_timer.stop()
            else:
                grace_timer.refresh()

    except WebSocketDisconnect:
        logger.info("%s disconnected", role.capitalize())
    except (RuntimeError, ValueError) as e:
        logger.info("%s disconnected: %s", role.capitalize(), e)
    finally:
        clients.discard(websocket)
        logger.info("Client disconnected; total clients: %d", len(clients))
