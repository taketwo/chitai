"""Session state management for active sessions."""

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from chitai.language import sanitize, syllabify, tokenize

if TYPE_CHECKING:
    from fastapi import WebSocket

logger = logging.getLogger(__name__)


@dataclass
class SessionState:
    """In-memory state for an active session.

    Attributes
    ----------
    session_id : str | None
        Database session ID (None if no active session)
    current_item_id : str | None
        Current item being displayed (None if no item)
    words : list[str]
        Words from the current text being displayed
    current_word_index : int
        Index of the currently highlighted word (0-based)
    clients : set[WebSocket]
        Connected clients (controllers and displays)

    """

    session_id: str | None = None
    current_item_id: str | None = None
    words: list[str] = field(default_factory=list)
    current_word_index: int = 0
    clients: set[WebSocket] = field(default_factory=set)

    async def add_client(self, websocket: WebSocket, role: str) -> None:
        """Add a client to the session.

        Parameters
        ----------
        websocket : WebSocket
            The client's WebSocket connection
        role : str
            Client role (for logging): 'controller' or 'display'

        """
        self.clients.add(websocket)
        logger.info(
            "%s connected. Total clients: %d", role.capitalize(), len(self.clients)
        )
        # Send current state to newly connected client
        if self.words:
            await self._send_state(websocket)

    def remove_client(self, websocket: WebSocket) -> None:
        """Remove a client from the session.

        Parameters
        ----------
        websocket : WebSocket
            The client's WebSocket connection

        """
        self.clients.discard(websocket)
        logger.info("Client disconnected. Total clients: %d", len(self.clients))

    async def set_text(self, text: str) -> None:
        """Set the current text and broadcast to all displays.

        Sanitizes and tokenizes text into words, resets the word index to 0.

        Parameters
        ----------
        text : str
            The text to display

        """
        self.words = tokenize(sanitize(text))
        self.current_word_index = 0
        logger.info("Text updated: %d words", len(self.words))
        await self._broadcast_state()

    async def advance_word(self, delta: int = 1) -> None:
        """Move to a different word by a given offset (with clamping).

        Parameters
        ----------
        delta : int
            Number of words to advance (positive) or go back (negative)

        """
        if not self.words:
            logger.warning("Cannot advance word: no text set")
            return

        if delta == 0:
            logger.debug("Delta is 0: no change to word index")
            return

        new_index = max(0, min(self.current_word_index + delta, len(self.words) - 1))

        if new_index != self.current_word_index:
            self.current_word_index = new_index
            logger.info("Word index: %d/%d", new_index + 1, len(self.words))
            await self._broadcast_state()
        else:
            logger.debug("Word index unchanged: already at boundary")

    async def _broadcast_state(self) -> None:
        """Broadcast current state to all connected clients."""
        for client in self.clients:
            await self._send_state(client)

    async def _send_state(self, websocket: WebSocket) -> None:
        """Send current state to a specific client.

        Parameters
        ----------
        websocket : WebSocket
            The client's WebSocket connection

        """
        message: dict[str, Any] = {
            "type": "state",
            "payload": {
                "words": self.words,
                "syllables": [syllabify(word) for word in self.words],
                "current_word_index": self.current_word_index,
            },
        }
        try:
            await websocket.send_json(message)
        except RuntimeError as e:
            logger.warning("Failed to send state: %s", e)

    def reset(self) -> None:
        """Reset session state."""
        self.session_id = None
        self.current_item_id = None
        self.words.clear()
        self.current_word_index = 0
        self.clients.clear()
