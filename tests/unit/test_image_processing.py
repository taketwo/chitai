"""Unit tests for image processing service."""

import asyncio
from io import BytesIO
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
from PIL import Image

from chitai.image_processing import (
    ImageDownloadError,
    InsufficientStorageError,
    InvalidImageError,
    fetch_image_from_url,
    process_image,
    save_image_file,
)

# Test constants
MAX_DIMENSION = 1200
THUMBNAIL_SIZE = 200
QUALITY = 85


def create_test_image(width: int, height: int, image_format: str = "PNG") -> bytes:
    """Create a test image in memory."""
    image = Image.new("RGB", (width, height), color="red")
    output = BytesIO()
    image.save(output, format=image_format)
    return output.getvalue()


class TestProcessImage:
    """Tests for process_image function."""

    def test_process_valid_image(self):
        """Process a valid image and verify output."""
        image_data = create_test_image(800, 600)

        result = process_image(image_data, MAX_DIMENSION, QUALITY)

        assert isinstance(result.data, bytes)
        assert result.width == 800
        assert result.height == 600
        assert len(result.data) > 0

        # Verify output is WebP
        image = Image.open(BytesIO(result.data))
        assert image.format == "WEBP"

    def test_resize_large_image(self):
        """Large image should be resized to max dimension."""
        image_data = create_test_image(2000, 1500)

        result = process_image(image_data, MAX_DIMENSION, QUALITY)

        assert result.width == MAX_DIMENSION
        assert result.height == 900

        # Verify actual image dimensions
        image = Image.open(BytesIO(result.data))
        assert image.size == (MAX_DIMENSION, 900)

    def test_thumbnail_generation(self):
        """Should generate smaller size."""
        image_data = create_test_image(800, 600)

        result = process_image(image_data, THUMBNAIL_SIZE, QUALITY)

        image = Image.open(BytesIO(result.data))
        assert max(image.size) == THUMBNAIL_SIZE
        # Aspect ratio should be preserved
        assert image.size == (THUMBNAIL_SIZE, 150)

    @pytest.mark.parametrize(
        ("width", "height", "expected_width", "expected_height"),
        [
            (800, 1600, 600, 1200),  # Portrait: height hits limit
            (1600, 800, 1200, 600),  # Landscape: width hits limit
        ],
    )
    def test_aspect_ratio_preserved(
        self, width, height, expected_width, expected_height
    ):
        """Aspect ratio should be maintained when resizing."""
        image_data = create_test_image(width, height)
        result = process_image(image_data, MAX_DIMENSION, QUALITY)
        assert result.width == expected_width
        assert result.height == expected_height

    def test_small_image_not_upscaled(self):
        """Small images should not be upscaled."""
        image_data = create_test_image(400, 300)

        result = process_image(image_data, MAX_DIMENSION, QUALITY)

        assert result.width == 400
        assert result.height == 300

    def test_invalid_image_data(self):
        """Invalid image data should raise InvalidImageError."""
        with pytest.raises(InvalidImageError, match="Invalid or unsupported"):
            process_image(b"not an image", MAX_DIMENSION, QUALITY)

    def test_corrupted_image(self):
        """Corrupted image should raise InvalidImageError."""
        image_data = create_test_image(100, 100)[:100]

        with pytest.raises(InvalidImageError):
            process_image(image_data, MAX_DIMENSION, QUALITY)

    @pytest.mark.parametrize("img_format", ["PNG", "JPEG", "BMP"])
    def test_different_image_formats(self, img_format):
        """Should handle different input formats."""
        image_data = create_test_image(400, 300, image_format=img_format)
        result = process_image(image_data, MAX_DIMENSION, QUALITY)
        assert result.width == 400
        assert result.height == 300

        # Output should always be WebP
        image = Image.open(BytesIO(result.data))
        assert image.format == "WEBP"


class TestSaveImageFile:
    """Tests for save_image_file function."""

    def test_save_creates_directory(self, tmp_path):
        """Should create parent directory if it doesn't exist."""
        file_path = tmp_path / "new_dir" / "test.webp"

        save_image_file(file_path, b"test data")

        assert file_path.exists()
        assert file_path.read_bytes() == b"test data"

    def test_save_to_existing_directory(self, tmp_path):
        """Should save file to existing directory."""
        file_path = tmp_path / "test.webp"

        save_image_file(file_path, b"image data")

        assert file_path.exists()
        assert file_path.read_bytes() == b"image data"

    def test_save_insufficient_space(self, tmp_path):
        """Should raise InsufficientStorageError on disk full."""
        file_path = tmp_path / "test.webp"

        with patch("pathlib.Path.write_bytes") as mock_write:
            mock_write.side_effect = OSError(28, "No space left on device")

            with pytest.raises(InsufficientStorageError, match="Not enough disk space"):
                save_image_file(file_path, b"data")


class TestFetchImageFromUrl:
    """Tests for fetch_image_from_url function."""

    @pytest.fixture
    def mock_httpx_client(self):
        """Create a mock httpx AsyncClient."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            yield mock_client

    @pytest.mark.asyncio
    async def test_fetch_successful(self, mock_httpx_client):
        """Should fetch image data from valid URL."""
        test_data = b"image data"
        mock_response = Mock()
        mock_response.content = test_data
        mock_response.raise_for_status = Mock()

        mock_httpx_client.get = AsyncMock(return_value=mock_response)

        result = await fetch_image_from_url("http://example.com/image.jpg")

        assert result == test_data
        mock_response.raise_for_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_timeout(self, mock_httpx_client):
        """Timeout should be handled by caller with asyncio.timeout()."""

        async def slow_get(*_args, **_kwargs):
            await asyncio.sleep(10)
            return Mock()

        mock_httpx_client.get = slow_get

        with pytest.raises(TimeoutError):
            async with asyncio.timeout(0.1):
                await fetch_image_from_url("http://example.com/image.jpg")

    @pytest.mark.asyncio
    async def test_fetch_http_error(self, mock_httpx_client):
        """Should raise ImageDownloadError on HTTP error."""

        async def mock_get_error(*_args, **_kwargs):
            msg = "404"
            raise httpx.HTTPStatusError(msg, request=Mock(), response=Mock())

        mock_httpx_client.get = mock_get_error

        with pytest.raises(ImageDownloadError, match="Could not fetch"):
            await fetch_image_from_url("http://example.com/image.jpg")
