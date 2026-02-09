"""Helper utilities for integration tests."""

from contextlib import AbstractAsyncContextManager, asynccontextmanager
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from httpx import AsyncClient
from httpx_ws import aconnect_ws
from httpx_ws.transport import ASGIWebSocketTransport

from chitai.db.models import Illustration, Item, SessionItem
from chitai.db.models import Session as DBSession
from chitai.server.app import app

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from httpx_ws import AsyncWebSocketSession
    from sqlalchemy.orm import Session

# Test constants
FAKE_UUID = "00000000-0000-0000-0000-000000000000"
DEFAULT_LANGUAGE = "ru"


@asynccontextmanager
async def _connect_ws(role: str) -> AsyncGenerator[AsyncWebSocketSession]:
    """Connect a WebSocket client with the given role."""
    async with (
        ASGIWebSocketTransport(app=app) as transport,
        AsyncClient(transport=transport, base_url="http://test") as client,
        aconnect_ws(f"http://test/ws?role={role}", client) as ws,
    ):
        yield ws


def connect_controller() -> AbstractAsyncContextManager[AsyncWebSocketSession]:
    """Return async context manager for a controller WebSocket connection."""
    return _connect_ws("controller")


def connect_display() -> AbstractAsyncContextManager[AsyncWebSocketSession]:
    """Return async context manager for a display WebSocket connection."""
    return _connect_ws("display")


@asynccontextmanager
async def connect_clients() -> AsyncGenerator[
    tuple[AsyncWebSocketSession, AsyncWebSocketSession]
]:
    """Connect both controller and display WebSocket clients sharing a transport.

    Returns (controller_ws, display_ws) tuple.
    """
    async with (
        ASGIWebSocketTransport(app=app) as transport,
        AsyncClient(transport=transport, base_url="http://test") as client,
        aconnect_ws("http://test/ws?role=controller", client) as controller_ws,
        aconnect_ws("http://test/ws?role=display", client) as display_ws,
    ):
        yield controller_ws, display_ws


@asynccontextmanager
async def started_session() -> AsyncGenerator[
    tuple[AsyncWebSocketSession, AsyncWebSocketSession, str]
]:
    """Connect controller and display, start a session.

    Returns (controller_ws, display_ws, session_id) tuple. Use this when the test needs
    an active session but starting the session is not what's being tested.
    """
    async with connect_clients() as (controller_ws, display_ws):
        # Consume initial state messages
        await controller_ws.receive_json()
        await display_ws.receive_json()

        # Start session
        await controller_ws.send_json({"type": "start_session"})
        controller_data = await controller_ws.receive_json()
        await display_ws.receive_json()
        session_id = controller_data["payload"]["session_id"]
        yield controller_ws, display_ws, session_id


@asynccontextmanager
async def http_client() -> AsyncGenerator[AsyncClient]:
    """Provide HTTP client for REST API tests.

    Yields
    ------
    AsyncClient
        HTTP client configured to communicate with the FastAPI app

    """
    async with (
        ASGIWebSocketTransport(app=app) as transport,
        AsyncClient(transport=transport, base_url="http://test") as client,
    ):
        yield client


def create_session(db_session: Session, *, ended: bool = False) -> DBSession:
    """Create a test database session.

    Parameters
    ----------
    db_session : Session
        Database session to use
    ended : bool
        Whether the session should be marked as ended

    Returns
    -------
    DBSession
        Created session object

    """
    session = DBSession(
        language=DEFAULT_LANGUAGE,
        started_at=datetime.now(UTC),
        ended_at=datetime.now(UTC) if ended else None,
    )
    db_session.add(session)
    db_session.commit()
    return session


def create_item(db_session: Session, text: str) -> Item:
    """Create a test item.

    Parameters
    ----------
    db_session : Session
        Database session to use
    text : str
        Item text

    Returns
    -------
    Item
        Created item object

    """
    item = Item(text=text, language=DEFAULT_LANGUAGE)
    db_session.add(item)
    db_session.commit()
    return item


def create_session_item(
    db_session: Session,
    session_id: str,
    item_id: str,
    displayed_at: datetime | None = None,
) -> SessionItem:
    """Create a session item linking a session to an item.

    Parameters
    ----------
    db_session : Session
        Database session to use
    session_id : str
        Session UUID
    item_id : str
        Item UUID
    displayed_at : datetime | None
        When the item was displayed (defaults to now)

    Returns
    -------
    SessionItem
        Created session item object

    """
    session_item = SessionItem(
        session_id=session_id,
        item_id=item_id,
        displayed_at=displayed_at or datetime.now(UTC),
    )
    db_session.add(session_item)
    db_session.commit()
    return session_item


def create_illustration(
    db_session: Session,
    *,
    source_url: str | None = None,
    width: int = 800,
    height: int = 600,
    file_size_bytes: int = 12345,
) -> Illustration:
    """Create a test illustration.

    Parameters
    ----------
    db_session : Session
        Database session to use
    source_url : str | None
        Optional source URL
    width : int
        Image width
    height : int
        Image height
    file_size_bytes : int
        File size in bytes

    Returns
    -------
    Illustration
        Created illustration object

    """
    illustration = Illustration(
        source_url=source_url,
        width=width,
        height=height,
        file_size_bytes=file_size_bytes,
    )
    db_session.add(illustration)
    db_session.commit()
    return illustration
