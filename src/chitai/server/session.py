"""Session state management for active sessions."""

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastapi import WebSocket

logger = logging.getLogger(__name__)


@dataclass
class SessionState:
    """In-memory state for an active session.

    Attributes
    ----------
    words : list[str]
        Words from the current text being displayed
    current_word_index : int
        Index of the currently highlighted word (0-based)
    controllers : set[WebSocket]
        Connected controller clients (phones)
    displays : set[WebSocket]
        Connected display clients (tablets)

    """

    words: list[str] = field(default_factory=list)
    current_word_index: int = 0
    controllers: set[WebSocket] = field(default_factory=set)
    displays: set[WebSocket] = field(default_factory=set)

    async def add_controller(self, websocket: WebSocket) -> None:
        """Add a controller client to the session.

        Parameters
        ----------
        websocket : WebSocket
            The controller's WebSocket connection

        """
        self.controllers.add(websocket)
        logger.info(
            "Controller connected. Total controllers: %d", len(self.controllers)
        )

    async def add_display(self, websocket: WebSocket) -> None:
        """Add a display client to the session.

        Parameters
        ----------
        websocket : WebSocket
            The display's WebSocket connection

        """
        self.displays.add(websocket)
        logger.info("Display connected. Total displays: %d", len(self.displays))
        # Send current state to newly connected display
        if self.words:
            await self._send_state(websocket)

    def remove_client(self, websocket: WebSocket) -> None:
        """Remove a client from the session.

        Parameters
        ----------
        websocket : WebSocket
            The client's WebSocket connection

        """
        self.controllers.discard(websocket)
        self.displays.discard(websocket)
        logger.info(
            "Client disconnected. Controllers: %d, Displays: %d",
            len(self.controllers),
            len(self.displays),
        )

    async def set_text(self, text: str) -> None:
        """Set the current text and broadcast to all displays.

        Splits text into words and resets the word index to 0.

        Parameters
        ----------
        text : str
            The text to display

        """
        self.words = text.split()
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
        """Broadcast current state to all connected displays."""
        for display in self.displays:
            await self._send_state(display)

    async def _send_state(self, websocket: WebSocket) -> None:
        """Send current state to a specific display.

        Parameters
        ----------
        websocket : WebSocket
            The display's WebSocket connection

        """
        message: dict[str, Any] = {
            "type": "state",
            "payload": {
                "words": self.words,
                "current_word_index": self.current_word_index,
            },
        }
        try:
            await websocket.send_json(message)
        except RuntimeError as e:
            logger.warning("Failed to send state: %s", e)

    def reset(self) -> None:
        """Reset session state."""
        self.words.clear()
        self.current_word_index = 0
        self.controllers.clear()
        self.displays.clear()
