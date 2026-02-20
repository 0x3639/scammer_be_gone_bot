"""Alert formatting and cooldown logic."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from telegram import Bot

from bot.config import AlertConfig
from bot.detection.engine import DetectionResult
from bot.persistence.database import Database
from bot.persistence.models import AlertRecord

logger = logging.getLogger(__name__)


def format_alert(
    suspect_username: str | None,
    suspect_display_name: str,
    suspect_user_id: int,
    result: DetectionResult,
) -> str:
    """Format the public warning message."""
    admin = result.matched_admin
    if admin is None:
        return ""

    suspect_tag = f"@{suspect_username}" if suspect_username else f"user#{suspect_user_id}"
    admin_tag = f"@{admin.username}"
    score_pct = int(result.composite_score * 100)

    details_str = ", ".join(result.details) if result.details else "multiple signals"

    return (
        "\u26a0\ufe0f IMPERSONATOR ALERT \u26a0\ufe0f\n"
        "\n"
        f"User may be impersonating a known community member.\n"
        "\n"
        f"Suspect: {suspect_tag} (\"{suspect_display_name}\")\n"
        f"Real Member: {admin_tag} (\"{admin.display_name}\")\n"
        "\n"
        f"Similarity: {score_pct}% | Detected: {details_str}\n"
        "\n"
        "\U0001f534 Do NOT send this user funds, keys, or personal info.\n"
        "\U0001f534 Trusted members will NEVER DM you first asking for money.\n"
        "\n"
        "Admins \u2014 please review this account."
    )


class Alerter:
    """Handles sending alerts with cooldown and rate limiting."""

    def __init__(self, bot: Bot, db: Database, config: AlertConfig):
        self._bot = bot
        self._db = db
        self._config = config
        self._cooldowns: dict[tuple[int, int], datetime] = {}  # (user_id, chat_id) → last alert time

    async def maybe_alert(
        self,
        chat_id: int,
        suspect_user_id: int,
        suspect_username: str | None,
        suspect_display_name: str,
        result: DetectionResult,
    ) -> bool:
        """Send an alert if not in cooldown. Returns True if alert was sent."""
        if not result.flagged or result.matched_admin is None:
            return False

        # Check cooldown
        if self._is_in_cooldown(suspect_user_id, chat_id):
            logger.debug(
                "Alert suppressed (cooldown) for user %d in chat %d",
                suspect_user_id,
                chat_id,
            )
            return False

        # Format and send
        message = format_alert(
            suspect_username=suspect_username,
            suspect_display_name=suspect_display_name,
            suspect_user_id=suspect_user_id,
            result=result,
        )

        try:
            await asyncio.sleep(self._config.send_delay_seconds)
            await self._bot.send_message(chat_id=chat_id, text=message)
            logger.info(
                "Alert sent for user %d (@%s) in chat %d — score %.2f",
                suspect_user_id,
                suspect_username,
                chat_id,
                result.composite_score,
            )
        except Exception:
            logger.exception("Failed to send alert for user %d in chat %d", suspect_user_id, chat_id)
            return False

        # Record cooldown and persist alert
        now = datetime.now(timezone.utc)
        self._cooldowns[(suspect_user_id, chat_id)] = now

        details_str = "; ".join(result.details) if result.details else "composite"
        await self._db.record_alert(
            AlertRecord(
                id=None,
                user_id=suspect_user_id,
                chat_id=chat_id,
                admin_username=result.matched_admin.username,
                similarity_score=result.composite_score,
                detection_details=details_str,
                alerted_at=now,
            )
        )
        return True

    def _is_in_cooldown(self, user_id: int, chat_id: int) -> bool:
        key = (user_id, chat_id)
        last = self._cooldowns.get(key)
        if last is None:
            return False
        elapsed = (datetime.now(timezone.utc) - last).total_seconds()
        return elapsed < self._config.cooldown_seconds
