"""Language processing for Russian text."""

from rusyll import rusyll


def sanitize(text: str) -> str:
    """Remove punctuation from text, preserving dashes for compound words."""
    return text.translate(str.maketrans("", "", ".,!?;:\"'"))


def tokenize(text: str) -> list[str]:
    """Split text into words on whitespace."""
    return [w for w in text.split() if w]


def syllabify(word: str) -> list[str]:
    """Split a Russian word into syllables.

    Handles compound words with dashes. Non-Cyrillic words are returned unchanged.

    Parameters
    ----------
    word : str
        The word to syllabify

    Returns
    -------
    list[str]
        List of syllables

    Examples
    --------
    >>> syllabify("молоко")
    ['мо', 'ло', 'ко']
    >>> syllabify("как-нибудь")
    ['как', '-', 'ни', 'будь']
    >>> syllabify("123")
    ['123']

    """
    has_cyrillic = any("\u0400" <= c <= "\u04ff" for c in word)
    if has_cyrillic:
        return rusyll.word_to_syllables_wd(word)
    return [word]
