"""Integration tests for WebSocket server."""

import pytest
from httpx import AsyncClient
from httpx_ws import aconnect_ws
from httpx_ws.transport import ASGIWebSocketTransport

from chitai.server.app import app


@pytest.fixture(autouse=True)
def reset_session():
    """Reset session state before each test."""
    app.state.session.reset()
    yield
    app.state.session.reset()


@pytest.mark.asyncio
async def test_controller_connection():
    """Test that controller can connect successfully."""
    async with (
        ASGIWebSocketTransport(app=app) as transport,
        AsyncClient(transport=transport, base_url="http://test") as client,
        aconnect_ws("http://test/ws?role=controller", client) as ws,
    ):
        assert ws is not None


@pytest.mark.asyncio
async def test_display_connection():
    """Test that display can connect successfully."""
    async with (
        ASGIWebSocketTransport(app=app) as transport,
        AsyncClient(transport=transport, base_url="http://test") as client,
        aconnect_ws("http://test/ws?role=display", client) as ws,
    ):
        assert ws is not None


@pytest.mark.asyncio
async def test_websocket_controller_sets_state():
    """Test that controller can set text state."""
    async with (
        ASGIWebSocketTransport(app=app) as transport,
        AsyncClient(transport=transport, base_url="http://test") as client,
        aconnect_ws("http://test/ws?role=controller", client) as ws,
    ):
        await ws.send_json(
            {
                "type": "add_item",
                "payload": {"text": "молоко"},
            }
        )

    assert app.state.session.current_text == "молоко"


@pytest.mark.asyncio
async def test_websocket_display_receives_state():
    """Test that display receives current state on connect."""
    app.state.session.current_text = "черепаха"

    async with (
        ASGIWebSocketTransport(app=app) as transport,
        AsyncClient(transport=transport, base_url="http://test") as client,
        aconnect_ws("http://test/ws?role=display", client) as ws,
    ):
        data = await ws.receive_json()
        assert data["type"] == "state"
        assert data["payload"]["current_text"] == "черепаха"


@pytest.mark.asyncio
async def test_websocket_controller_to_display_flow():
    """Test basic flow: controller sends text, display receives it."""
    async with (
        ASGIWebSocketTransport(app=app) as transport,
        AsyncClient(transport=transport, base_url="http://test") as client,
        aconnect_ws("http://test/ws?role=display", client) as display_ws,
        aconnect_ws("http://test/ws?role=controller", client) as controller_ws,
    ):
        await controller_ws.send_json(
            {
                "type": "add_item",
                "payload": {"text": "привет"},
            }
        )

        data = await display_ws.receive_json()
        assert data["type"] == "state"
        assert data["payload"]["current_text"] == "привет"
