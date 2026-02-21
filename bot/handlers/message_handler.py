"""Real-time message scanning handler.

Intercepts every group message to:
1. Upsert the sender into the observed members database.
2. Run the similarity engine against protected admins.
3. Trigger an alert if impersonation is detected.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from telegram import Update
from telegram.ext import ContextTypes

from bot.alerts.alerter import Alerter
from bot.config import BotConfig
from bot.detection.bio_checker import BioChecker
from bot.detection.engine import AlertLevel, SimilarityEngine
from bot.persistence.database import Database
from bot.persistence.models import ObservedMember

logger = logging.getLogger(__name__)


def make_message_handler(
    config: BotConfig,
    engine: SimilarityEngine,
    db: Database,
    alerter: Alerter,
    bio_checker: BioChecker,
):
    """Create the message handler callback with injected dependencies."""

    async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        if message is None or message.from_user is None:
            return

        user = message.from_user
        chat_id = message.chat_id

        # Find the group config
        group = next((g for g in config.groups if g.chat_id == chat_id), None)
        if group is None:
            return

        logger.info("Message from user %d (@%s) in chat %d", user.id, user.username, chat_id)

        # Upsert observed member
        member = ObservedMember(
            user_id=user.id,
            chat_id=chat_id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            last_seen=datetime.now(timezone.utc),
        )
        await db.upsert_member(member)

        # Skip if user is a protected admin (by user_id)
        if any(a.user_id == user.id for a in group.admins):
            return

        # Skip if whitelisted
        if await db.is_whitelisted(user.id, chat_id):
            return

        # Bio blacklist check
        try:
            chat_info = await context.bot.get_chat(user.id)
            bio = chat_info.bio
        except Exception:
            bio = None
        # Cache bio in DB
        member.bio = bio
        await db.upsert_member(member)
        bio_result = bio_checker.check_bio(bio)
        if bio_result.matched:
            logger.warning(
                "Bio blacklist match for user %d (@%s) in chat %d — term %r found in bio",
                user.id,
                user.username,
                chat_id,
                bio_result.matched_term,
            )
            try:
                await context.bot.ban_chat_member(chat_id, user.id)
            except Exception as exc:
                logger.error("Failed to ban user %d: %s", user.id, exc)
            try:
                await message.delete()
            except Exception as exc:
                logger.error("Failed to delete message from user %d: %s", user.id, exc)
            return

        # Run detection
        display_name = member.display_name
        result = engine.check_user(
            suspect_user_id=user.id,
            suspect_username=user.username,
            suspect_display_name=display_name,
            admins=group.admins,
        )

        if result.flagged and result.alert_level in (AlertLevel.MEDIUM, AlertLevel.HIGH):
            await alerter.maybe_alert(
                chat_id=chat_id,
                suspect_user_id=user.id,
                suspect_username=user.username,
                suspect_display_name=display_name,
                result=result,
            )
        elif result.flagged and result.alert_level == AlertLevel.LOW:
            logger.info(
                "Low-confidence match for user %d (@%s) in chat %d — score %.2f",
                user.id,
                user.username,
                chat_id,
                result.composite_score,
            )

    return handle_message
