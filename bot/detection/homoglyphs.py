"""Homoglyph / confusable character detection.

Uses the confusable_homoglyphs library (Unicode Consortium confusables DB)
to detect mixed-script attacks (e.g., Cyrillic 'а' for Latin 'a').
"""

from __future__ import annotations

from confusable_homoglyphs import confusables

from bot.detection.normalizer import canonicalize


def _normalize_confusables(text: str) -> str:
    """Replace each character with its Latin confusable skeleton where possible."""
    result = []
    for char in text:
        # Get confusable characters for this char
        greedy = confusables.is_confusable(char, greedy=True)
        if greedy:
            # Find the LATIN equivalent if one exists
            latin_char = None
            for entry in greedy:
                for homoglyph in entry.get("homoglyphs", []):
                    if "LATIN" in homoglyph.get("n", ""):
                        latin_char = homoglyph["c"]
                        break
                if latin_char:
                    break
            result.append(latin_char if latin_char else char)
        else:
            result.append(char)
    return "".join(result)


def has_mixed_scripts(text: str) -> bool:
    """Check if text contains characters from multiple Unicode scripts."""
    dangerous = confusables.is_dangerous(text)
    return bool(dangerous)


def homoglyph_score(suspect: str, admin: str) -> float:
    """Compute homoglyph similarity between suspect and admin strings.

    Returns 1.0 if confusable-normalized forms match, otherwise falls
    back to canonical comparison of normalized forms.
    """
    if not suspect or not admin:
        return 0.0

    # Normalize both through confusable detection
    suspect_norm = _normalize_confusables(suspect.lower())
    admin_norm = _normalize_confusables(admin.lower())

    # Canonicalize both (strip accents, apply charmap, strip non-alnum)
    suspect_canon = canonicalize(suspect_norm)
    admin_canon = canonicalize(admin_norm)

    if suspect_canon == admin_canon:
        return 1.0

    # Partial credit: check if the confusable normalization brought them closer
    # by comparing character overlap
    if not suspect_canon or not admin_canon:
        return 0.0

    # Character-level similarity after confusable normalization
    common = sum(1 for a, b in zip(suspect_canon, admin_canon) if a == b)
    max_len = max(len(suspect_canon), len(admin_canon))
    return common / max_len if max_len > 0 else 0.0
