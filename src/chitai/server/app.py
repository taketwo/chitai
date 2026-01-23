"""FastAPI application with WebSocket endpoint."""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from chitai.db.engine import get_session
from chitai.db.models import Item, Language, SessionItem
from chitai.db.models import Session as DBSession
from chitai.server.session import SessionState
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

app.state.context = AppStateContext()

app.mount("/web", StaticFiles(directory="web", html=True), name="web")


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


async def _send_state(session_state: SessionState, websocket: WebSocket) -> None:
    """Send current session state to a specific client.

    Parameters
    ----------
    session_state : SessionState
        The session state to send
    websocket : WebSocket
        The client's WebSocket connection

    """
    message = {
        "type": "state",
        "payload": session_state.to_payload(),
    }
    try:
        await websocket.send_json(message)
    except (WebSocketDisconnect, RuntimeError) as e:
        logger.warning("Failed to send state: %s", e)


async def _broadcast_state(
    session_state: SessionState, clients: set[WebSocket]
) -> None:
    """Broadcast current session state to all connected clients.

    Parameters
    ----------
    session_state : SessionState
        The session state to broadcast
    clients : set[WebSocket]
        Connected clients to broadcast to

    """
    for client in clients:
        await _send_state(session_state, client)


async def _grace_period_timer(
    context: AppStateContext, grace_period_seconds: int
) -> None:
    """Background task that waits for grace period then auto-ends session.

    Parameters
    ----------
    app_context : AppStateContext
        Application state context containing session and clients
    grace_period_seconds : int
        Grace period in seconds

    """
    try:
        await asyncio.sleep(grace_period_seconds)
        logger.info("Grace period expired, auto-ending session")
        await _end_session(
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

    await _send_state(session_state, websocket)

    try:
        while True:
            data = await websocket.receive_json()
            logger.info("Received from %s: %s", role, data)
            await _handle_message(websocket, data)

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


async def _handle_message(websocket: WebSocket, data: dict) -> None:
    """Handle messages from any client.

    Parameters
    ----------
    websocket : WebSocket
        The client's WebSocket connection
    data : dict
        The message data

    """
    session_state = websocket.app.state.context.session
    clients = websocket.app.state.context.clients
    message_type = data.get("type")

    if message_type == "start_session":
        await _start_session(session_state, clients)
    elif message_type == "end_session":
        await _end_session(session_state, clients)
    elif message_type == "add_item":
        await _add_item(session_state, clients, data.get("payload", {}))
    elif message_type == "advance_word":
        await _advance_word(session_state, clients, data.get("payload", {}))
    else:
        logger.warning("Unknown message type: %s", message_type)


async def _start_session(session_state: SessionState, clients: set[WebSocket]) -> None:
    """Start a new reading session.

    Parameters
    ----------
    session_state : SessionState
        The session state
    clients : set[WebSocket]
        Connected clients to broadcast to

    """
    if session_state.session_id is not None:
        logger.warning("Session already active, ignoring start_session")
        return

    with get_session() as db_session:
        db_session_obj = DBSession(language=Language.RUSSIAN)
        db_session.add(db_session_obj)
        db_session.commit()
        session_id = db_session_obj.id

    session_state.session_id = session_id
    logger.info("Session started: %s", session_id)

    await _broadcast_state(session_state, clients)


async def _end_session(
    session_state: SessionState,
    clients: set[WebSocket],
    ended_at: datetime | None = None,
) -> None:
    """End the active reading session.

    Parameters
    ----------
    session_state : SessionState
        The session state
    clients : set[WebSocket]
        Connected clients to broadcast to
    ended_at : datetime | None
        Optional timestamp for when session ended. If None, uses current time.
        Used when grace period expires to record actual disconnect time.

    """
    if session_state.session_id is None:
        logger.warning("No active session to end")
        return

    end_time = ended_at or datetime.now(UTC)

    with get_session() as db_session:
        db_session_obj = db_session.get(DBSession, session_state.session_id)
        if db_session_obj:
            db_session_obj.ended_at = end_time

            # Complete any incomplete SessionItems
            incomplete_items = db_session.scalars(
                select(SessionItem).where(
                    SessionItem.session_id == session_state.session_id,
                    SessionItem.completed_at.is_(None),
                )
            ).all()
            for session_item in incomplete_items:
                session_item.completed_at = end_time

            db_session.commit()

    logger.info("Session ended: %s", session_state.session_id)

    # Clear session state and broadcast to clients
    session_state.reset()
    await _broadcast_state(session_state, clients)


async def _add_item(
    session_state: SessionState, clients: set[WebSocket], payload: dict
) -> None:
    """Add a text item to the session.

    Creates or retrieves an Item, completes the previous SessionItem if any, and
    creates a new SessionItem for the current item.

    Parameters
    ----------
    session_state : SessionState
        The session state
    clients : set[WebSocket]
        Connected clients to broadcast to
    payload : dict
        Message payload containing 'text' field

    """
    text = payload.get("text")
    if not text:
        logger.warning("add_item message missing text")
        return

    if session_state.session_id is None:
        logger.warning("Cannot add item: no active session")
        return

    with get_session() as db_session:
        db_session_obj = db_session.get(DBSession, session_state.session_id)
        if not db_session_obj:
            logger.error("Session not found: %s", session_state.session_id)
            return

        language = db_session_obj.language

        # Check if item already exists
        item = db_session.scalars(
            select(Item).where(Item.text == text, Item.language == language)
        ).first()
        if not item:
            item = Item(text=text, language=language)
            db_session.add(item)
            db_session.flush()  # Get the item ID

        # Complete previous SessionItem if exists
        if session_state.current_item_id:
            prev_session_item = db_session.scalars(
                select(SessionItem).where(
                    SessionItem.session_id == session_state.session_id,
                    SessionItem.item_id == session_state.current_item_id,
                    SessionItem.completed_at.is_(None),
                )
            ).first()
            if prev_session_item:
                prev_session_item.completed_at = datetime.now(UTC)

        session_item = SessionItem(
            session_id=session_state.session_id,
            item_id=item.id,
        )
        db_session.add(session_item)
        db_session.commit()

        session_state.current_item_id = item.id

    session_state.set_text(text)
    await _broadcast_state(session_state, clients)


async def _advance_word(
    session_state: SessionState, clients: set[WebSocket], payload: dict
) -> None:
    """Advance to a different word in the current text.

    Parameters
    ----------
    session_state : SessionState
        The session state
    clients : set[WebSocket]
        Connected clients to broadcast to
    payload : dict
        Message payload containing optional 'delta' field

    """
    if session_state.advance_word(payload.get("delta", 1)):
        await _broadcast_state(session_state, clients)
