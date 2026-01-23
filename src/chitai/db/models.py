"""Database models for Chitai.

This module defines the SQLAlchemy ORM models for the application:
- Item: Words, phrases, or sentences with optional illustrations
- Session: Reading practice sessions
- SessionItem: Join table linking sessions to items with timestamps
- Settings: Application settings
"""

from datetime import UTC, datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from chitai.db.base import Base


def utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(UTC)


class Language(str, Enum):
    """Supported languages for text processing."""

    RUSSIAN = "ru"
    GERMAN = "de"
    ENGLISH = "en"


class Item(Base):
    """An item represents a word, phrase, or sentence to be read.

    Attributes
    ----------
    id : str
        UUID primary key
    language : Language
        Language of the text (ru, de, en)
    text : str
        The word, phrase, or sentence
    created_at : datetime
        When the item was created
    session_items : list[SessionItem]
        Related session items (usage history)
    """

    __tablename__ = "items"
    __table_args__ = (Index("ix_items_text_language", "text", "language"),)

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    language: Mapped[Language] = mapped_column(String(2), nullable=False)
    text: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utc_now
    )

    # Relationships
    session_items: Mapped[list[SessionItem]] = relationship(
        "SessionItem", back_populates="item"
    )


class Session(Base):
    """A reading practice session.

    Attributes
    ----------
    id : str
        UUID primary key
    language : Language
        Language of the session (ru, de, en)
    started_at : datetime
        Session start time
    ended_at : datetime | None
        Session end time (None if still active)
    session_items : list[SessionItem]
        Items displayed during this session
    """

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    language: Mapped[Language] = mapped_column(String(2), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utc_now
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    session_items: Mapped[list[SessionItem]] = relationship(
        "SessionItem", back_populates="session", cascade="all, delete-orphan"
    )


class SessionItem(Base):
    """Join table linking sessions to items with timestamps.

    Attributes
    ----------
    id : str
        UUID primary key
    session_id : str
        Foreign key to Session
    item_id : str
        Foreign key to Item
    displayed_at : datetime
        When item was shown
    completed_at : datetime | None
        When item was finished reading (None if not completed yet)
    session : Session
        Related session
    item : Item
        Related item
    """

    __tablename__ = "session_items"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sessions.id"), nullable=False
    )
    item_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("items.id"), nullable=False
    )
    displayed_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utc_now
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    session: Mapped[Session] = relationship("Session", back_populates="session_items")
    item: Mapped[Item] = relationship("Item", back_populates="session_items")


class Settings(Base):
    """Application settings.

    This table has a single row with id=1. Settings are persisted and
    editable from the parent interface.

    Attributes
    ----------
    id : int
        Primary key (always 1)
    show_syllables : bool
        Display syllable annotations
    dim_read_words : bool
        Dim words that have already been read
    dim_future_words : bool
        Dim words that haven't been read yet
    """

    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    show_syllables: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    dim_read_words: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    dim_future_words: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
