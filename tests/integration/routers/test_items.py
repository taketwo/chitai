"""Integration tests for /api/items endpoints."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from chitai.db.models import Item
from tests.integration.helpers import (
    DEFAULT_LANGUAGE,
    FAKE_UUID,
    create_illustration,
    create_item,
    create_session,
    create_session_item,
    http_client,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


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
    async def test_create_item(self):
        """Test POST /api/items creates a new item."""
        async with http_client() as client:
            response = await client.post(
                "/api/items",
                data={"text": "новый", "language": "ru"},
            )

            assert response.status_code == 201
            data = response.json()
            assert data["text"] == "новый"
            assert data["language"] == "ru"
            assert "id" in data
            assert "created_at" in data

    @pytest.mark.asyncio
    async def test_create_item_different_languages(self):
        """Test creating items with different languages."""
        async with http_client() as client:
            # Create items in all supported languages
            for lang in ["ru", "de", "en"]:
                response = await client.post(
                    "/api/items",
                    data={"text": "test", "language": lang},
                )
                assert response.status_code == 201
                assert response.json()["language"] == lang

            # Verify all three items exist
            response = await client.get("/api/items")
            assert response.status_code == 200
            items = response.json()["items"]
            assert len(items) == 3

    @pytest.mark.asyncio
    async def test_create_item_duplicate(self):
        """Test POST /api/items is idempotent - returns existing item with 200."""
        async with http_client() as client:
            # Create initial item
            response = await client.post(
                "/api/items",
                data={"text": "дубликат", "language": "ru"},
            )
            assert response.status_code == 201
            first_item = response.json()

            # Create duplicate - should return existing item with 200
            response = await client.post(
                "/api/items",
                data={"text": "дубликат", "language": "ru"},
            )
            assert response.status_code == 200
            second_item = response.json()

            # Should be the same item
            assert first_item["id"] == second_item["id"]
            assert second_item["text"] == "дубликат"
            assert second_item["language"] == "ru"

    @pytest.mark.asyncio
    async def test_create_item_empty_text(self):
        """Test POST /api/items returns 422 for empty text."""
        async with http_client() as client:
            response = await client.post(
                "/api/items",
                data={"text": "", "language": "ru"},
            )
            # FastAPI returns 422 for empty required field
            assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_item_whitespace_only(self):
        """Test POST /api/items returns 400 for whitespace-only text."""
        async with http_client() as client:
            response = await client.post(
                "/api/items",
                data={"text": "   ", "language": "ru"},
            )
            assert response.status_code == 400
            assert "cannot be empty" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_item_trims_whitespace(self):
        """Test POST /api/items trims leading/trailing whitespace."""
        async with http_client() as client:
            response = await client.post(
                "/api/items",
                data={"text": "  текст  ", "language": "ru"},
            )
            assert response.status_code == 201
            assert response.json()["text"] == "текст"

    @pytest.mark.asyncio
    async def test_create_item_invalid_language(self):
        """Test POST /api/items returns 422 for invalid language."""
        async with http_client() as client:
            response = await client.post(
                "/api/items",
                data={"text": "test", "language": "invalid"},
            )
            assert response.status_code == 422

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

    @pytest.mark.asyncio
    async def test_list_items_includes_illustration_count(self, db_session: Session):
        """Test GET /api/items returns illustration_count for each item."""
        # Create items
        item_with_illustrations = create_item(db_session, "с картинками")  # noqa: RUF001
        create_item(db_session, "без картинок")

        # Add illustrations to first item
        ill1 = create_illustration(db_session)
        ill2 = create_illustration(db_session)
        link1 = ItemIllustration(
            item_id=item_with_illustrations.id, illustration_id=ill1.id
        )
        link2 = ItemIllustration(
            item_id=item_with_illustrations.id, illustration_id=ill2.id
        )
        db_session.add_all([link1, link2])
        db_session.commit()

        async with http_client() as client:
            response = await client.get("/api/items")

            assert response.status_code == 200
            data = response.json()
            items_by_text = {item["text"]: item for item in data["items"]}

            assert items_by_text["с картинками"]["illustration_count"] == 2  # noqa: RUF001
            assert items_by_text["без картинок"]["illustration_count"] == 0

    @pytest.mark.asyncio
    async def test_get_item_includes_illustration_count(self, db_session: Session):
        """Test GET /api/items/{id} returns illustration_count."""
        item = create_item(db_session, "тестовый")

        # Add illustrations
        ill1 = create_illustration(db_session)
        ill2 = create_illustration(db_session)
        link1 = ItemIllustration(item_id=item.id, illustration_id=ill1.id)
        link2 = ItemIllustration(item_id=item.id, illustration_id=ill2.id)
        db_session.add_all([link1, link2])
        db_session.commit()

        async with http_client() as client:
            response = await client.get(f"/api/items/{item.id}")

            assert response.status_code == 200
            data = response.json()
            assert data["illustration_count"] == 2


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
