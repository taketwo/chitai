"""REST API endpoints for items."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session  # noqa: TC002

from chitai.db.engine import get_session
from chitai.db.models import Item, SessionItem
from chitai.server.routers.schemas import ItemListResponse, ItemResponse

router = APIRouter(prefix="/api/items", tags=["items"])


@router.get("", response_model=ItemListResponse)
async def list_items(db: Annotated[Session, Depends(get_session)]) -> ItemListResponse:
    """List all items with usage statistics.

    Returns all items in the database, enriched with usage count and last used
    timestamp from session history.

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
            func.count(SessionItem.id).label("usage_count"),
            func.max(SessionItem.displayed_at).label("last_used_at"),
        )
        .outerjoin(SessionItem, Item.id == SessionItem.item_id)
        .group_by(Item.id)
        .order_by(Item.created_at.desc())
    )

    results = db.execute(items_query).all()

    items = [
        ItemResponse(
            id=item.id,
            text=item.text,
            language=item.language,
            created_at=item.created_at,
            usage_count=usage_count or 0,
            last_used_at=last_used_at,
        )
        for item, usage_count, last_used_at in results
    ]

    return ItemListResponse(items=items)


@router.get("/{item_id}", response_model=ItemResponse)
async def get_item(
    item_id: str, db: Annotated[Session, Depends(get_session)]
) -> ItemResponse:
    """Get a single item with usage statistics.

    Parameters
    ----------
    item_id : str
        Item UUID
    db : Session
        Database session (injected)

    Returns
    -------
    ItemResponse
        Item with usage statistics

    Raises
    ------
    HTTPException
        404 if item not found

    """
    item_query = (
        select(
            Item,
            func.count(SessionItem.id).label("usage_count"),
            func.max(SessionItem.displayed_at).label("last_used_at"),
        )
        .outerjoin(SessionItem, Item.id == SessionItem.item_id)
        .where(Item.id == item_id)
        .group_by(Item.id)
    )

    result = db.execute(item_query).first()

    if not result:
        raise HTTPException(status_code=404, detail="Item not found")

    item, usage_count, last_used_at = result

    return ItemResponse(
        id=item.id,
        text=item.text,
        language=item.language,
        created_at=item.created_at,
        usage_count=usage_count or 0,
        last_used_at=last_used_at,
    )
