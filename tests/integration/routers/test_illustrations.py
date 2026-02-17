"""Integration tests for /api/illustrations endpoints."""

from io import BytesIO
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from PIL import Image

from chitai.db.models import ItemIllustration
from chitai.image_processing import ImageDownloadError, InsufficientStorageError
from tests.integration.helpers import (
    FAKE_UUID,
    create_illustration,
    create_item,
    create_test_image,
    http_client,
)

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.orm import Session


class TestIllustrationsEndpoints:
    """Tests for /api/illustrations endpoints."""

    @pytest.mark.asyncio
    async def test_list_illustrations_empty(self):
        """Test GET /api/illustrations returns empty list."""
        async with http_client() as client:
            response = await client.get("/api/illustrations")

            assert response.status_code == 200
            data = response.json()
            assert data["illustrations"] == []
            assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_illustrations_with_data(self, db_session: Session):
        """Test GET /api/illustrations returns all illustrations with item counts."""
        illustration1 = create_illustration(
            db_session, source_url="https://example.com/img1.jpg"
        )
        illustration2 = create_illustration(db_session, width=1024, height=768)

        # Link illustration1 to two items
        item1 = create_item(db_session, "собака")
        item2 = create_item(db_session, "кошка")
        db_session.add(
            ItemIllustration(item_id=item1.id, illustration_id=illustration1.id)
        )
        db_session.add(
            ItemIllustration(item_id=item2.id, illustration_id=illustration1.id)
        )
        db_session.commit()

        async with http_client() as client:
            response = await client.get("/api/illustrations")

            assert response.status_code == 200
            data = response.json()
            assert len(data["illustrations"]) == 2
            assert data["total"] == 2

            # Find illustrations in response (ordered by created_at desc)
            illustrations_by_id = {ill["id"]: ill for ill in data["illustrations"]}

            # Verify illustration1 has 2 items linked
            assert illustrations_by_id[str(illustration1.id)]["item_count"] == 2
            assert (
                illustrations_by_id[str(illustration1.id)]["source_url"]
                == "https://example.com/img1.jpg"
            )

            # Verify illustration2 has 0 items linked
            assert illustrations_by_id[str(illustration2.id)]["item_count"] == 0
            assert illustrations_by_id[str(illustration2.id)]["source_url"] is None

    @pytest.mark.asyncio
    async def test_list_illustrations_pagination(self, db_session: Session):
        """Test GET /api/illustrations respects pagination parameters."""
        for _ in range(5):
            create_illustration(db_session)

        async with http_client() as client:
            # Get first 2
            response = await client.get("/api/illustrations?offset=0&limit=2")
            assert response.status_code == 200
            data = response.json()
            assert len(data["illustrations"]) == 2
            assert data["total"] == 5

            # Get next 2
            response = await client.get("/api/illustrations?offset=2&limit=2")
            assert response.status_code == 200
            data = response.json()
            assert len(data["illustrations"]) == 2
            assert data["total"] == 5

    @pytest.mark.asyncio
    async def test_get_illustration_by_id(self, db_session: Session):
        """Test GET /api/illustrations/{id} returns single illustration."""
        illustration = create_illustration(
            db_session, source_url="https://example.com/test.jpg", width=1200
        )

        async with http_client() as client:
            response = await client.get(f"/api/illustrations/{illustration.id}")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == str(illustration.id)
            assert data["source_url"] == "https://example.com/test.jpg"
            assert data["width"] == 1200
            assert data["item_count"] == 0

    @pytest.mark.asyncio
    async def test_get_illustration_not_found(self):
        """Test GET /api/illustrations/{id} returns 404 when not found."""
        async with http_client() as client:
            response = await client.get(f"/api/illustrations/{FAKE_UUID}")

            assert response.status_code == 404
            assert response.json()["detail"] == "Illustration not found"

    @pytest.mark.asyncio
    async def test_delete_illustration(self, db_session: Session):
        """Test DELETE /api/illustrations/{id} deletes illustration."""
        illustration = create_illustration(db_session)

        async with http_client() as client:
            response = await client.delete(f"/api/illustrations/{illustration.id}")

            assert response.status_code == 200
            assert response.json() == {"status": "deleted"}

            # Verify illustration is deleted
            response = await client.get(f"/api/illustrations/{illustration.id}")
            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_illustration_not_found(self):
        """Test DELETE /api/illustrations/{id} returns 404 when not found."""
        async with http_client() as client:
            response = await client.delete(f"/api/illustrations/{FAKE_UUID}")

            assert response.status_code == 404
            assert response.json()["detail"] == "Illustration not found"

    @pytest.mark.asyncio
    async def test_delete_illustration_cascades_to_item_illustrations(
        self, db_session: Session
    ):
        """Test deleting an illustration also deletes its item links."""
        illustration = create_illustration(db_session)
        item = create_item(db_session, "собака")

        # Link illustration to item
        db_session.add(
            ItemIllustration(item_id=item.id, illustration_id=illustration.id)
        )
        db_session.commit()

        async with http_client() as client:
            # Verify item has 1 illustration
            response = await client.get(f"/api/items/{item.id}/illustrations")
            assert response.status_code == 200
            assert len(response.json()) == 1

            # Delete illustration
            response = await client.delete(f"/api/illustrations/{illustration.id}")
            assert response.status_code == 200

            # Verify item now has 0 illustrations
            response = await client.get(f"/api/items/{item.id}/illustrations")
            assert response.status_code == 200
            assert len(response.json()) == 0

            # Verify item still exists
            response = await client.get(f"/api/items/{item.id}")
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_import_illustration_from_url(self, temp_illustration_dir: Path):
        """Test POST /api/illustrations with URL parameter."""
        test_image = create_test_image(800, 600, "PNG")

        async def mock_fetch(_url: str) -> bytes:
            return test_image

        with patch(
            "chitai.server.routers.illustrations.fetch_image_from_url",
            side_effect=mock_fetch,
        ):
            async with http_client() as client:
                response = await client.post(
                    "/api/illustrations",
                    data={"url": "https://example.com/image.jpg"},
                )

                assert response.status_code == 201
                data = response.json()
                assert data["source_url"] == "https://example.com/image.jpg"
                assert data["width"] == 800
                assert data["height"] == 600
                assert data["item_count"] == 0
                assert "id" in data
                assert "created_at" in data

                # Verify files were created
                illustration_id = data["id"]
                full_image_path = temp_illustration_dir / f"{illustration_id}.webp"
                thumbnail_path = temp_illustration_dir / f"{illustration_id}_thumb.webp"
                assert full_image_path.exists()
                assert thumbnail_path.exists()
                assert full_image_path.stat().st_size > 0
                assert thumbnail_path.stat().st_size > 0

    @pytest.mark.asyncio
    async def test_import_illustration_from_file(self, temp_illustration_dir: Path):
        """Test POST /api/illustrations with file upload."""
        test_image = create_test_image(1024, 768, "JPEG")

        async with http_client() as client:
            response = await client.post(
                "/api/illustrations",
                files={"file": ("test.jpg", BytesIO(test_image), "image/jpeg")},
            )

            assert response.status_code == 201
            data = response.json()
            assert data["source_url"] is None
            assert data["width"] == 1024
            assert data["height"] == 768
            assert data["item_count"] == 0

            # Verify files were created
            illustration_id = data["id"]
            full_image_path = temp_illustration_dir / f"{illustration_id}.webp"
            thumbnail_path = temp_illustration_dir / f"{illustration_id}_thumb.webp"
            assert full_image_path.exists()
            assert thumbnail_path.exists()
            assert full_image_path.stat().st_size > 0
            assert thumbnail_path.stat().st_size > 0

    @pytest.mark.asyncio
    async def test_import_illustration_both_params_error(self):
        """Test POST /api/illustrations rejects both url and file."""
        test_image = create_test_image(800, 600)

        async with http_client() as client:
            response = await client.post(
                "/api/illustrations",
                data={"url": "https://example.com/image.jpg"},
                files={"file": ("test.jpg", BytesIO(test_image), "image/jpeg")},
            )

            assert response.status_code == 400
            assert "Cannot provide both" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_import_illustration_neither_param_error(self):
        """Test POST /api/illustrations rejects neither url nor file."""
        async with http_client() as client:
            response = await client.post("/api/illustrations")

            assert response.status_code == 400
            assert "Must provide either" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_import_illustration_invalid_file_type(self):
        """Test POST /api/illustrations rejects non-image files."""
        async with http_client() as client:
            response = await client.post(
                "/api/illustrations",
                files={"file": ("test.txt", BytesIO(b"not an image"), "text/plain")},
            )

            assert response.status_code == 400
            assert "Invalid content type" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_import_illustration_invalid_image_data(self):
        """Test POST /api/illustrations handles invalid image data."""

        async def mock_fetch(_url: str) -> bytes:
            return b"not a valid image"

        with patch(
            "chitai.server.routers.illustrations.fetch_image_from_url",
            side_effect=mock_fetch,
        ):
            async with http_client() as client:
                response = await client.post(
                    "/api/illustrations",
                    data={"url": "https://example.com/invalid.jpg"},
                )

                assert response.status_code == 400
                assert "detail" in response.json()

    @pytest.mark.asyncio
    async def test_import_illustration_download_error(self):
        """Test POST /api/illustrations handles download errors."""

        async def mock_fetch(_url: str) -> bytes:
            msg = "Failed to download image"
            raise ImageDownloadError(msg)

        with patch(
            "chitai.server.routers.illustrations.fetch_image_from_url",
            side_effect=mock_fetch,
        ):
            async with http_client() as client:
                response = await client.post(
                    "/api/illustrations",
                    data={"url": "https://example.com/error.jpg"},
                )

                assert response.status_code == 400
                assert "Failed to download" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_import_illustration_timeout(self):
        """Test POST /api/illustrations handles timeout."""

        async def timeout_fetch(_url: str) -> bytes:
            msg = "Request timed out"
            raise TimeoutError(msg)

        with patch(
            "chitai.server.routers.illustrations.fetch_image_from_url",
            side_effect=timeout_fetch,
        ):
            async with http_client() as client:
                response = await client.post(
                    "/api/illustrations",
                    data={"url": "https://example.com/slow.jpg"},
                )

                assert response.status_code == 400
                assert "timed out" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_import_illustration_insufficient_storage(self):
        """Test POST /api/illustrations returns 507 when disk is full.

        Also verifies that partially written image files are cleaned up."""
        storage_msg = "Not enough disk space"

        async def mock_fetch(_url: str) -> bytes:
            return create_test_image(100, 100, "PNG")

        with (
            patch(
                "chitai.server.routers.illustrations.fetch_image_from_url",
                side_effect=mock_fetch,
            ),
            patch(
                "chitai.server.routers.illustrations.save_image_file",
                side_effect=InsufficientStorageError(storage_msg),
            ),
        ):
            async with http_client() as client:
                response = await client.post(
                    "/api/illustrations",
                    data={"url": "https://example.com/img.jpg"},
                )

                assert response.status_code == 507
                assert "disk space" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_import_illustration_resizes_large_images(
        self,
        temp_illustration_dir: Path,
    ):
        """Test import resizes large images to max dimension."""
        test_image = create_test_image(2400, 1800, "PNG")

        async def mock_fetch(_url: str) -> bytes:
            return test_image

        with patch(
            "chitai.server.routers.illustrations.fetch_image_from_url",
            side_effect=mock_fetch,
        ):
            async with http_client() as client:
                response = await client.post(
                    "/api/illustrations",
                    data={"url": "https://example.com/large.jpg"},
                )

                assert response.status_code == 201
                data = response.json()
                # Default max dimension is 1200
                assert data["width"] == 1200
                assert data["height"] == 900

                # Verify files were created and are smaller than original
                illustration_id = data["id"]
                full_image_path = temp_illustration_dir / f"{illustration_id}.webp"
                thumbnail_path = temp_illustration_dir / f"{illustration_id}_thumb.webp"
                assert full_image_path.exists()
                assert thumbnail_path.exists()

                # Verify actual image dimensions from file

                with Image.open(full_image_path) as img:
                    assert img.size == (1200, 900)
                with Image.open(thumbnail_path) as img:
                    # Thumbnail should be even smaller (max 200px)
                    assert max(img.size) == 200

    @pytest.mark.asyncio
    async def test_get_illustration_image(
        self, db_session: Session, temp_illustration_dir: Path
    ):
        """Test GET /api/illustrations/{id}/image serves image file."""
        illustration = create_illustration(db_session)
        illustration_id = str(illustration.id)

        # Create a test image file
        test_image = create_test_image(800, 600)
        illustration_path = temp_illustration_dir / f"{illustration_id}.webp"
        illustration_path.write_bytes(test_image)

        async with http_client() as client:
            response = await client.get(f"/api/illustrations/{illustration_id}/image")

            assert response.status_code == 200
            assert response.headers["content-type"] == "image/webp"
            assert "Cache-Control" in response.headers
            assert "max-age=31536000" in response.headers["Cache-Control"]
            assert len(response.content) > 0

    @pytest.mark.asyncio
    async def test_get_illustration_thumbnail(
        self, db_session: Session, temp_illustration_dir: Path
    ):
        """Test GET /api/illustrations/{id}/thumbnail serves thumbnail file."""
        illustration = create_illustration(db_session)
        illustration_id = str(illustration.id)

        # Create a test thumbnail file
        test_image = create_test_image(200, 150)
        thumbnail_path = temp_illustration_dir / f"{illustration_id}_thumb.webp"
        thumbnail_path.write_bytes(test_image)

        async with http_client() as client:
            response = await client.get(
                f"/api/illustrations/{illustration_id}/thumbnail"
            )

            assert response.status_code == 200
            assert response.headers["content-type"] == "image/webp"
            assert "Cache-Control" in response.headers
            assert len(response.content) > 0

    @pytest.mark.asyncio
    async def test_get_illustration_image_not_found(self):
        """Test GET /api/illustrations/{id}/image returns 404."""
        async with http_client() as client:
            response = await client.get(f"/api/illustrations/{FAKE_UUID}/image")

            assert response.status_code == 404
            assert response.json()["detail"] == "Illustration not found"

    @pytest.mark.asyncio
    async def test_get_illustration_image_file_missing(self, db_session: Session):
        """Test GET /api/illustrations/{id}/image returns 404 when file is missing."""
        illustration = create_illustration(db_session)

        async with http_client() as client:
            response = await client.get(f"/api/illustrations/{illustration.id}/image")

            assert response.status_code == 404
            assert "file not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_illustration_thumbnail_file_missing(self, db_session: Session):
        """Test GET /api/illustrations/{id}/thumbnail returns 404."""
        illustration = create_illustration(db_session)

        async with http_client() as client:
            response = await client.get(
                f"/api/illustrations/{illustration.id}/thumbnail"
            )

            assert response.status_code == 404
            assert "Thumbnail file not found" in response.json()["detail"]


