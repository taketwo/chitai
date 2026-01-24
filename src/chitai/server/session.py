"""Session state management."""

import logging
from dataclasses import dataclass, field

from chitai.language import sanitize, syllabify, tokenize

logger = logging.getLogger(__name__)


@dataclass
class SessionState:
    """In-memory state for a reading session.

    Holds the current session data including which text is displayed and which word is
    highlighted. Can represent both active sessions (session_id present) and inactive
    state (session_id is None).

    Attributes
    ----------
    session_id : str | None
        Database session ID. None when no session is active.
    current_session_item_id : str | None
        ID of the SessionItem currently being displayed. None when no item is displayed.
    queue : list[str]
        SessionItem IDs waiting to be displayed. Empty when no items are queued.
    words : list[str]
        Words from the current text. Empty when no text is set.
    current_word_index : int
        Index of the currently highlighted word (0-based).

    """

    session_id: str | None = None
    current_session_item_id: str | None = None
    queue: list[str] = field(default_factory=list)
    words: list[str] = field(default_factory=list)
    current_word_index: int = 0

    @property
    def syllables(self) -> list[list[str]]:
        """Syllabified version of current words.

        Returns
        -------
        list[list[str]]
            List of syllable lists, one per word

        """
        return [syllabify(word) for word in self.words]

    def set_text(self, text: str) -> None:
        """Set the current text for display.

        Sanitizes and tokenizes text into words, resets the word index to 0.

        Parameters
        ----------
        text : str
            The text to display

        """
        self.words = tokenize(sanitize(text))
        self.current_word_index = 0
        logger.info("Text updated: %d words", len(self.words))

    def advance_word(self, delta: int) -> bool:
        """Move to a different word by a given offset (with clamping).

        Parameters
        ----------
        delta : int
            Number of words to advance (positive) or go back (negative)

        Returns
        -------
        bool
            True if word index changed, False otherwise

        """
        if not self.words:
            logger.warning("Cannot advance word: no text set")
            return False

        if delta == 0:
            logger.debug("Delta is 0: no change to word index")
            return False

        new_index = max(0, min(self.current_word_index + delta, len(self.words) - 1))

        if new_index != self.current_word_index:
            self.current_word_index = new_index
            logger.info("Word index: %d/%d", new_index + 1, len(self.words))
            return True
        logger.debug("Word index unchanged: already at boundary")
        return False

    def reset(self) -> None:
        """Reset all session state to initial values."""
        self.session_id = None
        self.current_session_item_id = None
        self.queue.clear()
        self.words.clear()
        self.current_word_index = 0
