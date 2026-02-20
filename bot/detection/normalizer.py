"""Unicode normalization and canonical form generation.

Produces a canonical representation of a username/display name by:
1. NFKD normalization
2. Stripping combining marks (accents)
3. Lowercasing
4. Applying character substitution map
5. Stripping non-alphanumeric characters
"""

from __future__ import annotations

import re
import unicodedata

from bot.detection.charmap import apply_substitutions

_NON_ALNUM = re.compile(r"[^a-z0-9]")


def _strip_combining_marks(text: str) -> str:
    """Remove Unicode combining marks (category 'M') after NFKD decomposition."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if unicodedata.category(ch)[0] != "M")


def canonicalize(text: str) -> str:
    """Produce canonical form for similarity comparison.

    Steps:
        1. NFKD normalize
        2. Strip combining marks (accents, diacritics)
        3. Lowercase
        4. Apply character substitution map (leet-speak, Cyrillic, etc.)
        5. Strip non-alphanumeric characters
    """
    if not text:
        return ""
    text = _strip_combining_marks(text)
    text = text.lower()
    text = apply_substitutions(text)
    text = _NON_ALNUM.sub("", text)
    return text


def canonical_match(suspect: str, admin: str) -> float:
    """Return 1.0 if canonical forms are identical, else 0.0."""
    if not suspect or not admin:
        return 0.0
    return 1.0 if canonicalize(suspect) == canonicalize(admin) else 0.0
