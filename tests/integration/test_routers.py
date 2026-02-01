"""Integration tests for REST API endpoints."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from chitai.db.models import Item, SessionItem
from chitai.db.models import Session as DBSession

from .helpers import http_client

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# Test constants
FAKE_UUID = "00000000-0000-0000-0000-000000000000"
DEFAULT_LANGUAGE = "ru"


def create_session(db_session: Session, *, ended: bool = False) -> DBSession:
    """Create a test database session.

    Parameters
    ----------
    db_session : Session
        Database session to use
    ended : bool
        Whether the session should be marked as ended

    Returns
    -------
    DBSession
        Created session object

    """
    session = DBSession(
        language=DEFAULT_LANGUAGE,
        started_at=datetime.now(UTC),
        ended_at=datetime.now(UTC) if ended else None,
    )
    db_session.add(session)
    db_session.commit()
    return session


def create_item(db_session: Session, text: str) -> Item:
    """Create a test item.

    Parameters
    ----------
    db_session : Session
        Database session to use
    text : str
        Item text

    Returns
    -------
    Item
        Created item object

    """
    item = Item(text=text, language=DEFAULT_LANGUAGE)
    db_session.add(item)
    db_session.commit()
    return item


def create_session_item(
    db_session: Session,
    session_id: str,
    item_id: str,
    displayed_at: datetime | None = None,
) -> SessionItem:
    """Create a session item linking a session to an item.

    Parameters
    ----------
    db_session : Session
        Database session to use
    session_id : str
        Session UUID
    item_id : str
        Item UUID
    displayed_at : datetime | None
        When the item was displayed (defaults to now)

    Returns
    -------
    SessionItem
        Created session item object

    """
    session_item = SessionItem(
        session_id=session_id,
        item_id=item_id,
        displayed_at=displayed_at or datetime.now(UTC),
    )
    db_session.add(session_item)
    db_session.commit()
    return session_item


class TestItemsEndpoints:
    """Tests for /api/items endpoints."""

    @pytest.mark.asyncio
    async def test_list_items_empty(self):
        """Test GET /api/items returns empty list when no items exist."""
        async with http_client() as client:
            response = await client.get("/api/items")

            assert response.status_code == 200
            data = response.json()
            assert data["items"] == []

    @pytest.mark.asyncio
    async def test_list_items_with_data(self, db_session: Session):
        """Test GET /api/items returns all items with usage stats."""
        # Create test items
        item1 = create_item(db_session, "молоко")
        item2 = create_item(db_session, "хлеб")
        create_item(db_session, "вода")  # item3 - never used

        # Create a session and link items with different usage counts
        session = create_session(db_session)

        # item1 used twice, item2 used once, item3 never used
        create_session_item(db_session, session.id, item1.id)
        create_session_item(db_session, session.id, item1.id)
        create_session_item(db_session, session.id, item2.id)

        async with http_client() as client:
            response = await client.get("/api/items")

            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) == 3

            # Find items in response
            items_by_text = {item["text"]: item for item in data["items"]}

            # Verify usage counts
            assert items_by_text["молоко"]["usage_count"] == 2
            assert items_by_text["молоко"]["last_used_at"] is not None

            assert items_by_text["хлеб"]["usage_count"] == 1
            assert items_by_text["хлеб"]["last_used_at"] is not None

            assert items_by_text["вода"]["usage_count"] == 0
            assert items_by_text["вода"]["last_used_at"] is None

    @pytest.mark.asyncio
    async def test_get_item_by_id(self, db_session: Session):
        """Test GET /api/items/{id} returns single item with correct stats."""
        item = create_item(db_session, "тестовый")
        session = create_session(db_session)
        create_session_item(db_session, session.id, item.id)

        async with http_client() as client:
            response = await client.get(f"/api/items/{item.id}")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == str(item.id)
            assert data["text"] == "тестовый"
            assert data["language"] == DEFAULT_LANGUAGE
            assert data["usage_count"] == 1
            assert data["last_used_at"] is not None

    @pytest.mark.asyncio
    async def test_get_item_not_found(self):
        """Test GET /api/items/{id} returns 404 for non-existent item."""
        async with http_client() as client:
            response = await client.get(f"/api/items/{FAKE_UUID}")

            assert response.status_code == 404
            assert response.json()["detail"] == "Item not found"

    @pytest.mark.asyncio
    async def test_usage_count_increments_correctly(self, db_session: Session):
        """Test usage_count increments correctly with multiple session items."""
        item = create_item(db_session, "повторяющийся")
        session1 = create_session(db_session)
        session2 = create_session(db_session)

        # Use item 3 times in each session (6 total)
        for session in [session1, session2]:
            for _ in range(3):
                create_session_item(db_session, session.id, item.id)

        async with http_client() as client:
            response = await client.get(f"/api/items/{item.id}")

            assert response.status_code == 200
            data = response.json()
            assert data["usage_count"] == 6

    @pytest.mark.asyncio
    async def test_last_used_at_reflects_most_recent_usage(self, db_session: Session):
        """Test last_used_at reflects most recent usage."""
        item = create_item(db_session, "временной")
        session = create_session(db_session)

        # Create session items with different timestamps
        early_time = datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC)
        late_time = datetime(2025, 1, 2, 15, 30, 0, tzinfo=UTC)

        create_session_item(db_session, session.id, item.id, early_time)
        create_session_item(db_session, session.id, item.id, late_time)

        async with http_client() as client:
            response = await client.get(f"/api/items/{item.id}")

            assert response.status_code == 200
            data = response.json()
            # SQLite stores without timezone
            assert data["last_used_at"] == "2025-01-02T15:30:00"

    @pytest.mark.asyncio
    async def test_delete_item(self, db_session: Session):
        """Test DELETE /api/items/{id} deletes item."""
        item = create_item(db_session, "удалить")

        async with http_client() as client:
            response = await client.delete(f"/api/items/{item.id}")

            assert response.status_code == 200
            assert response.json() == {"status": "deleted"}

            # Verify item is deleted
            response = await client.get(f"/api/items/{item.id}")
            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_item_not_found(self):
        """Test DELETE /api/items/{id} returns 404 for non-existent item."""
        async with http_client() as client:
            response = await client.delete(f"/api/items/{FAKE_UUID}")

            assert response.status_code == 404
            assert response.json()["detail"] == "Item not found"

    @pytest.mark.asyncio
    async def test_delete_item_cascades_to_session_items(self, db_session: Session):
        """Test deleting an item also deletes its session items."""
        item = create_item(db_session, "каскад")
        session = create_session(db_session)
        create_session_item(db_session, session.id, item.id)

        async with http_client() as client:
            # Verify session has 1 item before deletion
            response = await client.get(f"/api/sessions/{session.id}")
            assert response.status_code == 200
            assert len(response.json()["items"]) == 1

            # Delete the item
            response = await client.delete(f"/api/items/{item.id}")
            assert response.status_code == 200

            # Verify session now has 0 items (session_item was cascade deleted)
            response = await client.get(f"/api/sessions/{session.id}")
            assert response.status_code == 200
            assert len(response.json()["items"]) == 0


class TestSessionsEndpoints:
    """Tests for /api/sessions endpoints."""

    @pytest.mark.asyncio
    async def test_list_sessions_empty(self):
        """Test GET /api/sessions returns empty list when no sessions exist."""
        async with http_client() as client:
            response = await client.get("/api/sessions")

            assert response.status_code == 200
            data = response.json()
            assert data["sessions"] == []

    @pytest.mark.asyncio
    async def test_list_sessions_with_data(self, db_session: Session):
        """Test GET /api/sessions returns all sessions with item counts."""
        # Create test sessions
        session1 = create_session(db_session, ended=False)
        session2 = create_session(db_session, ended=True)

        # Create items
        item1 = create_item(db_session, "один")
        item2 = create_item(db_session, "два")

        # session1 has 2 items, session2 has 1 item
        create_session_item(db_session, session1.id, item1.id)
        create_session_item(db_session, session1.id, item2.id)
        create_session_item(db_session, session2.id, item1.id)

        async with http_client() as client:
            response = await client.get("/api/sessions")

            assert response.status_code == 200
            data = response.json()
            assert len(data["sessions"]) == 2

            # Find sessions in response
            sessions_by_id = {session["id"]: session for session in data["sessions"]}

            # Verify session1 (active)
            assert sessions_by_id[str(session1.id)]["item_count"] == 2
            assert sessions_by_id[str(session1.id)]["ended_at"] is None

            # Verify session2 (ended)
            assert sessions_by_id[str(session2.id)]["item_count"] == 1
            assert sessions_by_id[str(session2.id)]["ended_at"] is not None

    @pytest.mark.asyncio
    async def test_get_session_detail(self, db_session: Session):
        """Test GET /api/sessions/{id} returns session with items in order."""
        session = create_session(db_session)

        # Create items
        item1 = create_item(db_session, "первый")
        item2 = create_item(db_session, "второй")
        item3 = create_item(db_session, "третий")

        # Create session items with distinct timestamps to ensure ordering
        base_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        create_session_item(db_session, session.id, item1.id, base_time)
        create_session_item(
            db_session, session.id, item2.id, base_time.replace(second=1)
        )
        create_session_item(
            db_session, session.id, item3.id, base_time.replace(second=2)
        )

        async with http_client() as client:
            response = await client.get(f"/api/sessions/{session.id}")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == str(session.id)
            assert data["language"] == DEFAULT_LANGUAGE
            assert data["ended_at"] is None
            assert len(data["items"]) == 3

            # Verify items are in correct order
            assert data["items"][0]["text"] == "первый"
            assert data["items"][1]["text"] == "второй"
            assert data["items"][2]["text"] == "третий"

    @pytest.mark.asyncio
    async def test_get_session_not_found(self):
        """Test GET /api/sessions/{id} returns 404 for non-existent session."""
        async with http_client() as client:
            response = await client.get(f"/api/sessions/{FAKE_UUID}")

            assert response.status_code == 404
            assert response.json()["detail"] == "Session not found"

    @pytest.mark.asyncio
    async def test_delete_session(self, db_session: Session):
        """Test DELETE /api/sessions/{id} deletes session."""
        session = create_session(db_session)

        async with http_client() as client:
            response = await client.delete(f"/api/sessions/{session.id}")

            assert response.status_code == 200
            assert response.json() == {"status": "deleted"}

            # Verify session is deleted
            response = await client.get(f"/api/sessions/{session.id}")
            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_session_not_found(self):
        """Test DELETE /api/sessions/{id} returns 404 for non-existent session."""
        async with http_client() as client:
            response = await client.delete(f"/api/sessions/{FAKE_UUID}")

            assert response.status_code == 404
            assert response.json()["detail"] == "Session not found"

    @pytest.mark.asyncio
    async def test_delete_session_cascades_to_session_items(self, db_session: Session):
        """Test deleting a session also deletes its session items."""
        session = create_session(db_session)
        item = create_item(db_session, "элемент")
        create_session_item(db_session, session.id, item.id)

        async with http_client() as client:
            # Delete the session
            response = await client.delete(f"/api/sessions/{session.id}")
            assert response.status_code == 200

            # Verify item still exists but has no usage
            response = await client.get(f"/api/items/{item.id}")
            assert response.status_code == 200
            assert response.json()["usage_count"] == 0
            assert response.json()["last_used_at"] is None


class TestItemsAutocompleteEndpoint:
    """Tests for /api/items/autocomplete endpoint."""

    @pytest.mark.asyncio
    async def test_autocomplete_basic_match(self, db_session: Session):
        """Test autocomplete returns matching items."""
        # Create items with similar prefixes
        create_item(db_session, "черепаха")
        create_item(db_session, "черепаховый")
        create_item(db_session, "черешня")
        create_item(db_session, "молоко")  # Different prefix

        async with http_client() as client:
            response = await client.get(
                "/api/items/autocomplete", params={"text": "чере", "language": "ru"}
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data["suggestions"]) == 3

            # Should be ordered alphabetically
            texts = [item["text"] for item in data["suggestions"]]
            assert texts == ["черепаха", "черепаховый", "черешня"]

    @pytest.mark.asyncio
    async def test_autocomplete_respects_limit(self, db_session: Session):
        """Test autocomplete respects limit parameter."""
        create_item(db_session, "тест1")  # noqa: RUF001
        create_item(db_session, "тест2")  # noqa: RUF001
        create_item(db_session, "тест3")  # noqa: RUF001
        create_item(db_session, "тест4")  # noqa: RUF001

        async with http_client() as client:
            response = await client.get(
                "/api/items/autocomplete",
                params={"text": "тест", "language": "ru", "limit": 2},
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data["suggestions"]) == 2

    @pytest.mark.asyncio
    async def test_autocomplete_respects_large_limit(self, db_session: Session):
        """Test autocomplete respects large limit values."""
        # Create 15 items
        for i in range(15):
            create_item(db_session, f"тест{i:02d}")

        async with http_client() as client:
            response = await client.get(
                "/api/items/autocomplete",
                params={"text": "тест", "language": "ru", "limit": 20},
            )

            assert response.status_code == 200
            data = response.json()
            # Should return all 15 items since we asked for 20
            assert len(data["suggestions"]) == 15

    @pytest.mark.asyncio
    async def test_autocomplete_filters_by_language(self, db_session: Session):
        """Test autocomplete filters by language."""
        # Create Russian item
        russian_item = Item(text="черепаха", language="ru")
        db_session.add(russian_item)

        # Create German item with same prefix (if it existed)
        german_item = Item(text="черныйхлеб", language="de")
        db_session.add(german_item)

        db_session.commit()

        async with http_client() as client:
            # Query for Russian
            response = await client.get(
                "/api/items/autocomplete", params={"text": "чер", "language": "ru"}
            )
            assert response.status_code == 200
            data = response.json()
            assert len(data["suggestions"]) == 1
            assert data["suggestions"][0]["text"] == "черепаха"

            # Query for German
            response = await client.get(
                "/api/items/autocomplete", params={"text": "чер", "language": "de"}
            )
            assert response.status_code == 200
            data = response.json()
            assert len(data["suggestions"]) == 1
            assert data["suggestions"][0]["text"] == "черныйхлеб"

    @pytest.mark.asyncio
    async def test_autocomplete_case_sensitive(self, db_session: Session):
        """Test autocomplete is case-sensitive."""
        create_item(db_session, "Тест")
        create_item(db_session, "тест")

        async with http_client() as client:
            # Lowercase query should only match lowercase item
            response = await client.get(
                "/api/items/autocomplete", params={"text": "тес", "language": "ru"}
            )
            assert response.status_code == 200
            data = response.json()
            assert len(data["suggestions"]) == 1
            assert data["suggestions"][0]["text"] == "тест"

            # Uppercase query should only match uppercase item
            response = await client.get(
                "/api/items/autocomplete",
                params={"text": "Тес", "language": "ru"},  # noqa: RUF001
            )
            assert response.status_code == 200
            data = response.json()
            assert len(data["suggestions"]) == 1
            assert data["suggestions"][0]["text"] == "Тест"

    @pytest.mark.asyncio
    async def test_autocomplete_no_matches(self, db_session: Session):
        """Test autocomplete returns empty list when no matches."""
        create_item(db_session, "молоко")

        async with http_client() as client:
            response = await client.get(
                "/api/items/autocomplete", params={"text": "хле", "language": "ru"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["suggestions"] == []

    @pytest.mark.asyncio
    async def test_autocomplete_returns_minimal_fields(self, db_session: Session):
        """Test autocomplete only returns id and text, not usage stats."""
        item = create_item(db_session, "проверка")
        session = create_session(db_session)
        create_session_item(db_session, session.id, item.id)

        async with http_client() as client:
            response = await client.get(
                "/api/items/autocomplete", params={"text": "про", "language": "ru"}
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data["suggestions"]) == 1

            # Should only have id and text
            suggestion = data["suggestions"][0]
            assert set(suggestion.keys()) == {"id", "text"}
            assert suggestion["id"] == str(item.id)
            assert suggestion["text"] == "проверка"


class TestLogsEndpoint:
    """Tests for /api/logs endpoint."""

    @pytest.mark.asyncio
    async def test_receive_frontend_log(self):
        """Test POST /api/logs accepts and acknowledges frontend log."""
        async with http_client() as client:
            response = await client.post(
                "/api/logs",
                json={
                    "level": "error",
                    "message": "Test error from frontend",
                    "args": [],
                },
            )

            assert response.status_code == 200
            assert response.json() == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_receive_frontend_log_all_levels(self):
        """Test POST /api/logs accepts all log levels."""
        async with http_client() as client:
            for level in ["log", "info", "warn", "error"]:
                response = await client.post(
                    "/api/logs",
                    json={
                        "level": level,
                        "message": f"Test {level} message",
                        "args": [],
                    },
                )

                assert response.status_code == 200
                assert response.json() == {"status": "ok"}
