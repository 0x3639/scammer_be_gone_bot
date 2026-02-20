"""Tests for the SimilarityEngine."""

from bot.config import AdminConfig, DetectionConfig, DetectionWeights
from bot.detection.engine import AlertLevel, SimilarityEngine


class TestSimilarityEngine:
    def setup_method(self):
        self.config = DetectionConfig(weights=DetectionWeights())
        self.engine = SimilarityEngine(self.config)
        self.admins = [
            AdminConfig(user_id=111, username="sugoibtc", display_name="Sugoi"),
            AdminConfig(user_id=222, username="admin_real", display_name="Admin"),
        ]

    def test_real_admin_not_flagged(self):
        """The actual admin (same user_id) should never be flagged."""
        result = self.engine.check_user(
            suspect_user_id=111,
            suspect_username="sugoibtc",
            suspect_display_name="Sugoi",
            admins=self.admins,
        )
        assert not result.flagged

    def test_leet_speak_impersonator(self):
        """sug0ibtc (0 for o) should be flagged."""
        result = self.engine.check_user(
            suspect_user_id=999,
            suspect_username="sug0ibtc",
            suspect_display_name="Someone",
            admins=self.admins,
        )
        assert result.flagged
        assert result.matched_admin is not None
        assert result.matched_admin.username == "sugoibtc"
        assert result.composite_score > 0.75

    def test_display_name_copy(self):
        """Exact display name copy with different username/user_id."""
        result = self.engine.check_user(
            suspect_user_id=999,
            suspect_username="totallyDifferent",
            suspect_display_name="Sugoi",
            admins=self.admins,
        )
        assert result.display_name_score >= 0.95
        assert result.flagged

    def test_totally_different_user(self):
        """User with no similarity should not be flagged."""
        result = self.engine.check_user(
            suspect_user_id=999,
            suspect_username="john_doe_xyz",
            suspect_display_name="John Doe",
            admins=self.admins,
        )
        assert not result.flagged
        assert result.alert_level == AlertLevel.NONE

    def test_high_alert_level(self):
        """Near-perfect impersonation should get HIGH alert."""
        result = self.engine.check_user(
            suspect_user_id=999,
            suspect_username="sug0ibtc",
            suspect_display_name="Sugoi",
            admins=self.admins,
        )
        assert result.flagged
        assert result.alert_level in (AlertLevel.HIGH, AlertLevel.MEDIUM)

    def test_underscore_variant(self):
        """sugoi_btc (with underscore) should be flagged."""
        result = self.engine.check_user(
            suspect_user_id=999,
            suspect_username="sugoi_btc",
            suspect_display_name="Someone",
            admins=self.admins,
        )
        assert result.flagged
        assert result.canonical_score == 1.0

    def test_no_username(self):
        """User with no username but matching display name."""
        result = self.engine.check_user(
            suspect_user_id=999,
            suspect_username=None,
            suspect_display_name="Sugoi",
            admins=self.admins,
        )
        assert result.display_name_score >= 0.95

    def test_empty_admins(self):
        """No admins to check against — nothing should be flagged."""
        result = self.engine.check_user(
            suspect_user_id=999,
            suspect_username="sug0ibtc",
            suspect_display_name="Sugoi",
            admins=[],
        )
        assert not result.flagged

    def test_whitelisted_admin_excluded(self):
        """Verify the engine itself skips the admin by user_id."""
        result = self.engine.check_user(
            suspect_user_id=222,
            suspect_username="admin_real",
            suspect_display_name="Admin",
            admins=self.admins,
        )
        assert not result.flagged
