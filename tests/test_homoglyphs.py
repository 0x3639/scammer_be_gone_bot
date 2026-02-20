"""Tests for homoglyph detection."""

from bot.detection.homoglyphs import has_mixed_scripts, homoglyph_score


class TestHomoglyphScore:
    def test_identical_latin(self):
        assert homoglyph_score("sugoibtc", "sugoibtc") == 1.0

    def test_cyrillic_a_substitution(self):
        # Replace Latin 'a' in 'admin' with Cyrillic 'а' (U+0430)
        score = homoglyph_score("аdmin", "admin")
        assert score >= 0.8

    def test_totally_different(self):
        score = homoglyph_score("xyz123", "sugoibtc")
        assert score < 0.5

    def test_empty_strings(self):
        assert homoglyph_score("", "admin") == 0.0
        assert homoglyph_score("admin", "") == 0.0

    def test_greek_omicron(self):
        # Greek ο (omicron) for Latin o
        score = homoglyph_score("sugοibtc", "sugoibtc")
        assert score >= 0.8


class TestMixedScripts:
    def test_pure_latin(self):
        assert not has_mixed_scripts("sugoibtc")

    def test_mixed_cyrillic_latin(self):
        # Mix Cyrillic а with Latin letters
        assert has_mixed_scripts("аdmin")
