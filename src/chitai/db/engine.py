"""Database engine and session management."""

from collections.abc import Generator  # noqa: TC003
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from chitai.settings import settings

# Create engine
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},  # Needed for SQLite
    echo=False,
)

# Create default session factory instance
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
# Injectable global session factory
_session_factory: sessionmaker[Session] = SessionLocal


def configure_session_factory(factory: sessionmaker[Session] | None) -> None:
    """Configure the session factory used by get_session().

    This allows tests to inject a test database session factory without patching.

    Parameters
    ----------
    factory : sessionmaker[Session] | None
        Session factory to use. Pass None to reset to default (SessionLocal).

    """
    global _session_factory  # noqa: PLW0603
    _session_factory = factory if factory is not None else SessionLocal


def get_session() -> Generator[Session]:
    """Database session generator for FastAPI Depends().

    Yields
    ------
    Session
        SQLAlchemy database session

    """
    session = _session_factory()
    try:
        yield session
    finally:
        session.close()


# Context manager wrapper for WebSocket handlers
get_session_ctx = contextmanager(get_session)
