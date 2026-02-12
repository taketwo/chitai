"""WebSocket message handlers."""

import logging
import random
from datetime import UTC, datetime

from fastapi import WebSocket  # noqa: TC002
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session as SQLAlchemySession  # noqa: TC002

from chitai.db.engine import get_session_ctx
from chitai.db.models import Illustration, Item, ItemIllustration, Language, SessionItem
from chitai.db.models import Session as DBSession
from chitai.server.session import SessionState  # noqa: TC001
from chitai.server.websocket.protocol import incoming_message_adapter
from chitai.server.websocket.state import broadcast_state

logger = logging.getLogger(__name__)


def _select_random_illustration(
    db_session: SQLAlchemySession, item_id: str
) -> str | None:
    """Select a random illustration for an item.

    Parameters
    ----------
    db_session : SQLAlchemySession
        Database session
    item_id : str
        Item ID to fetch illustrations for

    Returns
    -------
    str | None
        Random illustration ID, or None if item has no illustrations

    """
    illustrations = db_session.scalars(
        select(Illustration.id)
        .join(ItemIllustration, Illustration.id == ItemIllustration.illustration_id)
        .where(ItemIllustration.item_id == item_id)
    ).all()

    if not illustrations:
        return None

    return random.choice(illustrations)  # noqa: S311


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
        await add_item(session_state, clients, message.payload.item_id)
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
        language = db_session_obj.language

    session_state.session_id = session_id
    session_state.language = language
    logger.info("Session started: %s (language: %s)", session_id, language)

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
    session_state: SessionState, clients: set[WebSocket], item_id: str
) -> None:
    """Add an item to the session queue.

    Creates a new SessionItem for the given item_id. If no item is currently displayed,
    displays the new item immediately. Otherwise, adds it to the queue.

    The item must already exist in the database (created via REST API).

    Parameters
    ----------
    session_state : SessionState
        The session state
    clients : set[WebSocket]
        Connected clients to broadcast to
    item_id : str
        The UUID of the item to add to the session

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

        # Fetch the item
        item = db_session.get(Item, item_id)
        if not item:
            logger.error("Item not found in database: %s", item_id)
            return

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
            illustration_id = _select_random_illustration(db_session, item.id)
            session_item.displayed_at = datetime.now(UTC)
            session_item.illustration_id = illustration_id
            db_session.commit()

            session_state.current_session_item_id = session_item.id
            session_state.current_illustration_id = illustration_id
            session_state.set_text(item.text)
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

    Pops the next item from the queue and displays it. If the queue is empty, logs a
    warning and does nothing.

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
        # Pop next SessionItem from queue
        next_session_item_id = session_state.queue.pop(0)
        next_session_item = db_session.get(SessionItem, next_session_item_id)

        if not next_session_item:
            logger.error("SessionItem not found in database: %s", next_session_item_id)
            await broadcast_state(session_state, clients)
            return

        # Load item text
        item = db_session.get(Item, next_session_item.item_id)
        if not item:
            logger.error("Item not found in database: %s", next_session_item.item_id)
            session_state.reset()
            await broadcast_state(session_state, clients)
            return

        # Select illustration and mark as displayed
        illustration_id = _select_random_illustration(db_session, item.id)
        next_session_item.displayed_at = datetime.now(UTC)
        next_session_item.illustration_id = illustration_id
        db_session.commit()

        session_state.current_session_item_id = next_session_item_id
        session_state.current_illustration_id = illustration_id
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
        # If item just became completed, persist to database
        if session_state.current_word_index is None:
            with get_session_ctx() as db_session:
                if session_state.current_session_item_id:
                    current = db_session.get(
                        SessionItem, session_state.current_session_item_id
                    )
                    if current:
                        current.completed_at = datetime.now(UTC)
                        db_session.commit()
                        logger.info(
                            "Item completed: %s", session_state.current_session_item_id
                        )

        await broadcast_state(session_state, clients)
