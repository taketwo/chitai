"""Unit tests for SessionState."""

import pytest

from chitai.server.session import SessionState


@pytest.fixture
def session():
    """Create a fresh SessionState for testing."""
    return SessionState()


def test_initial_state(session):
    """Test that SessionState initializes with empty state."""
    assert session.session_id is None
    assert session.current_session_item_id is None
    assert session.queue == []
    assert session.words == []
    assert session.current_word_index is None


def test_set_text_splits_into_words(session):
    """Test that set_text splits input into words."""
    session.set_text("молоко хлеб сыр")
    assert session.words == ["молоко", "хлеб", "сыр"]
    assert session.current_word_index == 0


def test_set_text_resets_index(session):
    """Test that set_text resets word index to 0."""
    session.set_text("один два три")
    session.current_word_index = 2
    session.set_text("новый текст")
    assert session.current_word_index == 0


def test_advance_word_forward(session):
    """Test advancing to next word."""
    session.set_text("один два три")
    session.advance_word(1)
    assert session.current_word_index == 1
    session.advance_word(1)
    assert session.current_word_index == 2


def test_advance_word_backward(session):
    """Test going back to previous word."""
    session.set_text("один два три")
    session.current_word_index = 2
    session.advance_word(-1)
    assert session.current_word_index == 1
    session.advance_word(-1)
    assert session.current_word_index == 0


def test_advance_word_clamps_at_start(session):
    """Test that going back from first word stays at first word."""
    session.set_text("один два три")
    session.advance_word(-1)
    assert session.current_word_index == 0
    session.advance_word(-5)
    assert session.current_word_index == 0


def test_advance_word_clamps_at_end(session):
    """Test that large jumps forward clamp to last word."""
    session.set_text("один два три")
    session.advance_word(10)
    assert session.current_word_index == 2


def test_advance_word_marks_completed(session):
    """Test that advancing from last word marks item as completed."""
    session.set_text("один два три")
    session.advance_word(2)
    assert session.current_word_index == 2
    session.advance_word(1)
    assert session.current_word_index is None


def test_advance_word_cannot_go_back_from_completed(session):
    """Test that cannot go back from completed state."""
    session.set_text("один два три")
    session.advance_word(2)
    session.advance_word(1)  # Mark as completed
    assert session.current_word_index is None
    result = session.advance_word(-1)
    assert result is False
    assert session.current_word_index is None


def test_advance_word_with_no_text(session):
    """Test that advance_word with no text set does nothing."""
    session.advance_word(1)
    assert session.current_word_index is None
    session.advance_word(-1)
    assert session.current_word_index is None


def test_reset_clears_state(session):
    """Test that reset clears all state."""
    session.session_id = "test-session-id"
    session.current_session_item_id = "test-session-item-id"
    session.queue = ["queued-item-1", "queued-item-2"]
    session.words = ["один", "два"]
    session.current_word_index = 1
    session.reset()
    assert session.session_id is None
    assert session.current_session_item_id is None
    assert session.queue == []
    assert session.words == []
    assert session.current_word_index is None
