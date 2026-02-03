"""Integration tests for WebSocket functionality."""

import asyncio

import pytest
from sqlalchemy import select

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
        assert app.state.context.session.words == ["молоко", "хлеб"]
        assert app.state.context.session.current_word_index == 0


@pytest.mark.asyncio
async def test_display_receives_state():
    """Test that display receives current state on connect."""
    app.state.context.session.set_text("черепаха молоко")

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
        assert initial_state["payload"]["language"] is None
        assert initial_state["payload"]["words"] == []
        assert initial_state["payload"]["current_word_index"] is None
        assert initial_state["payload"]["queue"] == []

        await controller_ws.send_json({"type": "start_session"})

        data = await controller_ws.receive_json()
        assert data["type"] == "state"
        assert data["payload"]["session_id"] is not None
        assert data["payload"]["language"] == "ru"
        session_id = data["payload"]["session_id"]
        assert data["payload"]["words"] == []
        assert data["payload"]["current_word_index"] is None
        assert data["payload"]["queue"] == []

        assert app.state.context.session.session_id == session_id

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
        assert data["payload"]["language"] is None
        assert app.state.context.session.session_id is None

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

        assert app.state.context.session.session_id == session_id1


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
        item = db_session.scalars(select(Item).where(Item.text == "молоко")).first()
        assert item is not None
        assert item.language == "ru"

        # Verify SessionItem was created
        session_item = db_session.scalars(
            select(SessionItem).where(
                SessionItem.session_id == session_id, SessionItem.item_id == item.id
            )
        ).first()
        assert session_item is not None
        assert session_item.displayed_at is not None
        assert session_item.completed_at is None

        # Verify current_session_item_id is set
        assert app.state.context.session.current_session_item_id == session_item.id


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
        items = db_session.scalars(select(Item).where(Item.text == "хлеб")).all()
        assert len(items) == 1
        item = items[0]

        # Verify two SessionItems were created for the same Item
        session_items = db_session.scalars(
            select(SessionItem).where(
                SessionItem.session_id == session_id, SessionItem.item_id == item.id
            )
        ).all()
        assert len(session_items) == 2


@pytest.mark.asyncio
async def test_add_item_queues_when_item_displayed(db_session):
    """Test that adding item when one is displayed adds to queue."""
    async with started_session() as (controller_ws, _, session_id):
        # Add first item
        await controller_ws.send_json(
            {"type": "add_item", "payload": {"text": "первый"}}
        )
        state = await controller_ws.receive_json()
        assert state["payload"]["queue"] == []

        # Get first item's SessionItem
        item1 = db_session.scalars(select(Item).where(Item.text == "первый")).first()
        assert item1 is not None
        session_item1 = db_session.scalars(
            select(SessionItem).where(
                SessionItem.session_id == session_id, SessionItem.item_id == item1.id
            )
        ).first()
        assert session_item1 is not None
        assert session_item1.displayed_at is not None
        assert session_item1.completed_at is None
        session_item1_id = session_item1.id

        # Add second item
        await controller_ws.send_json(
            {"type": "add_item", "payload": {"text": "второй"}}
        )
        state = await controller_ws.receive_json()

        # Verify first SessionItem is still active (not completed)
        db_session.expire_all()  # Refresh data from database
        session_item1 = db_session.get(SessionItem, session_item1_id)
        assert session_item1 is not None
        assert session_item1.completed_at is None

        # Verify second item was added to queue
        assert len(state["payload"]["queue"]) == 1
        assert state["payload"]["queue"][0]["text"] == "второй"

        item2 = db_session.scalars(select(Item).where(Item.text == "второй")).first()
        assert item2 is not None
        session_item2 = db_session.scalars(
            select(SessionItem).where(
                SessionItem.session_id == session_id, SessionItem.item_id == item2.id
            )
        ).first()
        assert session_item2 is not None
        assert session_item2.displayed_at is None
        assert session_item2.completed_at is None


