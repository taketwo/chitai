"""Integration tests for WebSocket server."""

import asyncio

import pytest

from chitai.db.models import Item, SessionItem
from chitai.db.models import Session as DBSession
from chitai.server.app import app

from .helpers import (
    connect_clients,
    connect_controller,
    connect_display,
    started_session,
)


@pytest.mark.asyncio
async def test_controller_connection():
    """Test that controller can connect successfully."""
    async with connect_controller() as controller_ws:
        assert controller_ws is not None


@pytest.mark.asyncio
async def test_display_connection():
    """Test that display can connect successfully."""
    async with connect_display() as display_ws:
        assert display_ws is not None


@pytest.mark.asyncio
async def test_controller_sets_state():
    """Test that controller can set text state and receives state broadcast."""
    async with started_session() as (controller_ws, _, _):
        await controller_ws.send_json(
            {
                "type": "add_item",
                "payload": {"text": "молоко хлеб"},
            }
        )
        data = await controller_ws.receive_json()
        assert data["type"] == "state"
        assert data["payload"]["words"] == ["молоко", "хлеб"]
        assert app.state.session.words == ["молоко", "хлеб"]
        assert app.state.session.current_word_index == 0


@pytest.mark.asyncio
async def test_display_receives_state():
    """Test that display receives current state on connect."""
    await app.state.session.set_text("черепаха молоко")

    async with connect_display() as display_ws:
        data = await display_ws.receive_json()
        assert data["type"] == "state"
        assert data["payload"]["words"] == ["черепаха", "молоко"]
        assert data["payload"]["current_word_index"] == 0


@pytest.mark.asyncio
async def test_controller_to_display_flow():
    """Test basic flow: controller sends text, display receives it."""
    async with started_session() as (controller_ws, display_ws, _):
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
async def test_advance_word_forward():
    """Test advancing to next word broadcasts state."""
    async with started_session() as (controller_ws, display_ws, _):
        await controller_ws.send_json(
            {"type": "add_item", "payload": {"text": "один два три"}}
        )
        await display_ws.receive_json()  # State after add_item

        await controller_ws.send_json({"type": "advance_word", "payload": {"delta": 1}})

        data = await display_ws.receive_json()
        assert data["type"] == "state"
        assert data["payload"]["current_word_index"] == 1


@pytest.mark.asyncio
async def test_advance_word_backward():
    """Test going back to previous word broadcasts state."""
    async with started_session() as (controller_ws, display_ws, _):
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
async def test_start_session(db_session):
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
async def test_end_session(db_session):
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
async def test_start_session_broadcasts_to_all_clients():
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
async def test_ignore_duplicate_start_session():
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


@pytest.mark.asyncio
async def test_reconnecting_client_receives_current_state():
    """Test that clients connecting to active session receive current state."""
    async with connect_controller() as controller_ws:
        await controller_ws.receive_json()  # Initial state

        # Start a session
        await controller_ws.send_json({"type": "start_session"})
        data = await controller_ws.receive_json()
        session_id = data["payload"]["session_id"]

    # Session is still active, connect a new client
    async with connect_controller() as new_controller_ws:
        # New client should immediately receive current state with session_id
        data = await new_controller_ws.receive_json()
        assert data["type"] == "state"
        assert data["payload"]["session_id"] == session_id


@pytest.mark.asyncio
async def test_add_item_creates_item_and_session_item(db_session):
    """Test that add_item creates Item and SessionItem in database."""
    async with started_session() as (controller_ws, _, session_id):
        await controller_ws.send_json(
            {"type": "add_item", "payload": {"text": "молоко"}}
        )
        await controller_ws.receive_json()  # state broadcast

        # Verify Item was created
        item = db_session.query(Item).filter_by(text="молоко").first()
        assert item is not None
        assert item.language == "ru"

        # Verify SessionItem was created
        session_item = (
            db_session.query(SessionItem)
            .filter_by(session_id=session_id, item_id=item.id)
            .first()
        )
        assert session_item is not None
        assert session_item.displayed_at is not None
        assert session_item.completed_at is None

        # Verify current_item_id is set
        assert app.state.session.current_item_id == item.id


