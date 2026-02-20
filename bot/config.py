"""Configuration loader — reads config.yaml + .env for secrets."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv


@dataclass(frozen=True)
class AdminConfig:
    user_id: int
    username: str
    display_name: str


@dataclass(frozen=True)
class GroupConfig:
    chat_id: int
    name: str
    admins: list[AdminConfig]


@dataclass(frozen=True)
class DetectionWeights:
    canonical: float = 0.35
    homoglyph: float = 0.30
    fuzzy: float = 0.25
    display_name: float = 0.10


@dataclass(frozen=True)
class DetectionConfig:
    canonical_threshold: float = 1.0
    homoglyph_threshold: float = 0.85
    fuzzy_levenshtein_threshold: float = 0.80
    fuzzy_jaro_winkler_threshold: float = 0.85
    fuzzy_partial_ratio_threshold: float = 0.90
    display_name_threshold: float = 0.95
    composite_threshold: float = 0.75
    weights: DetectionWeights = field(default_factory=DetectionWeights)


@dataclass(frozen=True)
class AlertConfig:
    cooldown_seconds: int = 3600
    send_delay_seconds: int = 2


@dataclass(frozen=True)
class BotConfig:
    bot_token: str
    log_level: str
    groups: list[GroupConfig]
    detection: DetectionConfig
    alerts: AlertConfig
    periodic_scan_interval: int = 300


def load_config(config_path: str | Path = "config.yaml") -> BotConfig:
    """Load configuration from YAML file and environment variables."""
    load_dotenv()

    bot_token = os.environ.get("BOT_TOKEN", "")
    log_level = os.environ.get("LOG_LEVEL", "INFO")

    config_path = Path(config_path)
    with open(config_path) as f:
        raw = yaml.safe_load(f)

    groups = []
    for g in raw.get("monitored_groups", []):
        admins = [
            AdminConfig(
                user_id=a["user_id"],
                username=a["username"],
                display_name=a["display_name"],
            )
            for a in g.get("admins", [])
        ]
        groups.append(GroupConfig(chat_id=g["chat_id"], name=g["name"], admins=admins))

    det_raw = raw.get("detection", {})
    weights_raw = det_raw.get("weights", {})
    weights = DetectionWeights(
        canonical=weights_raw.get("canonical", 0.35),
        homoglyph=weights_raw.get("homoglyph", 0.30),
        fuzzy=weights_raw.get("fuzzy", 0.25),
        display_name=weights_raw.get("display_name", 0.10),
    )
    detection = DetectionConfig(
        canonical_threshold=det_raw.get("canonical_threshold", 1.0),
        homoglyph_threshold=det_raw.get("homoglyph_threshold", 0.85),
        fuzzy_levenshtein_threshold=det_raw.get("fuzzy_levenshtein_threshold", 0.80),
        fuzzy_jaro_winkler_threshold=det_raw.get("fuzzy_jaro_winkler_threshold", 0.85),
        fuzzy_partial_ratio_threshold=det_raw.get("fuzzy_partial_ratio_threshold", 0.90),
        display_name_threshold=det_raw.get("display_name_threshold", 0.95),
        composite_threshold=det_raw.get("composite_threshold", 0.75),
        weights=weights,
    )

    alerts_raw = raw.get("alerts", {})
    alerts = AlertConfig(
        cooldown_seconds=alerts_raw.get("cooldown_seconds", 3600),
        send_delay_seconds=alerts_raw.get("send_delay_seconds", 2),
    )

    return BotConfig(
        bot_token=bot_token,
        log_level=log_level,
        groups=groups,
        detection=detection,
        alerts=alerts,
        periodic_scan_interval=raw.get("periodic_scan_interval", 300),
    )
