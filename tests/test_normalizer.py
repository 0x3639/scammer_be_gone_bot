"""Tests for canonical normalization."""

from bot.detection.normalizer import canonical_match, canonicalize


class TestCanonicalize:
    def test_basic_lowercase(self):
        assert canonicalize("SugoiBTC") == "sugoibtc"

    def test_leet_speak_zero_to_o(self):
        assert canonicalize("sug0ibtc") == "sugoibtc"

    def test_leet_speak_one_to_i(self):
        assert canonicalize("sugo1btc") == "sugoibtc"

    def test_leet_speak_three_to_e(self):
        assert canonicalize("sug0ibtc3") == "sugoibtce"

    def test_strips_underscores(self):
        assert canonicalize("sugoi_btc") == "sugoibtc"

    def test_strips_dots(self):
        assert canonicalize("sugoi.btc") == "sugoibtc"

    def test_accented_chars(self):
        assert canonicalize("sügöibtc") == "sugoibtc"

    def test_cyrillic_a(self):
        # Cyrillic а (U+0430) should map to Latin a
        assert canonicalize("sugoibtс") == "sugoibtc"  # с is Cyrillic

    def test_empty_string(self):
        assert canonicalize("") == ""

    def test_o_slash(self):
        assert canonicalize("sugøibtc") == "sugoibtc"

    def test_exclamation_to_i(self):
        assert canonicalize("sugo!btc") == "sugoibtc"

    def test_mixed_substitutions(self):
        # 0→o, 1→i, _→stripped
        assert canonicalize("sug0_1btc") == "sugoibtc"


class TestCanonicalMatch:
    def test_exact_match(self):
        assert canonical_match("sugoibtc", "sugoibtc") == 1.0

    def test_leet_match(self):
        assert canonical_match("sug0ibtc", "sugoibtc") == 1.0

    def test_case_insensitive_match(self):
        assert canonical_match("SugoiBTC", "sugoibtc") == 1.0

    def test_no_match(self):
        assert canonical_match("totallyDifferent", "sugoibtc") == 0.0

    def test_empty_strings(self):
        assert canonical_match("", "sugoibtc") == 0.0
        assert canonical_match("sugoibtc", "") == 0.0
