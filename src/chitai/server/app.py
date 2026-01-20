"""FastAPI application with WebSocket endpoint."""

import logging
from datetime import UTC, datetime

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from chitai.db.engine import get_session
from chitai.db.models import Item, Language, SessionItem
from chitai.db.models import Session as DBSession
from chitai.server.session import SessionState

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Chitai")

app.state.session = SessionState()

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
    session = websocket.app.state.session

    if role not in ("controller", "display"):
        logger.warning("Unknown role: %s", role)
        await websocket.close()
        return

    await session.add_client(websocket, role)

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
        session.remove_client(websocket)


async def _handle_message(websocket: WebSocket, data: dict) -> None:
    """Handle messages from any client.

    Parameters
    ----------
    websocket : WebSocket
        The client's WebSocket connection
    data : dict
        The message data

    """
    session_state = websocket.app.state.session
    message_type = data.get("type")

    if message_type == "start_session":
        await _handle_start_session(session_state)
    elif message_type == "end_session":
        await _handle_end_session(session_state)
    elif message_type == "add_item":
        text = data.get("payload", {}).get("text")
        if text:
            await _handle_add_item(session_state, text)
        else:
            logger.warning("add_item message missing text")
    elif message_type == "advance_word":
        delta = data.get("payload", {}).get("delta", 1)
        await session_state.advance_word(delta)
    else:
        logger.warning("Unknown message type: %s", message_type)


async def _handle_start_session(session_state: SessionState) -> None:
    """Handle start_session message.

    Parameters
    ----------
    session_state : SessionState
        The session state

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

    await session_state.broadcast_state()


async def _handle_end_session(session_state: SessionState) -> None:
    """Handle end_session message.

    Parameters
    ----------
    session_state : SessionState
        The session state

    """
    if session_state.session_id is None:
        logger.warning("No active session to end")
        return

    with get_session() as db_session:
        db_session_obj = db_session.get(DBSession, session_state.session_id)
        if db_session_obj:
            now = datetime.now(UTC)
            db_session_obj.ended_at = now

            # Complete any incomplete SessionItems
            incomplete_items = (
                db_session.query(SessionItem)
                .filter_by(session_id=session_state.session_id, completed_at=None)
                .all()
            )
            for session_item in incomplete_items:
                session_item.completed_at = now

            db_session.commit()

    logger.info("Session ended: %s", session_state.session_id)

    # Clear session_id before broadcasting so clients see None
    session_state.session_id = None
    session_state.current_item_id = None
    session_state.words.clear()
    session_state.current_word_index = 0

    await session_state.broadcast_state()


async def _handle_add_item(session_state: SessionState, text: str) -> None:
    """Handle add_item message.

    Creates or retrieves an Item, completes the previous SessionItem if any, and
    creates a new SessionItem for the current item.

    Parameters
    ----------
    session_state : SessionState
        The session state
    text : str
        The text to add

    """
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
        item = db_session.query(Item).filter_by(text=text, language=language).first()
        if not item:
            item = Item(text=text, language=language)
            db_session.add(item)
            db_session.flush()  # Get the item ID

        # Complete previous SessionItem if exists
        if session_state.current_item_id:
            prev_session_item = (
                db_session.query(SessionItem)
                .filter_by(
                    session_id=session_state.session_id,
                    item_id=session_state.current_item_id,
                    completed_at=None,
                )
                .first()
            )
            if prev_session_item:
                prev_session_item.completed_at = datetime.now(UTC)

        session_item = SessionItem(
            session_id=session_state.session_id,
            item_id=item.id,
        )
        db_session.add(session_item)
        db_session.commit()

        session_state.current_item_id = item.id

    await session_state.set_text(text)