@pytest.mark.asyncio
async def test_next_item_advances_through_queue(db_session):
    """Test that next_item advances through queued items."""
    async with started_session() as (controller_ws, _, session_id):
        # Add three items
        await controller_ws.send_json({"type": "add_item", "payload": {"text": "один"}})
        state = await controller_ws.receive_json()
        assert state["payload"]["words"] == ["один"]
        assert len(state["payload"]["queue"]) == 0

        await controller_ws.send_json({"type": "add_item", "payload": {"text": "два"}})
        state = await controller_ws.receive_json()
        assert len(state["payload"]["queue"]) == 1

        await controller_ws.send_json({"type": "add_item", "payload": {"text": "три"}})
        state = await controller_ws.receive_json()
        assert len(state["payload"]["queue"]) == 2

        # Get SessionItem IDs for verification
        item1 = db_session.scalars(select(Item).where(Item.text == "один")).first()
        item2 = db_session.scalars(select(Item).where(Item.text == "два")).first()

        session_item1 = db_session.scalars(
            select(SessionItem).where(
                SessionItem.session_id == session_id, SessionItem.item_id == item1.id
            )
        ).first()
        session_item2 = db_session.scalars(
            select(SessionItem).where(
                SessionItem.session_id == session_id, SessionItem.item_id == item2.id
            )
        ).first()

        # Advance to next item
        await controller_ws.send_json({"type": "next_item"})
        state = await controller_ws.receive_json()

        # Verify first item completed, second item displayed
        db_session.expire_all()
        session_item1 = db_session.get(SessionItem, session_item1.id)
        session_item2 = db_session.get(SessionItem, session_item2.id)

        assert session_item1.completed_at is not None
        assert session_item2.displayed_at is not None
        assert session_item2.completed_at is None
        assert state["payload"]["words"] == ["два"]
        assert len(state["payload"]["queue"]) == 1

        # Advance to third item
        await controller_ws.send_json({"type": "next_item"})
        state = await controller_ws.receive_json()

        assert state["payload"]["words"] == ["три"]
        assert len(state["payload"]["queue"]) == 0


@pytest.mark.asyncio
async def test_next_item_with_empty_queue():
    """Test that next_item with empty queue does nothing."""
    async with started_session() as (controller_ws, _, _):
        # Add one item
        await controller_ws.send_json({"type": "add_item", "payload": {"text": "один"}})
        state = await controller_ws.receive_json()
        assert state["payload"]["words"] == ["один"]

        # Try to advance with empty queue
        await controller_ws.send_json({"type": "next_item"})
        state = await controller_ws.receive_json()

        # Should still show same item
        assert state["payload"]["words"] == ["один"]


@pytest.mark.asyncio
async def test_end_session_does_not_complete_items(db_session):
    """Test that ending session does NOT auto-complete SessionItems.

    Items are only completed when explicitly advanced via next_item. Ending a session
    should leave incomplete items as evidence of what was displayed/queued but not
    finished.
    """
    async with started_session() as (controller_ws, _, session_id):
        # Add two items (first displayed, second queued)
        await controller_ws.send_json({"type": "add_item", "payload": {"text": "один"}})
        await controller_ws.receive_json()

        await controller_ws.send_json({"type": "add_item", "payload": {"text": "два"}})
        await controller_ws.receive_json()

        # End session without advancing
        await controller_ws.send_json({"type": "end_session"})
        await controller_ws.receive_json()

        # Verify SessionItems are NOT auto-completed
        session_items = db_session.scalars(
            select(SessionItem).where(SessionItem.session_id == session_id)
        ).all()
        assert len(session_items) == 2

        # First item was displayed but not completed
        item1 = db_session.scalars(select(Item).where(Item.text == "один")).first()
        session_item1 = db_session.scalars(
            select(SessionItem).where(
                SessionItem.session_id == session_id, SessionItem.item_id == item1.id
            )
        ).first()
        assert session_item1.displayed_at is not None
        assert session_item1.completed_at is None

        # Second item was queued but never displayed
        item2 = db_session.scalars(select(Item).where(Item.text == "два")).first()
        session_item2 = db_session.scalars(
            select(SessionItem).where(
                SessionItem.session_id == session_id, SessionItem.item_id == item2.id
            )
        ).first()
        assert session_item2.displayed_at is None
        assert session_item2.completed_at is None


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
        items = db_session.scalars(select(Item).where(Item.text == "молоко")).all()
        assert len(items) == 0


@pytest.mark.asyncio
async def test_add_item_with_missing_database_session_resets_state(db_session):
    """Test that missing database session triggers state reset and broadcast."""
    async with started_session() as (controller_ws, display_ws, session_id):
        # Manually delete the database session to simulate corruption
        db_session_obj = db_session.get(DBSession, session_id)
        assert db_session_obj is not None
        db_session.delete(db_session_obj)
        db_session.commit()

        # Try to add an item - should trigger the missing session error path
        await controller_ws.send_json(
            {"type": "add_item", "payload": {"text": "молоко"}}
        )

        # Should receive state broadcast with reset state
        controller_data = await controller_ws.receive_json()
        assert controller_data["type"] == "state"
        assert controller_data["payload"]["session_id"] is None
        assert controller_data["payload"]["language"] is None
        assert controller_data["payload"]["words"] == []

        display_data = await display_ws.receive_json()
        assert display_data["type"] == "state"
        assert display_data["payload"]["session_id"] is None
        assert display_data["payload"]["language"] is None

        # Verify in-memory state was reset
        assert app.state.context.session.session_id is None


