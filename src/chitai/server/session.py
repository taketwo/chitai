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
    current_text : str | None
        The text currently being displayed
    controllers : set[WebSocket]
        Connected controller clients (phones)
    displays : set[WebSocket]
        Connected display clients (tablets)

    """

    current_text: str | None = None
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
        if self.current_text is not None:
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

        Parameters
        ----------
        text : str
            The text to display

        """
        self.current_text = text
        logger.info("Text updated: %s", text[:50])
        await self._broadcast_state()

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
                "current_text": self.current_text,
            },
        }
        try:
            await websocket.send_json(message)
        except RuntimeError as e:
            logger.warning("Failed to send state: %s", e)

    def reset(self) -> None:
        """Reset session state."""
        self.current_text = None
        self.controllers.clear()
        self.displays.clear()
