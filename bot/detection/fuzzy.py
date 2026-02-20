"""Fuzzy string matching using rapidfuzz.

Provides Levenshtein ratio, Jaro-Winkler similarity, and partial ratio.
All comparisons run on canonicalized forms for best results.
"""

from __future__ import annotations

from dataclasses import dataclass

from rapidfuzz import fuzz
from rapidfuzz.distance import JaroWinkler

from bot.detection.normalizer import canonicalize


@dataclass
class FuzzyScores:
    levenshtein: float
    jaro_winkler: float
    partial_ratio: float
    best: float


def fuzzy_compare(suspect: str, admin: str) -> FuzzyScores:
    """Run all fuzzy comparisons on canonicalized strings.

    Returns scores normalized to 0.0–1.0.
    """
    s = canonicalize(suspect)
    a = canonicalize(admin)

    if not s or not a:
        return FuzzyScores(0.0, 0.0, 0.0, 0.0)

    levenshtein = fuzz.ratio(s, a) / 100.0
    jaro_winkler = JaroWinkler.similarity(s, a)
    partial = fuzz.partial_ratio(s, a) / 100.0

    return FuzzyScores(
        levenshtein=levenshtein,
        jaro_winkler=jaro_winkler,
        partial_ratio=partial,
        best=max(levenshtein, jaro_winkler, partial),
    )
