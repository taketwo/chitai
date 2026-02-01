"""WebSocket state management utilities."""

import logging

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from chitai.db.engine import get_session_ctx
from chitai.db.models import SessionItem
from chitai.server.session import SessionState  # noqa: TC001
from chitai.server.websocket.protocol import (
    SessionItemInfo,
    StateMessage,
    StatePayload,
)

logger = logging.getLogger(__name__)


def build_state_payload(session_state: SessionState) -> StatePayload:
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
        language=session_state.language,
        words=session_state.words,
        syllables=session_state.syllables,
        current_word_index=session_state.current_word_index,
        queue=queue_items,
    )


async def broadcast_state(session_state: SessionState, clients: set[WebSocket]) -> None:
    """Send current session state to one or more clients.

    Parameters
    ----------
    session_state : SessionState
        The session state to send
    clients : set[WebSocket]
        Connected clients to send to

    """
    payload = build_state_payload(session_state)
    message = StateMessage(type="state", payload=payload)
    message_dict = message.model_dump(mode="json")

    for client in clients:
        try:
            await client.send_json(message_dict)
        except (WebSocketDisconnect, RuntimeError) as e:
            logger.warning("Failed to send state: %s", e)
