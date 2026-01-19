"""Unit tests for database models."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from chitai.db.base import Base
from chitai.db.models import Item, Language, SessionItem, Settings
from chitai.db.models import Session as DBSession

if TYPE_CHECKING:
    from collections.abc import Generator

    from sqlalchemy.orm import Session


@pytest.fixture
def session() -> Generator[Session]:
    """Create an in-memory SQLite database for testing.

    Yields
    ------
    Session
        SQLAlchemy session with clean schema
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield session
    session.close()


def test_item_creation(session: Session) -> None:
    """Test creating and retrieving an Item."""
    item = Item(language=Language.RUSSIAN, text="молоко")
    session.add(item)
    session.commit()

    retrieved = session.query(Item).filter_by(text="молоко").first()
    assert retrieved is not None
    assert retrieved.text == "молоко"
    assert retrieved.language == Language.RUSSIAN
    assert isinstance(retrieved.created_at, datetime)
    assert len(retrieved.id) == 36  # UUID string length


def test_session_creation(session: Session) -> None:
    """Test creating and retrieving a Session."""
    db_session = DBSession(language=Language.RUSSIAN)
    session.add(db_session)
    session.commit()

    retrieved = session.query(DBSession).first()
    assert retrieved is not None
    assert retrieved.language == Language.RUSSIAN
    assert isinstance(retrieved.started_at, datetime)
    assert retrieved.ended_at is None
    assert len(retrieved.id) == 36


def test_session_end(session: Session) -> None:
    """Test ending a session."""
    db_session = DBSession(language=Language.RUSSIAN)
    session.add(db_session)
    session.commit()

    # End the session
    db_session.ended_at = datetime.now(UTC)
    session.commit()

    retrieved = session.query(DBSession).first()
    assert retrieved is not None
    assert retrieved.ended_at is not None
    assert retrieved.ended_at > retrieved.started_at


def test_session_item_creation(session: Session) -> None:
    """Test creating SessionItem linking Session and Item."""
    # Create item and session
    item = Item(language=Language.RUSSIAN, text="молоко")
    db_session = DBSession(language=Language.RUSSIAN)
    session.add(item)
    session.add(db_session)
    session.commit()

    # Create session item
    session_item = SessionItem(session_id=db_session.id, item_id=item.id)
    session.add(session_item)
    session.commit()

    # Verify relationships
    retrieved_session_item = session.query(SessionItem).first()
    assert retrieved_session_item is not None
    assert retrieved_session_item.session_id == db_session.id
    assert retrieved_session_item.item_id == item.id
    assert isinstance(retrieved_session_item.displayed_at, datetime)
    assert retrieved_session_item.completed_at is None
    assert len(retrieved_session_item.id) == 36


def test_session_item_relationships(session: Session) -> None:
    """Test SessionItem relationships to Session and Item."""
    # Create item and session
    item = Item(language=Language.RUSSIAN, text="молоко")
    db_session = DBSession(language=Language.RUSSIAN)
    session.add(item)
    session.add(db_session)
    session.commit()

    # Create session item
    session_item = SessionItem(session_id=db_session.id, item_id=item.id)
    session.add(session_item)
    session.commit()

    # Test relationships
    retrieved_session_item = session.query(SessionItem).first()
    assert retrieved_session_item is not None
    assert retrieved_session_item.session.id == db_session.id
    assert retrieved_session_item.item.text == "молоко"

    # Test back references
    assert len(db_session.session_items) == 1
    assert db_session.session_items[0].item.text == "молоко"
    assert len(item.session_items) == 1
    assert item.session_items[0].session.id == db_session.id


def test_session_item_completion(session: Session) -> None:
    """Test marking a SessionItem as completed."""
    item = Item(language=Language.RUSSIAN, text="молоко")
    db_session = DBSession(language=Language.RUSSIAN)
    session.add_all([item, db_session])
    session.commit()

    # Create session item with persisted IDs
    session_item = SessionItem(session_id=db_session.id, item_id=item.id)
    session.add(session_item)
    session.commit()

    # Mark as completed
    session_item.completed_at = datetime.now(UTC)
    session.commit()

    retrieved = session.query(SessionItem).first()
    assert retrieved is not None
    assert retrieved.completed_at is not None
    assert retrieved.completed_at >= retrieved.displayed_at


def test_session_cascade_delete(session: Session) -> None:
    """Test that deleting a session deletes its session_items."""
    item = Item(language=Language.RUSSIAN, text="молоко")
    db_session = DBSession(language=Language.RUSSIAN)
    session.add_all([item, db_session])
    session.commit()

    # Create session item with persisted IDs
    session_item = SessionItem(session_id=db_session.id, item_id=item.id)
    session.add(session_item)
    session.commit()

    # Delete session
    session.delete(db_session)
    session.commit()

    # Session items should be deleted
    assert session.query(SessionItem).count() == 0
    # But items should still exist
    assert session.query(Item).count() == 1


def test_settings_creation(session: Session) -> None:
    """Test creating and retrieving Settings."""
    settings = Settings()
    session.add(settings)
    session.commit()

    retrieved = session.query(Settings).first()
    assert retrieved is not None
    assert retrieved.id == 1
    assert retrieved.show_syllables is True
    assert retrieved.dim_read_words is True
    assert retrieved.dim_future_words is False


def test_settings_update(session: Session) -> None:
    """Test updating settings."""
    settings = Settings()
    session.add(settings)
    session.commit()

    # Update settings
    settings.show_syllables = False
    settings.dim_future_words = True
    session.commit()

    retrieved = session.query(Settings).first()
    assert retrieved is not None
    assert retrieved.show_syllables is False
    assert retrieved.dim_read_words is True
    assert retrieved.dim_future_words is True


def test_language_enum_values() -> None:
    """Test Language enum values."""
    assert Language.RUSSIAN.value == "ru"
    assert Language.GERMAN.value == "de"
    assert Language.ENGLISH.value == "en"
