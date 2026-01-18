"""Unit tests for language processing."""

from chitai.language import sanitize, syllabify, tokenize


def test_sanitize_removes_punctuation():
    """Test that sanitize removes common punctuation."""
    assert sanitize("Молоко, хлеб!") == "Молоко хлеб"
    assert sanitize("Привет? Да.") == "Привет Да"


def test_sanitize_preserves_dashes():
    """Test that sanitize preserves dashes for compound words."""
    assert sanitize("черепаха-гофер") == "черепаха-гофер"


def test_tokenize_splits_words():
    """Test that tokenize splits text into words."""
    assert tokenize("молоко хлеб сыр") == ["молоко", "хлеб", "сыр"]


def test_tokenize_filters_empty():
    """Test that tokenize filters out empty strings."""
    assert tokenize("молоко  хлеб") == ["молоко", "хлеб"]
    assert tokenize("   ") == []


def test_syllabify_multisyllable_word():
    """Test syllabifying a multi-syllable word."""
    assert syllabify("молоко") == ["мо", "ло", "ко"]


def test_syllabify_compound_word():
    """Test syllabifying compound word with dash."""
    result = syllabify("как-нибудь")
    assert result == ["как", "-", "ни", "будь"]


def test_syllabify_non_cyrillic():
    """Test that non-Cyrillic words are returned unchanged."""
    assert syllabify("123") == ["123"]
    assert syllabify("hello") == ["hello"]


def test_syllabify_returns_list():
    """Test that syllabification always returns a list."""
    result = syllabify("хлеб")
    assert isinstance(result, list)
    assert len(result) > 0
    assert all(isinstance(syl, str) for syl in result)
