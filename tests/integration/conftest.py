"""Pytest configuration for integration tests."""

from contextlib import contextmanager
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from chitai.db.base import Base
from chitai.server.app import app

if TYPE_CHECKING:
    from collections.abc import Generator

# Module-level storage for the current test's session factory, allowing
# the db_session fixture to access it.
_test_session_factory: sessionmaker[Session] | None = None


@pytest.fixture(autouse=True)
def setup_test_database():
    """Set up in-memory database for integration tests.

    This fixture automatically runs before each test and patches get_session() to use
    an in-memory SQLite database instead of the real database file.
    """
    global _test_session_factory  # noqa: PLW0603

    app.state.session.reset()

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    _test_session_factory = sessionmaker(bind=engine)

    @contextmanager
    def test_get_session() -> Generator[Session]:
        assert _test_session_factory is not None
        session = _test_session_factory()
        try:
            yield session
        finally:
            session.close()

    with patch("chitai.server.app.get_session", test_get_session):
        yield

    app.state.session.reset()
    _test_session_factory = None
    engine.dispose()


@pytest.fixture
def db_session() -> Generator[Session]:
    """Provide a database session for test assertions.

    Use this fixture when tests need to query the database directly to verify side
    effects of WebSocket operations.
    """
    if _test_session_factory is None:
        msg = "db_session fixture requires setup_test_database to run first"
        raise RuntimeError(msg)

    session = _test_session_factory()
    try:
        yield session
    finally:
        session.close()
