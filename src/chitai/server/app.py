"""FastAPI application entry point."""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from chitai.server.routers import items_router, logs_router, sessions_router
from chitai.server.session import SessionState
from chitai.server.websocket.handlers import end_session, handle_message
from chitai.server.websocket.state import broadcast_state
from chitai.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class AppStateContext:
    """Server state that persists across WebSocket connections."""

    session: SessionState = field(default_factory=SessionState)
    clients: set[WebSocket] = field(default_factory=set)
    grace_period_seconds: int = settings.grace_period_seconds
    disconnect_time: datetime | None = None
    grace_timer_task: asyncio.Task[None] | None = None

    @property
    def has_active_grace_timer(self) -> bool:
        """Check if grace period timer is currently running."""
        return self.grace_timer_task is not None and not self.grace_timer_task.done()


app = FastAPI(title="Chitai")

# Initialize application state
app.state.context = AppStateContext()

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


async def _grace_period_timer(
    context: AppStateContext, grace_period_seconds: int
) -> None:
    """Background task that waits for grace period then auto-ends session.

    Parameters
    ----------
    context : AppStateContext
        Application state context containing session and clients
    grace_period_seconds : int
        Grace period in seconds

    """
    try:
        await asyncio.sleep(grace_period_seconds)
        logger.info("Grace period expired, auto-ending session")
        await end_session(
            context.session,
            context.clients,
            ended_at=context.disconnect_time,
        )
        # Clean up grace period state
        context.disconnect_time = None
        context.grace_timer_task = None
    except asyncio.CancelledError:
        logger.debug("Grace period timer cancelled")
        raise


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

    if role not in ("controller", "display"):
        logger.warning("Unknown role: %s", role)
        await websocket.close()
        return

    clients.add(websocket)
    logger.info("%s connected; total clients: %d", role.capitalize(), len(clients))

    # Cancel grace period timer if clients are reconnecting
    if websocket.app.state.context.has_active_grace_timer:
        logger.info("Client reconnected, cancelling grace period timer")
        websocket.app.state.context.grace_timer_task.cancel()
        websocket.app.state.context.grace_timer_task = None
        websocket.app.state.context.disconnect_time = None

    # Send current state to newly connected client
    await broadcast_state(session_state, {websocket})

    try:
        while True:
            data = await websocket.receive_json()
            logger.info("Received from %s: %s", role, data)
            await handle_message(websocket, data)

    except WebSocketDisconnect:
        logger.info("%s disconnected", role.capitalize())
    except (RuntimeError, ValueError) as e:
        logger.info("%s disconnected: %s", role.capitalize(), e)
    finally:
        clients.discard(websocket)
        logger.info("Client disconnected; total clients: %d", len(clients))

        # Start grace period timer if this was the last client and session is active
        if len(clients) == 0 and session_state.session_id is not None:
            websocket.app.state.context.disconnect_time = datetime.now(UTC)
            grace_period = websocket.app.state.context.grace_period_seconds
            logger.info(
                "Last client disconnected, starting %ds grace period",
                grace_period,
            )
            websocket.app.state.context.grace_timer_task = asyncio.create_task(
                _grace_period_timer(websocket.app.state.context, grace_period)
            )
