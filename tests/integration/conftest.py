"""Pytest configuration for integration tests."""

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from chitai.db.base import Base
from chitai.db.engine import configure_session_factory
from chitai.server.app import app

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture(autouse=True)
def reset_app_state():
    """Reset app state before and after each test.

    Ensures each test starts with clean session state and stopped grace timer. Also
    stops any running grace timers after test completes.
    """
    # Setup: reset state to defaults
    app.state.context.session.reset()
    app.state.context.grace_timer.stop()
    app.state.context.grace_timer.grace_period_seconds = (
        3600  # Default grace period (tests can override)
    )

    yield

    # Teardown: stop timer and reset state
    app.state.context.grace_timer.stop()
    app.state.context.session.reset()


@pytest.fixture
def test_db():
    """Provide in-memory test database.

    Creates a fresh SQLite in-memory database with all tables for each test. Returns a
    sessionmaker that can be used to create database sessions.

    Returns
    -------
    sessionmaker[Session]
        Session factory for creating database sessions
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    yield session_factory

    engine.dispose()


@pytest.fixture
def db_session(test_db: sessionmaker[Session]) -> Generator[Session]:
    """Provide a database session for test assertions.

    Use this fixture when tests need to query the database directly to verify side
    effects of WebSocket operations.

    Parameters
    ----------
    test_db : sessionmaker[Session]
        Session factory from test_db fixture

    Yields
    ------
    Session
        Database session for test use
    """
    session = test_db()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def use_test_db(test_db: sessionmaker[Session]):
    """Configure get_session() to use test database.

    Automatically applied to all tests. Ensures that any code calling get_session()
    or get_session_ctx() receives a connection to the test database instead of the
    real database file.

    Parameters
    ----------
    test_db : sessionmaker[Session]
        Session factory from test_db fixture

    """
    configure_session_factory(test_db)
    yield
    configure_session_factory(None)  # Reset to default
