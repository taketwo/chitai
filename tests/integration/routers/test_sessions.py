"""Integration tests for /api/sessions endpoints."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from tests.integration.helpers import (
    DEFAULT_LANGUAGE,
    FAKE_UUID,
    create_item,
    create_session,
    create_session_item,
    http_client,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


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

    @pytest.mark.asyncio
    async def test_delete_session_item(self, db_session: Session):
        """Test DELETE /api/sessions/{id}/items/{item_id} deletes session item."""
        session = create_session(db_session)
        item1 = create_item(db_session, "первый")
        item2 = create_item(db_session, "второй")

        session_item1 = create_session_item(db_session, session.id, item1.id)
        create_session_item(db_session, session.id, item2.id)

        async with http_client() as client:
            # Delete first session item
            response = await client.delete(
                f"/api/sessions/{session.id}/items/{session_item1.id}"
            )

            assert response.status_code == 200
            assert response.json() == {"status": "deleted"}

            # Verify session still has second item
            response = await client.get(f"/api/sessions/{session.id}")
            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) == 1
            assert data["items"][0]["text"] == "второй"

    @pytest.mark.asyncio
    async def test_delete_session_item_session_not_found(self, db_session: Session):
        """Test DELETE returns 404 when session doesn't exist."""
        item = create_item(db_session, "элемент")
        session = create_session(db_session)
        session_item = create_session_item(db_session, session.id, item.id)

        async with http_client() as client:
            response = await client.delete(
                f"/api/sessions/{FAKE_UUID}/items/{session_item.id}"
            )

            assert response.status_code == 404
            assert response.json()["detail"] == "Session not found"

    @pytest.mark.asyncio
    async def test_delete_session_item_not_found(self, db_session: Session):
        """Test DELETE returns 404 when session item doesn't exist."""
        session = create_session(db_session)

        async with http_client() as client:
            response = await client.delete(
                f"/api/sessions/{session.id}/items/{FAKE_UUID}"
            )

            assert response.status_code == 404
            assert response.json()["detail"] == "Session item not found"

    @pytest.mark.asyncio
    async def test_delete_session_item_wrong_session(self, db_session: Session):
        """Test DELETE returns 404 when session item belongs to different session."""
        session1 = create_session(db_session)
        session2 = create_session(db_session)
        item = create_item(db_session, "элемент")

        # Create session item for session2
        session_item = create_session_item(db_session, session2.id, item.id)

        async with http_client() as client:
            # Try to delete it via session1
            response = await client.delete(
                f"/api/sessions/{session1.id}/items/{session_item.id}"
            )

            assert response.status_code == 404
            assert (
                response.json()["detail"]
                == "Session item does not belong to this session"
            )
