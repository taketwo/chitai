"""Helper utilities for integration tests."""

from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import TYPE_CHECKING

from httpx import AsyncClient
from httpx_ws import aconnect_ws
from httpx_ws.transport import ASGIWebSocketTransport

from chitai.server.app import app

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from httpx_ws import AsyncWebSocketSession


@asynccontextmanager
async def _connect_ws(role: str) -> AsyncGenerator[AsyncWebSocketSession]:
    """Connect a WebSocket client with the given role."""
    async with (
        ASGIWebSocketTransport(app=app) as transport,
        AsyncClient(transport=transport, base_url="http://test") as client,
        aconnect_ws(f"http://test/ws?role={role}", client) as ws,
    ):
        yield ws


def connect_controller() -> AbstractAsyncContextManager[AsyncWebSocketSession]:
    """Return async context manager for a controller WebSocket connection."""
    return _connect_ws("controller")


def connect_display() -> AbstractAsyncContextManager[AsyncWebSocketSession]:
    """Return async context manager for a display WebSocket connection."""
    return _connect_ws("display")


@asynccontextmanager
async def connect_clients() -> AsyncGenerator[
    tuple[AsyncWebSocketSession, AsyncWebSocketSession]
]:
    """Connect both controller and display WebSocket clients sharing a transport.

    Returns (controller_ws, display_ws) tuple.
    """
    async with (
        ASGIWebSocketTransport(app=app) as transport,
        AsyncClient(transport=transport, base_url="http://test") as client,
        aconnect_ws("http://test/ws?role=controller", client) as controller_ws,
        aconnect_ws("http://test/ws?role=display", client) as display_ws,
    ):
        yield controller_ws, display_ws


@asynccontextmanager
async def started_session() -> AsyncGenerator[
    tuple[AsyncWebSocketSession, AsyncWebSocketSession, str]
]:
    """Connect controller and display, start a session.

    Returns (controller_ws, display_ws, session_id) tuple. Use this when the test needs
    an active session but starting the session is not what's being tested.
    """
    async with connect_clients() as (controller_ws, display_ws):
        # Consume initial state messages
        await controller_ws.receive_json()
        await display_ws.receive_json()

        # Start session
        await controller_ws.send_json({"type": "start_session"})
        controller_data = await controller_ws.receive_json()
        await display_ws.receive_json()
        session_id = controller_data["payload"]["session_id"]
        yield controller_ws, display_ws, session_id


@asynccontextmanager
async def http_client() -> AsyncGenerator[AsyncClient]:
    """Provide HTTP client for REST API tests.

    Yields
    ------
    AsyncClient
        HTTP client configured to communicate with the FastAPI app

    """
    async with (
        ASGIWebSocketTransport(app=app) as transport,
        AsyncClient(transport=transport, base_url="http://test") as client,
    ):
        yield client
