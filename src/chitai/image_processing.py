"""Image processing utilities."""

from io import BytesIO
from pathlib import Path  # noqa: TC003
from typing import NamedTuple

import httpx
from PIL import Image


class ImageProcessingError(Exception):
    """Base exception for image processing errors."""


class InvalidImageError(ImageProcessingError):
    """Raised when image format is invalid or unsupported."""


class ImageDownloadError(ImageProcessingError):
    """Raised when image download fails."""


class InsufficientStorageError(ImageProcessingError):
    """Raised when disk space is insufficient."""


class ProcessedImage(NamedTuple):
    """A single processed image variant."""

    data: bytes
    width: int
    height: int


def _resize_image(image: Image.Image, max_dimension: int) -> Image.Image:
    """Resize image maintaining aspect ratio if either dimension exceeds max."""
    width, height = image.size

    if width <= max_dimension and height <= max_dimension:
        return image

    if width > height:
        new_width = max_dimension
        new_height = int(height * (max_dimension / width))
    else:
        new_height = max_dimension
        new_width = int(width * (max_dimension / height))

    return image.resize((new_width, new_height), Image.Resampling.LANCZOS)


def _convert_to_webp(image: Image.Image, quality: int) -> bytes:
    """Convert image to WebP format."""
    output = BytesIO()
    # Convert to RGB if necessary (WebP doesn't support all modes)
    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGB")
    image.save(output, format="WEBP", quality=quality)
    return output.getvalue()


def save_image_file(path: Path, data: bytes) -> None:
    """Save image bytes to path, creating parent directories if needed."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    except OSError as e:
        if e.errno == 28:  # ENOSPC: No space left on device  # noqa: PLR2004
            msg = "Not enough disk space"
            raise InsufficientStorageError(msg) from e
        raise


async def fetch_image_from_url(url: str) -> bytes:
    """Fetch image data from URL. Caller should wrap with asyncio.timeout()."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()
            return response.content
    except httpx.HTTPError as e:
        msg = f"Could not fetch image from URL: {e}"
        raise ImageDownloadError(msg) from e


def process_image(
    image_data: bytes, max_dimension: int, quality: int
) -> ProcessedImage:
    """Process image: resize to max dimension and convert to WebP.

    Parameters
    ----------
    image_data : bytes
        Raw image bytes in any supported format (JPEG, PNG, WebP, etc.)
    max_dimension : int
        Maximum width or height. Image is resized to fit within this dimension
        while maintaining aspect ratio. Images smaller than this are not upscaled.
    quality : int
        WebP quality level (0-100)

    Returns
    -------
    ProcessedImage
        Processed image with WebP data, width, and height.

    Raises
    ------
    InvalidImageError
        If image format is invalid, unsupported, or file is too large to process.
    """
    try:
        image = Image.open(BytesIO(image_data))
    except Exception as e:
        msg = "Invalid or unsupported image format"
        raise InvalidImageError(msg) from e

    # Verify it's a valid image by trying to load it
    try:
        image.load()
    except Exception as e:
        msg = "Image file too large to process"
        raise InvalidImageError(msg) from e

    # Resize and convert
    resized = _resize_image(image, max_dimension)
    width, height = resized.size
    webp_data = _convert_to_webp(resized, quality)

    return ProcessedImage(data=webp_data, width=width, height=height)
