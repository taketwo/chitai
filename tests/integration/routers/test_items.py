"""Integration tests for /api/items endpoints."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from chitai.db.models import Item, ItemIllustration, SessionItem
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


class TestItemsSearchEndpoint:
    """Tests for /api/items/search endpoint."""

    @pytest.mark.asyncio
    async def test_search_basic_substring_match(self, db_session: Session):
        """Test search returns items matching substring anywhere in text."""
        create_item(db_session, "картофель")
        create_item(db_session, "молочная каша")
        create_item(db_session, "хлеб")
        create_item(db_session, "каша")

        async with http_client() as client:
            response = await client.get(
                "/api/items/search",
                params={"language": "ru", "q": "ка"},
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) == 3  # картофель, молочная каша, каша
            assert data["has_more"] is False

            texts = [item["text"] for item in data["items"]]
            assert texts == ["картофель", "каша", "молочная каша"]

    @pytest.mark.asyncio
    async def test_search_empty_query_returns_all(self, db_session: Session):
        """Test search with no query string returns all items for language."""
        create_item(db_session, "один")
        create_item(db_session, "два")
        create_item(db_session, "три")

        async with http_client() as client:
            response = await client.get(
                "/api/items/search",
                params={"language": "ru"},
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) == 3
            assert data["has_more"] is False

    @pytest.mark.asyncio
    async def test_search_filters_by_language(self, db_session: Session):
        """Test search only returns items matching the language parameter."""
        # Create items in different languages
        russian_item = Item(text="тест", language="ru")
        german_item = Item(text="test", language="de")
        english_item = Item(text="test", language="en")
        db_session.add_all([russian_item, german_item, english_item])
        db_session.commit()

        async with http_client() as client:
            # Search Russian
            response = await client.get(
                "/api/items/search",
                params={"language": "ru", "q": "тест"},
            )
            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) == 1
            assert data["items"][0]["text"] == "тест"
            assert data["items"][0]["language"] == "ru"

            # Search German
            response = await client.get(
                "/api/items/search",
                params={"language": "de", "q": "test"},
            )
            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) == 1
            assert data["items"][0]["language"] == "de"

    @pytest.mark.asyncio
    async def test_search_sorted_alphabetically(self, db_session: Session):
        """Test search results are sorted alphabetically by text."""
        create_item(db_session, "яблоко")
        create_item(db_session, "банан")
        create_item(db_session, "арбуз")
        create_item(db_session, "груша")

        async with http_client() as client:
            response = await client.get(
                "/api/items/search",
                params={"language": "ru"},
            )

            assert response.status_code == 200
            data = response.json()
            texts = [item["text"] for item in data["items"]]
            assert texts == ["арбуз", "банан", "груша", "яблоко"]

    @pytest.mark.asyncio
    async def test_search_filter_new_items(self, db_session: Session):
        """Test 'new' filter returns only items never used in any session."""
        # Create items
        create_item(db_session, "новый1")  # noqa: RUF001
        create_item(db_session, "новый2")  # noqa: RUF001
        used_item = create_item(db_session, "использованный")

        # Use one item in a session
        session = create_session(db_session)
        create_session_item(db_session, session.id, used_item.id)

        async with http_client() as client:
            response = await client.get(
                "/api/items/search",
                params={"language": "ru", "new": "true"},
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) == 2
            texts = {item["text"] for item in data["items"]}
            assert texts == {"новый1", "новый2"}  # noqa: RUF001

            # Verify is_new flag is set correctly
            for item in data["items"]:
                assert item["is_new"] is True

    @pytest.mark.asyncio
    async def test_search_filter_illustrated_items(self, db_session: Session):
        """Test 'illustrated' filter returns only items with illustrations."""
        # Create items
        item_with_ill1 = create_item(db_session, "картинка1")  # noqa: RUF001
        item_with_ill2 = create_item(db_session, "картинка2")  # noqa: RUF001
        create_item(db_session, "текст")

        # Create illustrations and link them
        ill1 = create_illustration(db_session)
        ill2 = create_illustration(db_session)

        link1 = ItemIllustration(item_id=item_with_ill1.id, illustration_id=ill1.id)
        link2 = ItemIllustration(item_id=item_with_ill2.id, illustration_id=ill2.id)
        db_session.add_all([link1, link2])
        db_session.commit()

        async with http_client() as client:
            response = await client.get(
                "/api/items/search",
                params={"language": "ru", "illustrated": "true"},
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) == 2
            texts = {item["text"] for item in data["items"]}
            assert texts == {"картинка1", "картинка2"}  # noqa: RUF001

            # Verify has_illustrations flag is set correctly
            for item in data["items"]:
                assert item["has_illustrations"] is True

    @pytest.mark.asyncio
    async def test_search_filter_exclude_session(self, db_session: Session):
        """Test exclude_session filter removes items from specified session."""
        # Create items
        item1 = create_item(db_session, "первый")
        item2 = create_item(db_session, "второй")
        create_item(db_session, "третий")

        # Create session and add items to it
        session = create_session(db_session)
        create_session_item(db_session, session.id, item1.id)
        create_session_item(db_session, session.id, item2.id)

        async with http_client() as client:
            response = await client.get(
                "/api/items/search",
                params={"language": "ru", "exclude_session": session.id},
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) == 1
            assert data["items"][0]["text"] == "третий"

    @pytest.mark.asyncio
    async def test_search_exclude_session_includes_queued_items(
        self, db_session: Session
    ):
        """Test exclude_session filter removes queued items (displayed_at=NULL)."""
        # Create items
        displayed_item = create_item(db_session, "показанный")
        queued_item = create_item(db_session, "в очереди")
        create_item(db_session, "не использован")

        # Create session with one displayed and one queued item
        session = create_session(db_session)
        create_session_item(
            db_session, session.id, displayed_item.id
        )  # Has displayed_at

        # Create queued item without displayed_at
        queued_session_item = SessionItem(
            session_id=session.id,
            item_id=queued_item.id,
            displayed_at=None,  # Explicitly NULL for queued items
        )
        db_session.add(queued_session_item)
        db_session.commit()

        async with http_client() as client:
            response = await client.get(
                "/api/items/search",
                params={"language": "ru", "exclude_session": session.id},
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) == 1
            assert data["items"][0]["text"] == "не использован"

    @pytest.mark.asyncio
    async def test_search_combined_filters(self, db_session: Session):
        """Test combining multiple filters with AND logic."""
        # Create various items
        new_illustrated = create_item(db_session, "новая картинка")
        create_item(db_session, "новый текст")
        used_illustrated = create_item(db_session, "старая картинка")
        used_text_only = create_item(db_session, "старый текст")

        # Add illustrations to some items
        ill = create_illustration(db_session)
        link1 = ItemIllustration(item_id=new_illustrated.id, illustration_id=ill.id)
        link2 = ItemIllustration(item_id=used_illustrated.id, illustration_id=ill.id)
        db_session.add_all([link1, link2])
        db_session.commit()

        # Use some items in a session
        session = create_session(db_session)
        create_session_item(db_session, session.id, used_illustrated.id)
        create_session_item(db_session, session.id, used_text_only.id)

        async with http_client() as client:
            # Filter: new AND illustrated AND contains "картинка"
            response = await client.get(
                "/api/items/search",
                params={
                    "language": "ru",
                    "q": "картинка",
                    "new": "true",
                    "illustrated": "true",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) == 1
            assert data["items"][0]["text"] == "новая картинка"
            assert data["items"][0]["is_new"] is True
            assert data["items"][0]["has_illustrations"] is True

    @pytest.mark.asyncio
    async def test_search_has_more_flag_when_truncated(self, db_session: Session):
        """Test has_more flag is True when results exceed limit."""
        # Create 10 items
        for i in range(10):
            create_item(db_session, f"item{i:02d}")

        async with http_client() as client:
            # Request only 5 items when 10 exist
            response = await client.get(
                "/api/items/search",
                params={"language": "ru", "limit": 5},
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) == 5
            assert data["has_more"] is True

    @pytest.mark.asyncio
    async def test_search_has_more_flag_when_not_truncated(self, db_session: Session):
        """Test has_more flag is False when all results fit within limit."""
        # Create 5 items
        for i in range(5):
            create_item(db_session, f"item{i:02d}")

        async with http_client() as client:
            # Request 10 items when only 5 exist
            response = await client.get(
                "/api/items/search",
                params={"language": "ru", "limit": 10},
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) == 5
            assert data["has_more"] is False

    @pytest.mark.asyncio
    async def test_search_has_more_flag_exact_limit(self, db_session: Session):
        """Test has_more flag is False when results exactly match limit."""
        # Create exactly 5 items
        for i in range(5):
            create_item(db_session, f"item{i:02d}")

        async with http_client() as client:
            response = await client.get(
                "/api/items/search",
                params={"language": "ru", "limit": 5},
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) == 5
            assert data["has_more"] is False

    @pytest.mark.asyncio
    async def test_search_no_matches_returns_empty(self, db_session: Session):
        """Test search with no matches returns empty list."""
        create_item(db_session, "молоко")
        create_item(db_session, "хлеб")

        async with http_client() as client:
            response = await client.get(
                "/api/items/search",
                params={"language": "ru", "q": "вода"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["items"] == []
            assert data["has_more"] is False

    @pytest.mark.asyncio
    async def test_search_is_new_flag_correct(self, db_session: Session):
        """Test is_new flag accurately reflects usage status."""
        create_item(db_session, "новый")
        used_item = create_item(db_session, "использованный")

        session = create_session(db_session)
        create_session_item(db_session, session.id, used_item.id)

        async with http_client() as client:
            response = await client.get(
                "/api/items/search",
                params={"language": "ru"},
            )

            assert response.status_code == 200
            data = response.json()
            items_by_text = {item["text"]: item for item in data["items"]}

            assert items_by_text["новый"]["is_new"] is True
            assert items_by_text["использованный"]["is_new"] is False

    @pytest.mark.asyncio
    async def test_search_has_illustrations_flag_correct(self, db_session: Session):
        """Test has_illustrations flag accurately reflects illustration status."""
        illustrated_item = create_item(db_session, "с картинкой")  # noqa: RUF001
        create_item(db_session, "без картинки")

        # Add illustration to one item
        ill = create_illustration(db_session)
        link = ItemIllustration(item_id=illustrated_item.id, illustration_id=ill.id)
        db_session.add(link)
        db_session.commit()

        async with http_client() as client:
            response = await client.get(
                "/api/items/search",
                params={"language": "ru"},
            )

            assert response.status_code == 200
            data = response.json()
            items_by_text = {item["text"]: item for item in data["items"]}

            assert items_by_text["с картинкой"]["has_illustrations"] is True  # noqa: RUF001
            assert items_by_text["без картинки"]["has_illustrations"] is False

    @pytest.mark.asyncio
    async def test_search_flags_correct_with_both_session_items_and_illustrations(
        self, db_session: Session
    ):
        """Test is_new and has_illustrations flags are correct when an item has both
        session items and illustrations.

        Guards against Cartesian product inflation from joining both tables."""
        item = create_item(db_session, "комбо")

        # Link 2 illustrations
        ill1 = create_illustration(db_session)
        ill2 = create_illustration(db_session)
        db_session.add_all(
            [
                ItemIllustration(item_id=item.id, illustration_id=ill1.id),
                ItemIllustration(item_id=item.id, illustration_id=ill2.id),
            ]
        )

        # Use in 1 session
        session = create_session(db_session)
        create_session_item(db_session, session.id, item.id)
        db_session.commit()

        async with http_client() as client:
            response = await client.get(
                "/api/items/search",
                params={"language": "ru"},
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) == 1
            result = data["items"][0]
            assert result["is_new"] is False
            assert result["has_illustrations"] is True

    @pytest.mark.asyncio
    async def test_search_case_sensitive(self, db_session: Session):
        """Test search is case-sensitive."""
        create_item(db_session, "Тест")
        create_item(db_session, "тест")

        async with http_client() as client:
            # Lowercase query
            response = await client.get(
                "/api/items/search",
                params={"language": "ru", "q": "тес"},
            )
            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) == 1
            assert data["items"][0]["text"] == "тест"

            # Uppercase query
            response = await client.get(
                "/api/items/search",
                params={"language": "ru", "q": "Тес"},  # noqa: RUF001
            )
            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) == 1
            assert data["items"][0]["text"] == "Тест"

    @pytest.mark.asyncio
    async def test_search_response_fields(self, db_session: Session):
        """Test search response contains all expected fields."""
        item = create_item(db_session, "проверка полей")

        async with http_client() as client:
            response = await client.get(
                "/api/items/search",
                params={"language": "ru"},
            )

            assert response.status_code == 200
            data = response.json()
            assert "items" in data
            assert "has_more" in data

            assert len(data["items"]) == 1
            result_item = data["items"][0]
            assert set(result_item.keys()) == {
                "id",
                "text",
                "language",
                "is_new",
                "has_illustrations",
            }
            assert result_item["id"] == str(item.id)
            assert result_item["text"] == "проверка полей"
            assert result_item["language"] == "ru"
            assert isinstance(result_item["is_new"], bool)
            assert isinstance(result_item["has_illustrations"], bool)
