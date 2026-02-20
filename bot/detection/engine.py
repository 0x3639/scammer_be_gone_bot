"""SimilarityEngine — orchestrates all detection layers and computes composite scores."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum

from bot.config import AdminConfig, DetectionConfig
from bot.detection.fuzzy import FuzzyScores, fuzzy_compare
from bot.detection.homoglyphs import homoglyph_score
from bot.detection.normalizer import canonical_match, canonicalize

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    NONE = "none"
    LOW = "low"          # 0.60–0.74: log only
    MEDIUM = "medium"    # 0.75–0.89: alert
    HIGH = "high"        # 0.90+: alert


@dataclass
class DetectionResult:
    flagged: bool
    alert_level: AlertLevel
    composite_score: float
    canonical_score: float
    homoglyph_score: float
    fuzzy_scores: FuzzyScores
    display_name_score: float
    matched_admin: AdminConfig | None
    details: list[str] = field(default_factory=list)


class SimilarityEngine:
    """Orchestrates all detection layers for impersonation checking."""

    def __init__(self, config: DetectionConfig):
        self.config = config

    def check_user(
        self,
        suspect_user_id: int,
        suspect_username: str | None,
        suspect_display_name: str | None,
        admins: list[AdminConfig],
    ) -> DetectionResult:
        """Check a user against all protected admins.

        Returns the worst (highest-scoring) match across all admins.
        """
        worst = DetectionResult(
            flagged=False,
            alert_level=AlertLevel.NONE,
            composite_score=0.0,
            canonical_score=0.0,
            homoglyph_score=0.0,
            fuzzy_scores=FuzzyScores(0.0, 0.0, 0.0, 0.0),
            display_name_score=0.0,
            matched_admin=None,
        )

        for admin in admins:
            # Skip if this IS the admin (match by immutable user_id)
            if suspect_user_id == admin.user_id:
                continue

            result = self._check_against_admin(
                suspect_user_id=suspect_user_id,
                suspect_username=suspect_username or "",
                suspect_display_name=suspect_display_name or "",
                admin=admin,
            )

            if result.composite_score > worst.composite_score:
                worst = result

        return worst

    def _check_against_admin(
        self,
        suspect_user_id: int,
        suspect_username: str,
        suspect_display_name: str,
        admin: AdminConfig,
    ) -> DetectionResult:
        """Check a single user against a single admin."""
        details: list[str] = []

        # Layer 1: Canonical normalization (username)
        canon_score = canonical_match(suspect_username, admin.username)
        if canon_score >= self.config.canonical_threshold:
            s_canon = canonicalize(suspect_username)
            a_canon = canonicalize(admin.username)
            details.append(
                f"canonical match: '{suspect_username}' → '{s_canon}' == '{a_canon}' ← '{admin.username}'"
            )

        # Layer 2: Homoglyph detection (username)
        homo_score = homoglyph_score(suspect_username, admin.username)
        if homo_score >= self.config.homoglyph_threshold:
            details.append(f"homoglyph match: score={homo_score:.2f}")

        # Layer 3: Fuzzy matching (username)
        fuzz_scores = fuzzy_compare(suspect_username, admin.username)
        if fuzz_scores.levenshtein >= self.config.fuzzy_levenshtein_threshold:
            details.append(f"levenshtein: {fuzz_scores.levenshtein:.2f}")
        if fuzz_scores.jaro_winkler >= self.config.fuzzy_jaro_winkler_threshold:
            details.append(f"jaro-winkler: {fuzz_scores.jaro_winkler:.2f}")
        if fuzz_scores.partial_ratio >= self.config.fuzzy_partial_ratio_threshold:
            details.append(f"partial ratio: {fuzz_scores.partial_ratio:.2f}")

        # Layer 4: Display name matching
        dn_score = 0.0
        if suspect_display_name and admin.display_name:
            dn_canon_suspect = canonicalize(suspect_display_name)
            dn_canon_admin = canonicalize(admin.display_name)
            if dn_canon_suspect and dn_canon_admin:
                # Use Levenshtein ratio on canonicalized display names
                from rapidfuzz import fuzz as rf_fuzz

                dn_score = rf_fuzz.ratio(dn_canon_suspect, dn_canon_admin) / 100.0
                if dn_score >= self.config.display_name_threshold:
                    details.append(f"display name match: {dn_score:.2f}")

        # Composite score
        w = self.config.weights
        fuzzy_best = fuzz_scores.best
        composite = (
            w.canonical * canon_score
            + w.homoglyph * homo_score
            + w.fuzzy * fuzzy_best
            + w.display_name * dn_score
        )

        # Determine if flagged — any single layer exceeding threshold OR composite >= threshold
        flagged = False
        if canon_score >= self.config.canonical_threshold:
            flagged = True
        if homo_score >= self.config.homoglyph_threshold:
            flagged = True
        if fuzz_scores.levenshtein >= self.config.fuzzy_levenshtein_threshold:
            flagged = True
        if fuzz_scores.jaro_winkler >= self.config.fuzzy_jaro_winkler_threshold:
            flagged = True
        if fuzz_scores.partial_ratio >= self.config.fuzzy_partial_ratio_threshold:
            flagged = True
        if dn_score >= self.config.display_name_threshold:
            flagged = True
        if composite >= self.config.composite_threshold:
            flagged = True

        # Alert level
        if composite >= 0.90:
            alert_level = AlertLevel.HIGH
        elif composite >= 0.75:
            alert_level = AlertLevel.MEDIUM
        elif composite >= 0.60:
            alert_level = AlertLevel.LOW
        else:
            alert_level = AlertLevel.NONE

        # If flagged by a single-layer threshold but composite is below 0.75,
        # still treat as MEDIUM since a single strong signal is suspicious
        if flagged and alert_level in (AlertLevel.NONE, AlertLevel.LOW):
            alert_level = AlertLevel.MEDIUM

        return DetectionResult(
            flagged=flagged,
            alert_level=alert_level,
            composite_score=composite,
            canonical_score=canon_score,
            homoglyph_score=homo_score,
            fuzzy_scores=fuzz_scores,
            display_name_score=dn_score,
            matched_admin=admin,
            details=details,
        )
