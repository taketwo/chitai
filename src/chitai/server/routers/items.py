"""REST API endpoints for items."""

from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session  # noqa: TC002

from chitai.db.engine import get_session
from chitai.db.models import Illustration, Item, ItemIllustration, Language, SessionItem
from chitai.server.routers.schemas import (
    ItemAutocompleteEntry,
    ItemAutocompleteResponse,
    ItemIllustrationEntry,
    ItemListEntry,
    ItemListResponse,
)

router = APIRouter(prefix="/api/items", tags=["items"])


@router.post("", response_model=ItemListEntry)
async def get_or_create_item(
    text: Annotated[str, Form()],
    language: Annotated[Language, Form()],
    response: Response,
    *,
    db: Annotated[Session, Depends(get_session)],
) -> ItemListEntry:
    """Get existing item or create a new one (idempotent).

    Returns 200 with existing item if found, 201 with new item if created.

    Parameters
    ----------
    text : str
        The word, phrase, or sentence (via form data)
    language : Language
        Language of the text: ru, de, or en (via form data)
    db : Session
        Database session (injected)

    Raises
    ------
    HTTPException
        400 if text is empty or only whitespace

    """
    normalized_text = text.strip()
    if not normalized_text:
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    usage_count = 0
    last_used_at = None
    illustration_count = 0

    # Try to find existing item
    item = db.scalars(
        select(Item).where(Item.text == normalized_text, Item.language == language)
    ).first()

    if item:
        # Fetch usage stats and illustration count for existing item
        item_query = (
            select(
                Item,
                func.count(SessionItem.id.distinct()).label("usage_count"),
                func.max(SessionItem.displayed_at).label("last_used_at"),
                func.count(ItemIllustration.id.distinct()).label("illustration_count"),
            )
            .outerjoin(SessionItem, Item.id == SessionItem.item_id)
            .outerjoin(ItemIllustration, Item.id == ItemIllustration.item_id)
            .where(Item.id == item.id)
            .group_by(Item.id)
        )

        if result := db.execute(item_query).first():
            _, usage_count, last_used_at, illustration_count = result

        response.status_code = 200
    else:
        # Create new item
        item = Item(text=normalized_text, language=language)
        db.add(item)
        db.commit()
        db.refresh(item)
        response.status_code = 201

    return ItemListEntry(
        id=item.id,
        text=item.text,
        language=item.language,
        created_at=item.created_at,
        usage_count=usage_count,
        last_used_at=last_used_at,
        illustration_count=illustration_count,
    )


@router.get("", response_model=ItemListResponse)
async def list_items(db: Annotated[Session, Depends(get_session)]) -> ItemListResponse:
    """List all items with usage statistics and illustration counts.

    Returns all items in the database, enriched with usage count, last used
    timestamp, and illustration count.

    Parameters
    ----------
    db : Session
        Database session (injected)

    Returns
    -------
    ItemListResponse
        List of items with usage statistics

    """
    items_query = (
        select(
            Item,
            func.count(SessionItem.id.distinct()).label("usage_count"),
            func.max(SessionItem.displayed_at).label("last_used_at"),
            func.count(ItemIllustration.id.distinct()).label("illustration_count"),
        )
        .outerjoin(SessionItem, Item.id == SessionItem.item_id)
        .outerjoin(ItemIllustration, Item.id == ItemIllustration.item_id)
        .group_by(Item.id)
        .order_by(Item.created_at.desc())
    )

    results = db.execute(items_query).all()

    items = [
        ItemListEntry(
            id=item.id,
            text=item.text,
            language=item.language,
            created_at=item.created_at,
            usage_count=usage_count or 0,
            last_used_at=last_used_at,
            illustration_count=illustration_count or 0,
        )
        for item, usage_count, last_used_at, illustration_count in results
    ]

    return ItemListResponse(items=items)


@router.get("/autocomplete", response_model=ItemAutocompleteResponse)
async def autocomplete_items(
    text: str,
    language: Language,
    limit: int = 3,
    *,
    db: Annotated[Session, Depends(get_session)],
) -> ItemAutocompleteResponse:
    """Autocomplete item text based on prefix match.

    Returns items matching the given text prefix, ordered alphabetically. Used for quick
    text entry assistance in the controller UI.

    Parameters
    ----------
    text : str
        Text prefix to match
    language : Language
        Language to filter by (ru, de, en)
    limit : int, optional
        Maximum number of suggestions to return (default 3)
    db : Session
        Database session (injected)

    Returns
    -------
    ItemAutocompleteResponse
        List of matching items (id and text only)

    """
    # Simple prefix match query - no joins needed for fast autocomplete
    query = (
        select(Item.id, Item.text)
        .where(Item.text.like(f"{text}%"))
        .where(Item.language == language)
        .order_by(Item.text)
        .limit(limit)
    )

    results = db.execute(query).all()

    suggestions = [
        ItemAutocompleteEntry(id=str(item_id), text=item_text)
        for item_id, item_text in results
    ]

    return ItemAutocompleteResponse(suggestions=suggestions)


