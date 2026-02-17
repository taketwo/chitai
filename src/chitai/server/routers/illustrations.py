"""REST API endpoints for illustrations."""

import asyncio
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session  # noqa: TC002

from chitai.db.engine import get_session
from chitai.db.models import Illustration, ItemIllustration
from chitai.image_processing import (
    ImageDownloadError,
    InsufficientStorageError,
    InvalidImageError,
    fetch_image_from_url,
    process_image,
    save_image_file,
)
from chitai.server.routers.schemas import (
    IllustrationListEntry,
    IllustrationListResponse,
)
from chitai.settings import settings

router = APIRouter(prefix="/api/illustrations", tags=["illustrations"])


def _get_illustration_path(illustration_id: str, *, thumbnail: bool = False) -> Path:
    """Get file path for illustration or thumbnail."""
    suffix = "_thumb" if thumbnail else ""
    filename = f"{illustration_id}{suffix}.webp"
    return Path(settings.illustration_dir) / filename


def _serve_illustration_file(
    illustration_id: str, db: Session, *, thumbnail: bool = False
) -> FileResponse:
    """Serve illustration or thumbnail file with proper caching headers."""
    illustration = db.get(Illustration, illustration_id)

    if not illustration:
        raise HTTPException(status_code=404, detail="Illustration not found")

    file_path = _get_illustration_path(illustration_id, thumbnail=thumbnail)

    if not file_path.exists():
        file_type = "Thumbnail" if thumbnail else "Illustration"
        raise HTTPException(status_code=404, detail=f"{file_type} file not found")

    return FileResponse(
        file_path,
        media_type="image/webp",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@router.post("", response_model=IllustrationListEntry, status_code=201)
async def import_illustration(
    url: Annotated[str | None, Form()] = None,
    file: Annotated[UploadFile | None, File()] = None,
    *,
    db: Annotated[Session, Depends(get_session)],
) -> IllustrationListEntry:
    """Import illustration from URL or file upload (mutually exclusive)."""
    if url and file:
        raise HTTPException(
            status_code=400, detail="Cannot provide both url and file parameters"
        )

    illustration_id = None

    try:
        if url:
            async with asyncio.timeout(30):
                image_data = await fetch_image_from_url(url)
            source_url = url
        elif file:
            if file.content_type and not file.content_type.startswith("image/"):
                detail = (
                    f"Invalid content type: {file.content_type}. "
                    "Expected an image file."
                )
                raise HTTPException(status_code=400, detail=detail)

            image_data = file.file.read()
            source_url = None
        else:
            raise HTTPException(
                status_code=400, detail="Must provide either url or file parameter"
            )

        full_image = process_image(
            image_data,
            settings.illustration_max_dimension,
            settings.illustration_webp_quality,
        )
        thumbnail = process_image(
            image_data,
            settings.illustration_thumbnail_max_dimension,
            settings.illustration_webp_quality,
        )

        illustration_id = str(uuid4())
        full_image_path = _get_illustration_path(illustration_id, thumbnail=False)
        thumbnail_path = _get_illustration_path(illustration_id, thumbnail=True)

        try:
            save_image_file(full_image_path, full_image.data)
            save_image_file(thumbnail_path, thumbnail.data)
            illustration = Illustration(
                id=illustration_id,
                source_url=source_url,
                width=full_image.width,
                height=full_image.height,
                file_size_bytes=len(full_image.data),
            )
            db.add(illustration)
            db.commit()
            db.refresh(illustration)
        except Exception:
            full_image_path.unlink(missing_ok=True)
            thumbnail_path.unlink(missing_ok=True)
            raise

        return IllustrationListEntry(
            id=illustration.id,
            source_url=illustration.source_url,
            width=illustration.width,
            height=illustration.height,
            file_size_bytes=illustration.file_size_bytes,
            created_at=illustration.created_at,
            item_count=0,  # Newly created, no items yet
        )

    except InvalidImageError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ImageDownloadError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except TimeoutError as e:
        raise HTTPException(status_code=400, detail="Image download timed out") from e
    except InsufficientStorageError as e:
        raise HTTPException(status_code=507, detail=str(e)) from e


@router.get("", response_model=IllustrationListResponse)
async def list_illustrations(
    offset: int = 0,
    limit: int = 50,
    *,
    db: Annotated[Session, Depends(get_session)],
) -> IllustrationListResponse:
    """List all illustrations with pagination and item counts."""
    query = (
        select(
            Illustration,
            func.count(ItemIllustration.id).label("item_count"),
        )
        .outerjoin(
            ItemIllustration, Illustration.id == ItemIllustration.illustration_id
        )
        .group_by(Illustration.id)
        .order_by(Illustration.created_at.desc())
        .offset(offset)
        .limit(limit)
    )

    results = db.execute(query).all()

    illustrations = [
        IllustrationListEntry(
            id=illustration.id,
            source_url=illustration.source_url,
            width=illustration.width,
            height=illustration.height,
            file_size_bytes=illustration.file_size_bytes,
            created_at=illustration.created_at,
            item_count=item_count or 0,
        )
        for illustration, item_count in results
    ]

    total_query = select(func.count(Illustration.id))
    total = db.execute(total_query).scalar_one()

    return IllustrationListResponse(illustrations=illustrations, total=total)


@router.get("/{illustration_id}", response_model=IllustrationListEntry)
async def get_illustration(
    illustration_id: str, db: Annotated[Session, Depends(get_session)]
) -> IllustrationListEntry:
    """Get illustration metadata with item count."""
    query = (
        select(
            Illustration,
            func.count(ItemIllustration.id).label("item_count"),
        )
        .outerjoin(
            ItemIllustration, Illustration.id == ItemIllustration.illustration_id
        )
        .where(Illustration.id == illustration_id)
        .group_by(Illustration.id)
    )

    result = db.execute(query).first()

    if not result:
        raise HTTPException(status_code=404, detail="Illustration not found")

    illustration, item_count = result

    return IllustrationListEntry(
        id=illustration.id,
        source_url=illustration.source_url,
        width=illustration.width,
        height=illustration.height,
        file_size_bytes=illustration.file_size_bytes,
        created_at=illustration.created_at,
        item_count=item_count or 0,
    )


@router.get("/{illustration_id}/image")
async def get_illustration_image(
    illustration_id: str, db: Annotated[Session, Depends(get_session)]
) -> FileResponse:
    """Serve full WebP image."""
    return _serve_illustration_file(illustration_id, db, thumbnail=False)


@router.get("/{illustration_id}/thumbnail")
async def get_illustration_thumbnail(
    illustration_id: str, db: Annotated[Session, Depends(get_session)]
) -> FileResponse:
    """Serve thumbnail WebP image."""
    return _serve_illustration_file(illustration_id, db, thumbnail=True)


@router.delete("/{illustration_id}")
async def delete_illustration(
    illustration_id: str, db: Annotated[Session, Depends(get_session)]
) -> dict[str, str]:
    """Delete illustration from database and remove files from disk."""
    illustration = db.get(Illustration, illustration_id)

    if not illustration:
        raise HTTPException(status_code=404, detail="Illustration not found")

    db.delete(illustration)
    db.commit()

    _get_illustration_path(illustration_id, thumbnail=False).unlink(missing_ok=True)
    _get_illustration_path(illustration_id, thumbnail=True).unlink(missing_ok=True)

    return {"status": "deleted"}
