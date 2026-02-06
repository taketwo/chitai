"""Unit tests for database models."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from chitai.db.base import Base
from chitai.db.models import (
    Illustration,
    Item,
    ItemIllustration,
    Language,
    SessionItem,
    Settings,
)
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
    engine.dispose()


def test_item_creation(session: Session) -> None:
    """Test creating and retrieving an Item."""
    item = Item(language=Language.RUSSIAN, text="молоко")
    session.add(item)
    session.commit()

    retrieved = session.scalars(select(Item).where(Item.text == "молоко")).first()
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

    retrieved = session.scalars(select(DBSession)).first()
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

    retrieved = session.scalars(select(DBSession)).first()
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

    # Create session item (not displayed yet)
    session_item = SessionItem(session_id=db_session.id, item_id=item.id)
    session.add(session_item)
    session.commit()

    # Verify relationships
    retrieved_session_item = session.scalars(select(SessionItem)).first()
    assert retrieved_session_item is not None
    assert retrieved_session_item.session_id == db_session.id
    assert retrieved_session_item.item_id == item.id
    assert retrieved_session_item.displayed_at is None
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
    retrieved_session_item = session.scalars(select(SessionItem)).first()
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

    # Create session item and mark as displayed
    now = datetime.now(UTC)
    session_item = SessionItem(
        session_id=db_session.id, item_id=item.id, displayed_at=now
    )
    session.add(session_item)
    session.commit()

    # Mark as completed
    session_item.completed_at = datetime.now(UTC)
    session.commit()

    retrieved = session.scalars(select(SessionItem)).first()
    assert retrieved is not None
    assert retrieved.displayed_at is not None
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
    assert session.scalar(select(func.count()).select_from(SessionItem)) == 0
    # But items should still exist
    assert session.scalar(select(func.count()).select_from(Item)) == 1


def test_settings_creation(session: Session) -> None:
    """Test creating and retrieving Settings."""
    settings = Settings()
    session.add(settings)
    session.commit()

    retrieved = session.scalars(select(Settings)).first()
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

    retrieved = session.scalars(select(Settings)).first()
    assert retrieved is not None
    assert retrieved.show_syllables is False
    assert retrieved.dim_read_words is True
    assert retrieved.dim_future_words is True


def test_language_enum_values() -> None:
    """Test Language enum values."""
    assert Language.RUSSIAN.value == "ru"
    assert Language.GERMAN.value == "de"
    assert Language.ENGLISH.value == "en"


def test_illustration_creation(session: Session) -> None:
    """Test creating and retrieving an Illustration."""
    illustration = Illustration(
        source_url="https://example.com/image.jpg",
        width=800,
        height=600,
        file_size_bytes=12345,
    )
    session.add(illustration)
    session.commit()

    retrieved = session.scalars(select(Illustration)).first()
    assert retrieved is not None
    assert retrieved.source_url == "https://example.com/image.jpg"
    assert retrieved.width == 800
    assert retrieved.height == 600
    assert retrieved.file_size_bytes == 12345
    assert isinstance(retrieved.created_at, datetime)
    assert len(retrieved.id) == 36


def test_illustration_without_source_url(session: Session) -> None:
    """Test creating an Illustration from file upload (no source URL)."""
    illustration = Illustration(
        source_url=None, width=1024, height=768, file_size_bytes=54321
    )
    session.add(illustration)
    session.commit()

    retrieved = session.scalars(select(Illustration)).first()
    assert retrieved is not None
    assert retrieved.source_url is None
    assert retrieved.width == 1024
    assert retrieved.height == 768


def test_item_illustration_creation(session: Session) -> None:
    """Test creating ItemIllustration linking Item and Illustration."""
    item = Item(language=Language.RUSSIAN, text="собака")
    illustration = Illustration(width=800, height=600, file_size_bytes=12345)
    session.add_all([item, illustration])
    session.commit()

    link = ItemIllustration(item_id=item.id, illustration_id=illustration.id)
    session.add(link)
    session.commit()

    retrieved_link = session.scalars(select(ItemIllustration)).first()
    assert retrieved_link is not None
    assert retrieved_link.item_id == item.id
    assert retrieved_link.illustration_id == illustration.id
    assert len(retrieved_link.id) == 36


def test_item_illustration_relationships(session: Session) -> None:
    """Test ItemIllustration relationships to Item and Illustration."""
    item = Item(language=Language.RUSSIAN, text="собака")
    illustration = Illustration(width=800, height=600, file_size_bytes=12345)
    session.add_all([item, illustration])
    session.commit()

    link = ItemIllustration(item_id=item.id, illustration_id=illustration.id)
    session.add(link)
    session.commit()

    retrieved_link = session.scalars(select(ItemIllustration)).first()
    assert retrieved_link is not None
    assert retrieved_link.item.text == "собака"
    assert retrieved_link.illustration.width == 800

    # Test back references
    assert len(item.item_illustrations) == 1
    assert item.item_illustrations[0].illustration.width == 800
    assert len(illustration.item_illustrations) == 1
    assert illustration.item_illustrations[0].item.text == "собака"


def test_multiple_illustrations_per_item(session: Session) -> None:
    """Test that an item can have multiple illustrations."""
    item = Item(language=Language.RUSSIAN, text="собака")
    illustration1 = Illustration(width=800, height=600, file_size_bytes=12345)
    illustration2 = Illustration(width=1024, height=768, file_size_bytes=54321)
    session.add_all([item, illustration1, illustration2])
    session.commit()

    link1 = ItemIllustration(item_id=item.id, illustration_id=illustration1.id)
    link2 = ItemIllustration(item_id=item.id, illustration_id=illustration2.id)
    session.add_all([link1, link2])
    session.commit()

    assert len(item.item_illustrations) == 2
    widths = {link.illustration.width for link in item.item_illustrations}
    assert widths == {800, 1024}


def test_multiple_items_per_illustration(session: Session) -> None:
    """Test that an illustration can be linked to multiple items."""
    item1 = Item(language=Language.RUSSIAN, text="собака")
    item2 = Item(language=Language.RUSSIAN, text="кошка")
    illustration = Illustration(width=800, height=600, file_size_bytes=12345)
    session.add_all([item1, item2, illustration])
    session.commit()

    link1 = ItemIllustration(item_id=item1.id, illustration_id=illustration.id)
    link2 = ItemIllustration(item_id=item2.id, illustration_id=illustration.id)
    session.add_all([link1, link2])
    session.commit()

    assert len(illustration.item_illustrations) == 2
    texts = {link.item.text for link in illustration.item_illustrations}
    assert texts == {"собака", "кошка"}


def test_illustration_cascade_delete(session: Session) -> None:
    """Test that deleting an illustration deletes item_illustrations but not items."""
    item = Item(language=Language.RUSSIAN, text="собака")
    illustration = Illustration(width=800, height=600, file_size_bytes=12345)
    session.add_all([item, illustration])
    session.commit()

    link = ItemIllustration(item_id=item.id, illustration_id=illustration.id)
    session.add(link)
    session.commit()

    # Delete illustration
    session.delete(illustration)
    session.commit()

    # ItemIllustration should be deleted
    assert session.scalar(select(func.count()).select_from(ItemIllustration)) == 0
    # Item should still exist
    assert session.scalar(select(func.count()).select_from(Item)) == 1


def test_item_cascade_delete_with_illustrations(session: Session) -> None:
    """Test that deleting an item deletes item_illustrations but not illustrations."""
    item = Item(language=Language.RUSSIAN, text="собака")
    illustration = Illustration(width=800, height=600, file_size_bytes=12345)
    session.add_all([item, illustration])
    session.commit()

    link = ItemIllustration(item_id=item.id, illustration_id=illustration.id)
    session.add(link)
    session.commit()

    # Delete item
    session.delete(item)
    session.commit()

    # ItemIllustration should be deleted
    assert session.scalar(select(func.count()).select_from(ItemIllustration)) == 0
    # Illustration should still exist
    assert session.scalar(select(func.count()).select_from(Illustration)) == 1
