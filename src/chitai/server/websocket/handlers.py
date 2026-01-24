"""WebSocket message handlers."""

import logging
from datetime import UTC, datetime

from fastapi import WebSocket  # noqa: TC002
from pydantic import ValidationError
from sqlalchemy import select

from chitai.db.engine import get_session_ctx
from chitai.db.models import Item, Language, SessionItem
from chitai.db.models import Session as DBSession
from chitai.server.session import SessionState  # noqa: TC001
from chitai.server.websocket.protocol import incoming_message_adapter
from chitai.server.websocket.state import broadcast_state

logger = logging.getLogger(__name__)


async def handle_message(websocket: WebSocket, data: dict) -> None:
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
        await start_session(session_state, clients)
    elif message.type == "end_session":
        await end_session(session_state, clients)
    elif message.type == "add_item":
        await add_item(session_state, clients, message.payload.text)
    elif message.type == "next_item":
        await next_item(session_state, clients)
    elif message.type == "advance_word":
        await advance_word(session_state, clients, message.payload.delta)


async def start_session(session_state: SessionState, clients: set[WebSocket]) -> None:
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

    await broadcast_state(session_state, clients)


async def end_session(
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
            db_session.commit()

    logger.info("Session ended: %s", session_state.session_id)

    # Clear session state and broadcast to clients
    session_state.reset()
    await broadcast_state(session_state, clients)


async def add_item(
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
            await broadcast_state(session_state, clients)
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

    await broadcast_state(session_state, clients)


async def next_item(session_state: SessionState, clients: set[WebSocket]) -> None:
    """Advance to the next item in the queue.

    Completes the current SessionItem and pops the next item from the queue.
    If the queue is empty, logs a warning and does nothing.

    Parameters
    ----------
    session_state : SessionState
        The session state
    clients : set[WebSocket]
        Connected clients to broadcast to

    """
    if not session_state.queue:
        logger.warning("Cannot advance: queue is empty")
        await broadcast_state(session_state, clients)
        return

    with get_session_ctx() as db_session:
        # Complete current SessionItem if exists
        if session_state.current_session_item_id:
            current = db_session.get(SessionItem, session_state.current_session_item_id)
            if current:
                current.completed_at = datetime.now(UTC)

        # Pop next SessionItem from queue
        next_session_item_id = session_state.queue.pop(0)
        next_session_item = db_session.get(SessionItem, next_session_item_id)

        if not next_session_item:
            logger.error("SessionItem not found in database: %s", next_session_item_id)
            await broadcast_state(session_state, clients)
            return

        # Mark as displayed and set as current
        next_session_item.displayed_at = datetime.now(UTC)
        db_session.commit()

        session_state.current_session_item_id = next_session_item_id

        # Load item text
        item = db_session.get(Item, next_session_item.item_id)
        if not item:
            logger.error("Item not found in database: %s", next_session_item.item_id)
            session_state.reset()
            await broadcast_state(session_state, clients)
            return

        session_state.set_text(item.text)
        logger.info("Advanced to next item: %s", item.id)

    await broadcast_state(session_state, clients)


async def advance_word(
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
        await broadcast_state(session_state, clients)
