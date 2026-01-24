"""FastAPI application with WebSocket endpoint."""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from chitai.db.engine import get_session_ctx
from chitai.db.models import Item, Language, SessionItem
from chitai.db.models import Session as DBSession
from chitai.server.protocol import (
    SessionItemInfo,
    StateMessage,
    StatePayload,
    incoming_message_adapter,
)
from chitai.server.routers import items_router, logs_router, sessions_router
from chitai.server.session import SessionState
from chitai.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _build_state_payload(session_state: SessionState) -> StatePayload:
    """Build protocol payload from session state.

    Fetches queue item details from database and combines with in-memory state.

    Parameters
    ----------
    session_state : SessionState
        The session state to convert

    Returns
    -------
    StatePayload
        Protocol message payload ready for broadcast

    """
    queue_items: list[SessionItemInfo] = []

    if session_state.queue:
        with get_session_ctx() as db_session:
            # Fetch all queued SessionItems with their Items in a single query
            session_items = (
                db_session.scalars(
                    select(SessionItem)
                    .options(joinedload(SessionItem.item))
                    .where(SessionItem.id.in_(session_state.queue))
                )
                .unique()
                .all()
            )

            # Create lookup dict and maintain queue order
            session_item_map = {si.id: si for si in session_items}
            queue_items.extend(
                SessionItemInfo(
                    session_item_id=session_item_id,
                    text=session_item.item.text,
                )
                for session_item_id in session_state.queue
                if (session_item := session_item_map.get(session_item_id))
            )

    return StatePayload(
        session_id=session_state.session_id,
        words=session_state.words,
        syllables=session_state.syllables,
        current_word_index=session_state.current_word_index,
        queue=queue_items,
    )


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

app.include_router(items_router)
app.include_router(logs_router)
app.include_router(sessions_router)
app.mount("/web", StaticFiles(directory="web", html=True), name="web")


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


async def _send_state(payload: StatePayload, websocket: WebSocket) -> None:
    """Send state payload to a specific client.

    Parameters
    ----------
    payload : StatePayload
        The state payload to send
    websocket : WebSocket
        The client's WebSocket connection

    """
    message = StateMessage(type="state", payload=payload)
    try:
        await websocket.send_json(message.model_dump(mode="json"))
    except (WebSocketDisconnect, RuntimeError) as e:
        logger.warning("Failed to send state: %s", e)


async def _broadcast_state(
    session_state: SessionState, clients: set[WebSocket]
) -> None:
    """Broadcast current session state to all connected clients.

    Builds the state payload once and sends to all clients to avoid
    redundant database queries.

    Parameters
    ----------
    session_state : SessionState
        The session state to broadcast
    clients : set[WebSocket]
        Connected clients to broadcast to

    """
    payload = _build_state_payload(session_state)
    for client in clients:
        await _send_state(payload, client)


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

    # Send current state to newly connected client
    payload = _build_state_payload(session_state)
    await _send_state(payload, websocket)

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

    try:
        message = incoming_message_adapter.validate_python(data)
    except ValidationError as e:
        logger.warning("Invalid message format: %s", e)
        return

    if message.type == "start_session":
        await _start_session(session_state, clients)
    elif message.type == "end_session":
        await _end_session(session_state, clients)
    elif message.type == "add_item":
        await _add_item(session_state, clients, message.payload.text)
    elif message.type == "advance_word":
        await _advance_word(session_state, clients, message.payload.delta)


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

    with get_session_ctx() as db_session:
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

    with get_session_ctx() as db_session:
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
    session_state: SessionState, clients: set[WebSocket], text: str
) -> None:
    """Add a text item to the session.

    Creates or retrieves an Item and creates a new SessionItem. If no item is currently
    displayed, displays the new item immediately. Otherwise, adds it to the queue.

    Parameters
    ----------
    session_state : SessionState
        The session state
    clients : set[WebSocket]
        Connected clients to broadcast to
    text : str
        The text to add

    """
    if session_state.session_id is None:
        logger.warning("Cannot add item: no active session")
        return

    with get_session_ctx() as db_session:
        db_session_obj = db_session.get(DBSession, session_state.session_id)
        if not db_session_obj:
            logger.error(
                "Session not found in database: %s, resetting state",
                session_state.session_id,
            )
            session_state.reset()
            await _broadcast_state(session_state, clients)
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

        # Create SessionItem (not displayed yet)
        session_item = SessionItem(
            session_id=session_state.session_id,
            item_id=item.id,
            displayed_at=None,
        )
        db_session.add(session_item)
        db_session.flush()  # Get the session_item ID

        # If nothing is currently displayed, display immediately
        if session_state.current_session_item_id is None:
            session_item.displayed_at = datetime.now(UTC)
            db_session.commit()

            session_state.current_session_item_id = session_item.id
            session_state.set_text(text)
            logger.info("Item displayed immediately: %s", item.id)
        else:
            # Otherwise, add to queue
            db_session.commit()
            session_state.queue.append(session_item.id)
            logger.info(
                "Item added to queue (position %d): %s",
                len(session_state.queue),
                item.id,
            )

    await _broadcast_state(session_state, clients)


async def _advance_word(
    session_state: SessionState, clients: set[WebSocket], delta: int
) -> None:
    """Advance to a different word in the current text.

    Parameters
    ----------
    session_state : SessionState
        The session state
    clients : set[WebSocket]
        Connected clients to broadcast to
    delta : int
        Number of words to advance (positive) or go back (negative)

    """
    if session_state.advance_word(delta):
        await _broadcast_state(session_state, clients)