@pytest.mark.asyncio
async def test_grace_period_auto_ends_inactive_session(db_session):
    """Test that inactive sessions are automatically ended after grace period."""
    app.state.context.grace_timer.grace_period_seconds = 0.1

    async with started_session() as (controller_ws, _, session_id):
        await controller_ws.send_json(
            {"type": "add_item", "payload": {"text": "молоко"}}
        )
        await controller_ws.receive_json()

    # Session should still be active, regardless of client disconnection
    assert app.state.context.session.session_id is not None

    # Wait for grace period to expire
    await asyncio.sleep(0.15)

    # Session should be auto-ended
    assert app.state.context.session.session_id is None

    # Verify in database
    db_session.expire_all()
    session_obj = db_session.get(DBSession, session_id)
    assert session_obj.ended_at is not None


@pytest.mark.asyncio
async def test_grace_timer_not_started_without_active_session():
    """Test that grace timer doesn't start if no session is active."""
    app.state.context.grace_timer.grace_period_seconds = 0.1

    # Connect and disconnect without starting a session
    async with connect_controller() as controller_ws:
        await controller_ws.receive_json()  # Initial state

    # Grace timer should not be running
    assert not app.state.context.grace_timer.is_running


@pytest.mark.asyncio
async def test_complete_session_flow_end_to_end(db_session):  # noqa: PLR0915
    """Test complete realistic session flow from start to finish.

    This test simulates a typical parent-child reading session:
    1. Start session
    2. Add multiple items to build a queue
    3. Read through first item word-by-word
    4. Advance to next queued item
    5. Complete that item
    6. End session
    7. Verify all database state is correct
    """
    async with started_session() as (controller_ws, _, session_id):
        # Build a queue with three items
        await controller_ws.send_json(
            {"type": "add_item", "payload": {"text": "черепаха ползёт"}}
        )
        state = await controller_ws.receive_json()

        assert state["payload"]["words"] == ["черепаха", "ползёт"]
        assert state["payload"]["current_word_index"] == 0
        assert len(state["payload"]["queue"]) == 0

        await controller_ws.send_json(
            {"type": "add_item", "payload": {"text": "мама готовит обед"}}
        )
        state = await controller_ws.receive_json()

        assert len(state["payload"]["queue"]) == 1
        assert state["payload"]["queue"][0]["text"] == "мама готовит обед"

        await controller_ws.send_json(
            {"type": "add_item", "payload": {"text": "солнце светит"}}
        )
        state = await controller_ws.receive_json()

        assert len(state["payload"]["queue"]) == 2

        # Read through first item word-by-word
        assert state["payload"]["current_word_index"] == 0

        await controller_ws.send_json({"type": "advance_word", "payload": {"delta": 1}})
        state = await controller_ws.receive_json()

        assert state["payload"]["current_word_index"] == 1
        assert state["payload"]["words"] == ["черепаха", "ползёт"]

        # Go back to first word (parent correcting)
        await controller_ws.send_json(
            {"type": "advance_word", "payload": {"delta": -1}}
        )
        state = await controller_ws.receive_json()

        assert state["payload"]["current_word_index"] == 0

        # Advance to second word again
        await controller_ws.send_json({"type": "advance_word", "payload": {"delta": 1}})
        state = await controller_ws.receive_json()

        assert state["payload"]["current_word_index"] == 1

        # Advance to next item in queue
        await controller_ws.send_json({"type": "next_item"})
        state = await controller_ws.receive_json()

        assert state["payload"]["words"] == ["мама", "готовит", "обед"]
        assert state["payload"]["current_word_index"] == 0
        assert len(state["payload"]["queue"]) == 1
        assert state["payload"]["queue"][0]["text"] == "солнце светит"

        # Read through second item quickly ("мама готовит обед" has 3 words)
        await controller_ws.send_json({"type": "advance_word", "payload": {"delta": 1}})
        await controller_ws.receive_json()

        await controller_ws.send_json({"type": "advance_word", "payload": {"delta": 1}})
        state = await controller_ws.receive_json()

        assert state["payload"]["current_word_index"] == 2

        # Advance to third item
        await controller_ws.send_json({"type": "next_item"})
        state = await controller_ws.receive_json()

        assert state["payload"]["words"] == ["солнце", "светит"]
        assert state["payload"]["current_word_index"] == 0
        assert len(state["payload"]["queue"]) == 0

        # End session
        await controller_ws.send_json({"type": "end_session"})
        state = await controller_ws.receive_json()

        assert state["payload"]["session_id"] is None
        assert state["payload"]["language"] is None
        assert app.state.context.session.session_id is None

    # Verify database state
    db_session.expire_all()

    session_obj = db_session.get(DBSession, session_id)
    assert session_obj is not None
    assert session_obj.ended_at is not None

    items = db_session.scalars(select(Item)).all()
    assert len(items) == 3

    items_by_text = {item.text: item for item in items}
    assert "черепаха ползёт" in items_by_text
    assert "мама готовит обед" in items_by_text
    assert "солнце светит" in items_by_text

    session_items = db_session.scalars(
        select(SessionItem).where(SessionItem.session_id == session_id)
    ).all()
    assert len(session_items) == 3

    item1 = items_by_text["черепаха ползёт"]
    item2 = items_by_text["мама готовит обед"]
    item3 = items_by_text["солнце светит"]

    session_item1 = db_session.scalars(
        select(SessionItem).where(
            SessionItem.session_id == session_id, SessionItem.item_id == item1.id
        )
    ).first()
    session_item2 = db_session.scalars(
        select(SessionItem).where(
            SessionItem.session_id == session_id, SessionItem.item_id == item2.id
        )
    ).first()
    session_item3 = db_session.scalars(
        select(SessionItem).where(
            SessionItem.session_id == session_id, SessionItem.item_id == item3.id
        )
    ).first()

    # First two items completed, third displayed but not completed
    assert session_item1.displayed_at is not None
    assert session_item1.completed_at is not None

    assert session_item2.displayed_at is not None
    assert session_item2.completed_at is not None

    assert session_item3.displayed_at is not None
    assert session_item3.completed_at is None


