"""Shared test fixtures."""

import pytest

from bot.config import AdminConfig, DetectionConfig, DetectionWeights


@pytest.fixture
def default_detection_config() -> DetectionConfig:
    return DetectionConfig(
        weights=DetectionWeights(),
    )


@pytest.fixture
def sample_admins() -> list[AdminConfig]:
    return [
        AdminConfig(user_id=111, username="sugoibtc", display_name="Sugoi"),
        AdminConfig(user_id=222, username="admin_real", display_name="Admin"),
    ]