@router.get("/{item_id}", response_model=ItemListEntry)
async def get_item(
    item_id: str, db: Annotated[Session, Depends(get_session)]
) -> ItemListEntry:
    """Get a single item with usage statistics and illustration count.

    Parameters
    ----------
    item_id : str
        Item UUID
    db : Session
        Database session (injected)

    Returns
    -------
    ItemListEntry
        Item with usage statistics

    Raises
    ------
    HTTPException
        404 if item not found

    """
    item_query = (
        select(
            Item,
            func.count(SessionItem.id.distinct()).label("usage_count"),
            func.max(SessionItem.displayed_at).label("last_used_at"),
            func.count(ItemIllustration.id.distinct()).label("illustration_count"),
        )
        .outerjoin(SessionItem, Item.id == SessionItem.item_id)
        .outerjoin(ItemIllustration, Item.id == ItemIllustration.item_id)
        .where(Item.id == item_id)
        .group_by(Item.id)
    )

    result = db.execute(item_query).first()

    if not result:
        raise HTTPException(status_code=404, detail="Item not found")

    item, usage_count, last_used_at, illustration_count = result

    return ItemListEntry(
        id=item.id,
        text=item.text,
        language=item.language,
        created_at=item.created_at,
        usage_count=usage_count or 0,
        last_used_at=last_used_at,
        illustration_count=illustration_count or 0,
    )


@router.delete("/{item_id}")
async def delete_item(
    item_id: str, db: Annotated[Session, Depends(get_session)]
) -> dict[str, str]:
    """Delete an item and all its associated session items.

    Parameters
    ----------
    item_id : str
        Item UUID
    db : Session
        Database session (injected)

    Returns
    -------
    dict[str, str]
        Success status

    Raises
    ------
    HTTPException
        404 if item not found

    """
    item = db.get(Item, item_id)

    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    db.delete(item)
    db.commit()

    return {"status": "deleted"}


@router.get("/{item_id}/illustrations", response_model=list[ItemIllustrationEntry])
async def list_item_illustrations(
    item_id: str, db: Annotated[Session, Depends(get_session)]
) -> list[ItemIllustrationEntry]:
    """List all illustrations linked to an item."""
    item = db.get(Item, item_id)

    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    query = (
        select(Illustration)
        .join(ItemIllustration, Illustration.id == ItemIllustration.illustration_id)
        .where(ItemIllustration.item_id == item_id)
        .order_by(Illustration.created_at.desc())
    )

    illustrations = db.scalars(query).all()

    return [
        ItemIllustrationEntry(
            id=illustration.id,
            width=illustration.width,
            height=illustration.height,
        )
        for illustration in illustrations
    ]


@router.post("/{item_id}/illustrations/{illustration_id}", status_code=201)
async def link_illustration_to_item(
    item_id: str,
    illustration_id: str,
    db: Annotated[Session, Depends(get_session)],
) -> dict[str, str]:
    """Link an illustration to an item."""
    item = db.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    illustration = db.get(Illustration, illustration_id)
    if not illustration:
        raise HTTPException(status_code=404, detail="Illustration not found")

    link = ItemIllustration(item_id=item_id, illustration_id=illustration_id)
    db.add(link)

    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=409, detail="Link already exists") from e

    return {"status": "linked"}


@router.delete("/{item_id}/illustrations/{illustration_id}")
async def unlink_illustration_from_item(
    item_id: str,
    illustration_id: str,
    db: Annotated[Session, Depends(get_session)],
) -> dict[str, str]:
    """Unlink an illustration from an item."""
    link = db.scalars(
        select(ItemIllustration)
        .where(ItemIllustration.item_id == item_id)
        .where(ItemIllustration.illustration_id == illustration_id)
    ).first()

    if not link:
        raise HTTPException(status_code=404, detail="Link not found")

    db.delete(link)
    db.commit()

    return {"status": "unlinked"}