@pytest.mark.asyncio
async def test_add_item_reuses_existing_item(db_session):
    """Test that add_item reuses existing Item with same text."""
    async with started_session() as (controller_ws, _, session_id):
        # Add same item twice
        await controller_ws.send_json({"type": "add_item", "payload": {"text": "хлеб"}})
        await controller_ws.receive_json()

        await controller_ws.send_json({"type": "add_item", "payload": {"text": "хлеб"}})
        await controller_ws.receive_json()

        # Verify only one Item was created
        items = db_session.query(Item).filter_by(text="хлеб").all()
        assert len(items) == 1
        item = items[0]

        # Verify two SessionItems were created for the same Item
        session_items = (
            db_session.query(SessionItem)
            .filter_by(session_id=session_id, item_id=item.id)
            .all()
        )
        assert len(session_items) == 2


@pytest.mark.asyncio
async def test_add_item_completes_previous_session_item(db_session):
    """Test that adding new item completes the previous SessionItem."""
    async with started_session() as (controller_ws, _, session_id):
        # Add first item
        await controller_ws.send_json(
            {"type": "add_item", "payload": {"text": "первый"}}
        )
        await controller_ws.receive_json()

        # Get first item's SessionItem
        item1 = db_session.query(Item).filter_by(text="первый").first()
        assert item1 is not None
        session_item1 = (
            db_session.query(SessionItem)
            .filter_by(session_id=session_id, item_id=item1.id)
            .first()
        )
        assert session_item1 is not None
        assert session_item1.completed_at is None
        session_item1_id = session_item1.id

        # Add second item
        await controller_ws.send_json(
            {"type": "add_item", "payload": {"text": "второй"}}
        )
        await controller_ws.receive_json()

        # Verify first SessionItem is now completed
        db_session.expire_all()  # Refresh data from database
        session_item1 = db_session.get(SessionItem, session_item1_id)
        assert session_item1 is not None
        assert session_item1.completed_at is not None

        # Verify second SessionItem is not completed
        item2 = db_session.query(Item).filter_by(text="второй").first()
        assert item2 is not None
        session_item2 = (
            db_session.query(SessionItem)
            .filter_by(session_id=session_id, item_id=item2.id)
            .first()
        )
        assert session_item2 is not None
        assert session_item2.completed_at is None


@pytest.mark.asyncio
async def test_end_session_completes_all_session_items(db_session):
    """Test that ending session completes all incomplete SessionItems."""
    async with started_session() as (controller_ws, _, session_id):
        # Add two items
        await controller_ws.send_json({"type": "add_item", "payload": {"text": "один"}})
        await controller_ws.receive_json()

        await controller_ws.send_json({"type": "add_item", "payload": {"text": "два"}})
        await controller_ws.receive_json()

        # End session
        await controller_ws.send_json({"type": "end_session"})
        await controller_ws.receive_json()

        # Verify all SessionItems are completed
        session_items = (
            db_session.query(SessionItem).filter_by(session_id=session_id).all()
        )
        assert len(session_items) == 2
        for session_item in session_items:
            assert session_item.completed_at is not None


@pytest.mark.asyncio
async def test_add_item_without_session_is_ignored(db_session):
    """Test that add_item without active session is ignored."""
    async with connect_controller() as controller_ws:
        await controller_ws.receive_json()  # Initial state

        # Try to add item without starting session
        await controller_ws.send_json(
            {"type": "add_item", "payload": {"text": "молоко"}}
        )

        # Should not receive state broadcast (ignored)
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(controller_ws.receive_json(), timeout=0.1)

        # Verify no Item was created
        items = db_session.query(Item).filter_by(text="молоко").all()
        assert len(items) == 0
