"""Bio blacklist checker — bans users with blacklisted terms in their bio."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_BLACKLIST_PATH = Path("bio_blacklist.json")


@dataclass
class BioCheckResult:
    matched: bool
    matched_term: str | None
    matched_field: str | None
    bio_text: str | None


class BioChecker:
    def __init__(self, path: Path = DEFAULT_BLACKLIST_PATH):
        self._path = path
        self._terms: list[str] = []
        self._load()

    def _load(self) -> None:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            terms = data.get("blacklisted_terms", [])
            if not isinstance(terms, list):
                logger.warning("bio blacklist 'blacklisted_terms' is not a list — feature disabled")
                self._terms = []
                return
            self._terms = [t.lower() for t in terms if isinstance(t, str) and t.strip()]
            logger.info("Loaded %d bio blacklist term(s)", len(self._terms))
        except FileNotFoundError:
            logger.warning("Bio blacklist file not found at %s — feature disabled", self._path)
            self._terms = []
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load bio blacklist: %s — feature disabled", exc)
            self._terms = []

    def reload(self) -> None:
        self._load()

    @property
    def term_count(self) -> int:
        return len(self._terms)

    def check_bio(
        self, bio: str | None, channel_title: str | None = None
    ) -> BioCheckResult:
        if not self._terms:
            return BioCheckResult(matched=False, matched_term=None, matched_field=None, bio_text=bio)

        for text, field in ((bio, "bio"), (channel_title, "channel_title")):
            if not text:
                continue
            text_lower = text.lower()
            for term in self._terms:
                if term in text_lower:
                    return BioCheckResult(
                        matched=True, matched_term=term, matched_field=field, bio_text=bio,
                    )

        return BioCheckResult(matched=False, matched_term=None, matched_field=None, bio_text=bio)
