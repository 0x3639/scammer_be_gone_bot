"""Periodic audit job — re-checks all observed members every N minutes.

Scans the local SQLite database (no Telegram API calls per member).
Catches profile changes or late additions to the protected admin list.
"""

from __future__ import annotations

import logging

from telegram.ext import ContextTypes

from bot.alerts.alerter import Alerter
from bot.config import BotConfig
from bot.detection.bio_checker import BioChecker
from bot.detection.engine import AlertLevel, SimilarityEngine
from bot.persistence.database import Database

logger = logging.getLogger(__name__)


def make_periodic_scan(
    config: BotConfig,
    engine: SimilarityEngine,
    db: Database,
    alerter: Alerter,
    bio_checker: BioChecker,
):
    """Create the periodic scan callback."""

    async def periodic_scan(context: ContextTypes.DEFAULT_TYPE) -> None:
        logger.info("Starting periodic scan of observed members")
        total_checked = 0
        total_flagged = 0

        for group in config.groups:
            members = await db.get_members_by_chat(group.chat_id)
            logger.debug(
                "Scanning %d observed members in group %s (%d)",
                len(members),
                group.name,
                group.chat_id,
            )

            for member in members:
                # Skip admins
                if any(a.user_id == member.user_id for a in group.admins):
                    continue

                # Skip whitelisted
                if await db.is_whitelisted(member.user_id, group.chat_id):
                    continue

                total_checked += 1

                # Bio blacklist check using cached bio
                bio_result = bio_checker.check_bio(member.bio)
                if bio_result.matched:
                    total_flagged += 1
                    logger.warning(
                        "Bio blacklist match for user %d (@%s) in periodic scan — term %r",
                        member.user_id,
                        member.username,
                        bio_result.matched_term,
                    )
                    try:
                        await context.bot.ban_chat_member(group.chat_id, member.user_id)
                    except Exception as exc:
                        logger.error("Failed to ban user %d: %s", member.user_id, exc)
                    continue

                display_name = member.display_name

                result = engine.check_user(
                    suspect_user_id=member.user_id,
                    suspect_username=member.username,
                    suspect_display_name=display_name,
                    admins=group.admins,
                )

                if result.flagged and result.alert_level in (AlertLevel.MEDIUM, AlertLevel.HIGH):
                    total_flagged += 1
                    await alerter.maybe_alert(
                        chat_id=group.chat_id,
                        suspect_user_id=member.user_id,
                        suspect_username=member.username,
                        suspect_display_name=display_name,
                        result=result,
                    )

        logger.info(
            "Periodic scan complete: %d members checked, %d flagged",
            total_checked,
            total_flagged,
        )

    return periodic_scan
