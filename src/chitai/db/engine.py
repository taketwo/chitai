"""Database engine and session management."""

from typing import TYPE_CHECKING

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from chitai.settings import settings

if TYPE_CHECKING:
    from collections.abc import Generator

    from sqlalchemy.orm import Session

# Create engine
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},  # Needed for SQLite
    echo=False,
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_session() -> Generator[Session]:
    """Get a database session.

    Yields
    ------
    Session
        SQLAlchemy database session

    Examples
    --------
    >>> with get_session() as session:
    ...     items = session.query(Item).all()
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