@pytest.mark.asyncio
async def test_completed_state_flow():
    """Test item completed state flow.

    This test verifies the completed state behavior:
    1. Advance through words to last word
    2. Advance past last word to mark as completed (current_word_index becomes None)
    3. Verify cannot go back from completed state
    4. Add item to queue while in completed state
    5. Advance from completed state to next queued item
    """
    async with started_session() as (controller_ws, _, _):
        # Add first item
        await controller_ws.send_json(
            {"type": "add_item", "payload": {"text": "один два три"}}
        )
        state = await controller_ws.receive_json()

        assert state["payload"]["words"] == ["один", "два", "три"]
        assert state["payload"]["current_word_index"] == 0
        assert len(state["payload"]["queue"]) == 0

        # Advance to second word
        await controller_ws.send_json({"type": "advance_word", "payload": {"delta": 1}})
        state = await controller_ws.receive_json()
        assert state["payload"]["current_word_index"] == 1

        # Advance to last word
        await controller_ws.send_json({"type": "advance_word", "payload": {"delta": 1}})
        state = await controller_ws.receive_json()
        assert state["payload"]["current_word_index"] == 2

        # Advance past last word - mark as completed (current_word_index → None)
        await controller_ws.send_json({"type": "advance_word", "payload": {"delta": 1}})
        state = await controller_ws.receive_json()
        assert state["payload"]["current_word_index"] is None
        assert state["payload"]["words"] == ["один", "два", "три"]

        # Try to go back - should not work (no state broadcast expected)
        await controller_ws.send_json(
            {"type": "advance_word", "payload": {"delta": -1}}
        )

        # Should not receive any state update since advance failed
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(controller_ws.receive_json(), timeout=0.1)

        # Add item to queue while in completed state
        await controller_ws.send_json(
            {"type": "add_item", "payload": {"text": "новый текст"}}
        )
        state = await controller_ws.receive_json()

        # Should still be in completed state, with new item in queue
        assert state["payload"]["current_word_index"] is None
        assert state["payload"]["words"] == ["один", "два", "три"]
        assert len(state["payload"]["queue"]) == 1
        assert state["payload"]["queue"][0]["text"] == "новый текст"

        # Advance from completed state to next item
        await controller_ws.send_json({"type": "next_item"})
        state = await controller_ws.receive_json()

        # Should now be on the new item at first word
        assert state["payload"]["words"] == ["новый", "текст"]
        assert state["payload"]["current_word_index"] == 0
        assert len(state["payload"]["queue"]) == 0
