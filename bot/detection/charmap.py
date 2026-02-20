"""Static character substitution maps for normalization.

Maps visually similar characters to their canonical Latin equivalent.
Used before fuzzy matching to catch intentional substitutions like 0→o, 1→i.
"""

# Common leet-speak and lookalike substitutions
CHAR_SUBSTITUTIONS: dict[str, str] = {
    # Digits → letters
    "0": "o",
    "1": "i",
    "3": "e",
    "4": "a",
    "5": "s",
    "6": "g",
    "7": "t",
    "8": "b",
    "9": "g",
    # Special characters → letters
    "!": "i",
    "|": "i",
    "@": "a",
    "$": "s",
    "+": "t",
    # Latin extended / accented → base
    "à": "a",
    "á": "a",
    "â": "a",
    "ã": "a",
    "ä": "a",
    "å": "a",
    "æ": "ae",
    "ç": "c",
    "è": "e",
    "é": "e",
    "ê": "e",
    "ë": "e",
    "ì": "i",
    "í": "i",
    "î": "i",
    "ï": "i",
    "ð": "d",
    "ñ": "n",
    "ò": "o",
    "ó": "o",
    "ô": "o",
    "õ": "o",
    "ö": "o",
    "ø": "o",
    "ù": "u",
    "ú": "u",
    "û": "u",
    "ü": "u",
    "ý": "y",
    "ÿ": "y",
    "ß": "ss",
    # Common Cyrillic lookalikes
    "а": "a",  # Cyrillic а
    "с": "c",  # Cyrillic с
    "е": "e",  # Cyrillic е
    "о": "o",  # Cyrillic о
    "р": "p",  # Cyrillic р
    "х": "x",  # Cyrillic х
    "у": "y",  # Cyrillic у
    "і": "i",  # Ukrainian і
    # Greek lookalikes
    "ο": "o",  # Greek omicron
    "α": "a",  # Greek alpha
    "ε": "e",  # Greek epsilon
    "ι": "i",  # Greek iota
    "κ": "k",  # Greek kappa
    "ν": "v",  # Greek nu
    "τ": "t",  # Greek tau
    # Misc lookalikes
    "ℓ": "l",
    "ⅰ": "i",
    "ⅱ": "ii",
    "ℹ": "i",
    "ⓘ": "i",
    "ⓞ": "o",
}


def apply_substitutions(text: str) -> str:
    """Apply character substitution map to text, returning normalized form."""
    result = []
    for ch in text:
        replacement = CHAR_SUBSTITUTIONS.get(ch)
        if replacement is not None:
            result.append(replacement)
        else:
            result.append(ch)
    return "".join(result)
