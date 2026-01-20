"""Integration tests for WebSocket server."""

import asyncio

import pytest

from chitai.db.models import Session as DBSession
from chitai.server.app import app

from .helpers import connect_clients, connect_controller, connect_display


@pytest.mark.asyncio
async def test_controller_connection():
    """Test that controller can connect successfully."""
    async with connect_controller() as ws:
        assert ws is not None


@pytest.mark.asyncio
async def test_display_connection():
    """Test that display can connect successfully."""
    async with connect_display() as ws:
        assert ws is not None


@pytest.mark.asyncio
async def test_websocket_controller_sets_state():
    """Test that controller can set text state and receives state broadcast."""
    async with connect_controller() as ws:
        await ws.receive_json()  # Initial state

        await ws.send_json(
            {
                "type": "add_item",
                "payload": {"text": "молоко хлеб"},
            }
        )
        data = await ws.receive_json()
        assert data["type"] == "state"
        assert data["payload"]["words"] == ["молоко", "хлеб"]
        assert app.state.session.words == ["молоко", "хлеб"]
        assert app.state.session.current_word_index == 0


@pytest.mark.asyncio
async def test_websocket_display_receives_state():
    """Test that display receives current state on connect."""
    await app.state.session.set_text("черепаха молоко")

    async with connect_display() as ws:
        data = await ws.receive_json()
        assert data["type"] == "state"
        assert data["payload"]["words"] == ["черепаха", "молоко"]
        assert data["payload"]["current_word_index"] == 0


@pytest.mark.asyncio
async def test_websocket_controller_to_display_flow():
    """Test basic flow: controller sends text, display receives it."""
    async with connect_clients() as (controller_ws, display_ws):
        await display_ws.receive_json()  # Initial state
        await controller_ws.receive_json()  # Initial state

        await controller_ws.send_json(
            {
                "type": "add_item",
                "payload": {"text": "привет мир"},
            }
        )

        data = await display_ws.receive_json()
        assert data["type"] == "state"
        assert data["payload"]["words"] == ["привет", "мир"]
        assert data["payload"]["current_word_index"] == 0


@pytest.mark.asyncio
async def test_websocket_advance_word_forward():
    """Test advancing to next word broadcasts state."""
    async with connect_clients() as (controller_ws, display_ws):
        await display_ws.receive_json()  # Initial state
        await controller_ws.receive_json()  # Initial state

        await controller_ws.send_json(
            {"type": "add_item", "payload": {"text": "один два три"}}
        )
        await display_ws.receive_json()  # State after add_item

        await controller_ws.send_json({"type": "advance_word", "payload": {"delta": 1}})

        data = await display_ws.receive_json()
        assert data["type"] == "state"
        assert data["payload"]["current_word_index"] == 1


@pytest.mark.asyncio
async def test_websocket_advance_word_backward():
    """Test going back to previous word broadcasts state."""
    async with connect_clients() as (controller_ws, display_ws):
        await display_ws.receive_json()  # Initial state
        await controller_ws.receive_json()  # Initial state

        await controller_ws.send_json(
            {"type": "add_item", "payload": {"text": "один два три"}}
        )
        await display_ws.receive_json()  # State after add_item

        await controller_ws.send_json({"type": "advance_word", "payload": {"delta": 1}})
        await display_ws.receive_json()
        await controller_ws.send_json({"type": "advance_word", "payload": {"delta": 1}})
        await display_ws.receive_json()

        await controller_ws.send_json(
            {"type": "advance_word", "payload": {"delta": -1}}
        )

        data = await display_ws.receive_json()
        assert data["type"] == "state"
        assert data["payload"]["current_word_index"] == 1


@pytest.mark.asyncio
async def test_websocket_start_session(db_session):
    """Test that start_session creates a database session."""
    async with connect_controller() as controller_ws:
        initial_state = await controller_ws.receive_json()
        assert initial_state["type"] == "state"
        assert initial_state["payload"]["session_id"] is None

        await controller_ws.send_json({"type": "start_session"})

        data = await controller_ws.receive_json()
        assert data["type"] == "state"
        assert data["payload"]["session_id"] is not None
        session_id = data["payload"]["session_id"]

        assert app.state.session.session_id == session_id

        db_session_obj = db_session.get(DBSession, session_id)
        assert db_session_obj is not None
        assert db_session_obj.ended_at is None


@pytest.mark.asyncio
async def test_websocket_end_session(db_session):
    """Test that end_session marks session as ended."""
    async with connect_controller() as controller_ws:
        await controller_ws.receive_json()  # Initial state

        await controller_ws.send_json({"type": "start_session"})
        start_data = await controller_ws.receive_json()
        session_id = start_data["payload"]["session_id"]

        await controller_ws.send_json({"type": "end_session"})

        data = await controller_ws.receive_json()
        assert data["type"] == "state"
        assert data["payload"]["session_id"] is None
        assert app.state.session.session_id is None

        db_session_obj = db_session.get(DBSession, session_id)
        assert db_session_obj is not None
        assert db_session_obj.ended_at is not None


@pytest.mark.asyncio
async def test_websocket_start_session_broadcasts_to_all_clients():
    """Test that state is broadcast to all connected clients when session starts."""
    async with connect_clients() as (controller_ws, display_ws):
        await display_ws.receive_json()  # Initial state
        await controller_ws.receive_json()  # Initial state

        await controller_ws.send_json({"type": "start_session"})

        controller_data = await controller_ws.receive_json()
        display_data = await display_ws.receive_json()

        assert controller_data["type"] == "state"
        assert display_data["type"] == "state"
        assert controller_data["payload"]["session_id"] is not None
        assert (
            controller_data["payload"]["session_id"]
            == display_data["payload"]["session_id"]
        )


@pytest.mark.asyncio
async def test_websocket_ignore_duplicate_start_session():
    """Test that second start_session is ignored if session already active."""
    async with connect_controller() as controller_ws:
        await controller_ws.receive_json()  # Initial state

        await controller_ws.send_json({"type": "start_session"})
        data1 = await controller_ws.receive_json()
        session_id1 = data1["payload"]["session_id"]

        await controller_ws.send_json({"type": "start_session"})

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(controller_ws.receive_json(), timeout=0.1)

        assert app.state.session.session_id == session_id1
