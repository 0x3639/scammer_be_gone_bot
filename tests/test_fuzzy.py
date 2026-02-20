"""Tests for fuzzy string matching."""

from bot.detection.fuzzy import fuzzy_compare


class TestFuzzyCompare:
    def test_identical_strings(self):
        scores = fuzzy_compare("sugoibtc", "sugoibtc")
        assert scores.levenshtein == 1.0
        assert scores.jaro_winkler == 1.0
        assert scores.partial_ratio == 1.0
        assert scores.best == 1.0

    def test_one_char_difference(self):
        scores = fuzzy_compare("sugoibtc", "sug0ibtc")
        # After canonicalization, these are identical
        assert scores.levenshtein == 1.0

    def test_similar_strings(self):
        # sugoibtc vs sugoybtc — i→y difference (post-canonicalization)
        scores = fuzzy_compare("sugoibtc", "sugoybtc")
        assert scores.levenshtein > 0.7
        assert scores.jaro_winkler > 0.8

    def test_totally_different(self):
        scores = fuzzy_compare("abcdefgh", "zyxwvuts")
        assert scores.levenshtein < 0.3
        assert scores.best < 0.5

    def test_substring_match(self):
        # partial_ratio should be high when one is substring of the other
        scores = fuzzy_compare("sugoibtc", "sugoibtc_support")
        assert scores.partial_ratio > 0.8

    def test_empty_strings(self):
        scores = fuzzy_compare("", "sugoibtc")
        assert scores.best == 0.0

    def test_close_misspelling(self):
        scores = fuzzy_compare("sugoibtc", "sugibtc")
        assert scores.levenshtein > 0.7
