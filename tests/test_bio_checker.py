"""Tests for the BioChecker module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bot.detection.bio_checker import BioChecker


@pytest.fixture()
def blacklist_file(tmp_path: Path) -> Path:
    path = tmp_path / "bio_blacklist.json"
    data = {"blacklisted_terms": ["18+", "only fans", "crypto pump"]}
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.fixture()
def checker(blacklist_file: Path) -> BioChecker:
    return BioChecker(path=blacklist_file)


class TestBioChecker:
    def test_match_exact(self, checker: BioChecker) -> None:
        result = checker.check_bio("18+")
        assert result.matched is True
        assert result.matched_term == "18+"
        assert result.matched_field == "bio"

    def test_match_substring(self, checker: BioChecker) -> None:
        result = checker.check_bio("hey check my 18+ content")
        assert result.matched is True
        assert result.matched_term == "18+"

    def test_match_case_insensitive(self, checker: BioChecker) -> None:
        result = checker.check_bio("Only Fans link in bio")
        assert result.matched is True
        assert result.matched_term == "only fans"

    def test_match_mixed_case(self, checker: BioChecker) -> None:
        result = checker.check_bio("CRYPTO PUMP group join now")
        assert result.matched is True
        assert result.matched_term == "crypto pump"

    def test_no_match(self, checker: BioChecker) -> None:
        result = checker.check_bio("Just a normal person")
        assert result.matched is False
        assert result.matched_term is None
        assert result.matched_field is None

    def test_none_bio(self, checker: BioChecker) -> None:
        result = checker.check_bio(None)
        assert result.matched is False
        assert result.matched_term is None
        assert result.bio_text is None

    def test_empty_bio(self, checker: BioChecker) -> None:
        result = checker.check_bio("")
        assert result.matched is False
        assert result.matched_term is None

    def test_bio_text_preserved(self, checker: BioChecker) -> None:
        result = checker.check_bio("hello world")
        assert result.bio_text == "hello world"

    def test_term_count(self, checker: BioChecker) -> None:
        assert checker.term_count == 3


class TestChannelTitle:
    def test_match_channel_title(self, checker: BioChecker) -> None:
        result = checker.check_bio(None, channel_title="18+ Secret Place")
        assert result.matched is True
        assert result.matched_term == "18+"
        assert result.matched_field == "channel_title"

    def test_match_channel_title_case_insensitive(self, checker: BioChecker) -> None:
        result = checker.check_bio(None, channel_title="ONLY FANS Premium")
        assert result.matched is True
        assert result.matched_term == "only fans"
        assert result.matched_field == "channel_title"

    def test_bio_checked_before_channel(self, checker: BioChecker) -> None:
        result = checker.check_bio("18+ in bio", channel_title="18+ in channel")
        assert result.matched is True
        assert result.matched_field == "bio"

    def test_channel_checked_when_bio_clean(self, checker: BioChecker) -> None:
        result = checker.check_bio("clean bio", channel_title="crypto pump signals")
        assert result.matched is True
        assert result.matched_field == "channel_title"
        assert result.matched_term == "crypto pump"

    def test_no_match_both_clean(self, checker: BioChecker) -> None:
        result = checker.check_bio("clean bio", channel_title="My Cooking Channel")
        assert result.matched is False

    def test_none_channel_title(self, checker: BioChecker) -> None:
        result = checker.check_bio(None, channel_title=None)
        assert result.matched is False


class TestBioCheckerNoTerms:
    def test_missing_file(self, tmp_path: Path) -> None:
        checker = BioChecker(path=tmp_path / "nonexistent.json")
        assert checker.term_count == 0
        result = checker.check_bio("18+")
        assert result.matched is False

    def test_malformed_json(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.json"
        path.write_text("not json at all", encoding="utf-8")
        checker = BioChecker(path=path)
        assert checker.term_count == 0

    def test_wrong_type(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.json"
        path.write_text(json.dumps({"blacklisted_terms": "not a list"}), encoding="utf-8")
        checker = BioChecker(path=path)
        assert checker.term_count == 0

    def test_empty_terms(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.json"
        path.write_text(json.dumps({"blacklisted_terms": []}), encoding="utf-8")
        checker = BioChecker(path=path)
        assert checker.term_count == 0
        result = checker.check_bio("18+")
        assert result.matched is False


class TestBioCheckerReload:
    def test_reload_picks_up_new_terms(self, blacklist_file: Path) -> None:
        checker = BioChecker(path=blacklist_file)
        assert checker.term_count == 3

        # Update the file with a new term
        data = {"blacklisted_terms": ["18+", "only fans", "crypto pump", "scam"]}
        blacklist_file.write_text(json.dumps(data), encoding="utf-8")

        checker.reload()
        assert checker.term_count == 4
        result = checker.check_bio("this is a scam")
        assert result.matched is True
