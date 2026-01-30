"""REST API endpoints for sessions."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session  # noqa: TC002

from chitai.db.engine import get_session
from chitai.db.models import Item, SessionItem
from chitai.db.models import Session as DBSession
from chitai.server.routers.schemas import (
    SessionDetailResponse,
    SessionItemResponse,
    SessionListResponse,
    SessionResponse,
)

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.get("", response_model=SessionListResponse)
async def list_sessions(
    db: Annotated[Session, Depends(get_session)],
) -> SessionListResponse:
    """List all sessions with item counts.

    Returns all sessions in the database, enriched with the count of items displayed
    during each session.

    Parameters
    ----------
    db : Session
        Database session (injected)

    Returns
    -------
    SessionListResponse
        List of sessions with item counts

    """
    sessions_query = (
        select(
            DBSession,
            func.count(SessionItem.id).label("item_count"),
        )
        .outerjoin(SessionItem, DBSession.id == SessionItem.session_id)
        .group_by(DBSession.id)
        .order_by(DBSession.started_at.desc())
    )

    results = db.execute(sessions_query).all()

    sessions = [
        SessionResponse(
            id=session.id,
            language=session.language,
            started_at=session.started_at,
            ended_at=session.ended_at,
            item_count=item_count or 0,
        )
        for session, item_count in results
    ]

    return SessionListResponse(sessions=sessions)


@router.get("/{session_id}", response_model=SessionDetailResponse)
async def get_session_detail(
    session_id: str, db: Annotated[Session, Depends(get_session)]
) -> SessionDetailResponse:
    """Get a single session with all its items.

    Parameters
    ----------
    session_id : str
        Session UUID
    db : Session
        Database session (injected)

    Returns
    -------
    SessionDetailResponse
        Session with all items displayed during it

    Raises
    ------
    HTTPException
        404 if session not found

    """
    session = db.get(DBSession, session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Query session items with their item text, ordered by display time
    session_items_query = (
        select(SessionItem, Item.text)
        .join(Item, SessionItem.item_id == Item.id)
        .where(SessionItem.session_id == session_id)
        .order_by(SessionItem.displayed_at)
    )

    results = db.execute(session_items_query).all()

    items = [
        SessionItemResponse(
            id=session_item.id,
            item_id=session_item.item_id,
            text=text,
            displayed_at=session_item.displayed_at,
            completed_at=session_item.completed_at,
        )
        for session_item, text in results
    ]

    return SessionDetailResponse(
        id=session.id,
        language=session.language,
        started_at=session.started_at,
        ended_at=session.ended_at,
        items=items,
    )


@router.delete("/{session_id}")
async def delete_session(
    session_id: str, db: Annotated[Session, Depends(get_session)]
) -> dict[str, str]:
    """Delete a session and all its associated session items.

    Parameters
    ----------
    session_id : str
        Session UUID
    db : Session
        Database session (injected)

    Returns
    -------
    dict[str, str]
        Success status

    Raises
    ------
    HTTPException
        404 if session not found

    """
    session = db.get(DBSession, session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    db.delete(session)
    db.commit()

    return {"status": "deleted"}