class TestItemIllustrationLinking:
    """Tests for /api/items/{id}/illustrations endpoints."""

    @pytest.mark.asyncio
    async def test_list_item_illustrations_empty(self, db_session: Session):
        """Test GET /api/items/{id}/illustrations returns empty list."""
        item = create_item(db_session, "собака")

        async with http_client() as client:
            response = await client.get(f"/api/items/{item.id}/illustrations")

            assert response.status_code == 200
            assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_item_illustrations_not_found(self):
        """Test GET /api/items/{id}/illustrations returns 404 for non-existent item."""
        async with http_client() as client:
            response = await client.get(f"/api/items/{FAKE_UUID}/illustrations")

            assert response.status_code == 404
            assert response.json()["detail"] == "Item not found"

    @pytest.mark.asyncio
    async def test_link_illustration_to_item(self, db_session: Session):
        """Test POST /api/items/{id}/illustrations/{illustration_id} links."""
        item = create_item(db_session, "собака")
        illustration = create_illustration(db_session)

        async with http_client() as client:
            response = await client.post(
                f"/api/items/{item.id}/illustrations/{illustration.id}"
            )

            assert response.status_code == 201
            assert response.json() == {"status": "linked"}

            # Verify link was created
            response = await client.get(f"/api/items/{item.id}/illustrations")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["id"] == str(illustration.id)

    @pytest.mark.asyncio
    async def test_link_illustration_duplicate_returns_409(self, db_session: Session):
        """Test linking same illustration twice returns 409 conflict."""
        item = create_item(db_session, "собака")
        illustration = create_illustration(db_session)

        # Create link
        db_session.add(
            ItemIllustration(item_id=item.id, illustration_id=illustration.id)
        )
        db_session.commit()

        async with http_client() as client:
            # Try to create duplicate link
            response = await client.post(
                f"/api/items/{item.id}/illustrations/{illustration.id}"
            )

            assert response.status_code == 409
            assert response.json()["detail"] == "Link already exists"

    @pytest.mark.asyncio
    async def test_link_illustration_item_not_found(self, db_session: Session):
        """Test linking to non-existent item returns 404."""
        illustration = create_illustration(db_session)

        async with http_client() as client:
            response = await client.post(
                f"/api/items/{FAKE_UUID}/illustrations/{illustration.id}"
            )

            assert response.status_code == 404
            assert response.json()["detail"] == "Item not found"

    @pytest.mark.asyncio
    async def test_link_illustration_illustration_not_found(self, db_session: Session):
        """Test linking non-existent illustration returns 404."""
        item = create_item(db_session, "собака")

        async with http_client() as client:
            response = await client.post(
                f"/api/items/{item.id}/illustrations/{FAKE_UUID}"
            )

            assert response.status_code == 404
            assert response.json()["detail"] == "Illustration not found"

    @pytest.mark.asyncio
    async def test_unlink_illustration_from_item(self, db_session: Session):
        """Test DELETE /api/items/{id}/illustrations/{illustration_id} unlinks."""
        item = create_item(db_session, "собака")
        illustration = create_illustration(db_session)

        # Create link
        db_session.add(
            ItemIllustration(item_id=item.id, illustration_id=illustration.id)
        )
        db_session.commit()

        async with http_client() as client:
            response = await client.delete(
                f"/api/items/{item.id}/illustrations/{illustration.id}"
            )

            assert response.status_code == 200
            assert response.json() == {"status": "unlinked"}

            # Verify link was removed
            response = await client.get(f"/api/items/{item.id}/illustrations")
            assert response.status_code == 200
            assert response.json() == []

    @pytest.mark.asyncio
    async def test_unlink_illustration_link_not_found(self, db_session: Session):
        """Test unlinking non-existent link returns 404."""
        item = create_item(db_session, "собака")
        illustration = create_illustration(db_session)

        async with http_client() as client:
            response = await client.delete(
                f"/api/items/{item.id}/illustrations/{illustration.id}"
            )

            assert response.status_code == 404
            assert response.json()["detail"] == "Link not found"

    @pytest.mark.asyncio
    async def test_list_multiple_illustrations_for_item(self, db_session: Session):
        """Test listing multiple illustrations linked to an item."""
        item = create_item(db_session, "собака")
        illustration1 = create_illustration(db_session, width=800)
        illustration2 = create_illustration(db_session, width=1024)

        # Link both illustrations
        db_session.add(
            ItemIllustration(item_id=item.id, illustration_id=illustration1.id)
        )
        db_session.add(
            ItemIllustration(item_id=item.id, illustration_id=illustration2.id)
        )
        db_session.commit()

        async with http_client() as client:
            response = await client.get(f"/api/items/{item.id}/illustrations")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            widths = {ill["width"] for ill in data}
            assert widths == {800, 1024}
