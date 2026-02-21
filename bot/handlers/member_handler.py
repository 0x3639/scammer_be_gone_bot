"""ChatMemberUpdated handler — detects join/leave events.

When a new member joins, upserts them into the database and runs
impersonation detection immediately.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from telegram import ChatMemberUpdated, Update
from telegram.ext import ContextTypes

from bot.alerts.alerter import Alerter
from bot.config import BotConfig
from bot.detection.bio_checker import BioChecker
from bot.detection.engine import AlertLevel, SimilarityEngine
from bot.persistence.database import Database
from bot.persistence.models import ObservedMember

logger = logging.getLogger(__name__)

# Statuses that indicate a user is present in the group
_MEMBER_STATUSES = {"member", "administrator", "creator", "restricted"}


def _extract_status_change(update: ChatMemberUpdated) -> tuple[bool, bool]:
    """Return (was_member, is_member) from a ChatMemberUpdated event."""
    old = update.old_chat_member.status if update.old_chat_member else None
    new = update.new_chat_member.status if update.new_chat_member else None
    was_member = old in _MEMBER_STATUSES
    is_member = new in _MEMBER_STATUSES
    return was_member, is_member


def make_member_handler(
    config: BotConfig,
    engine: SimilarityEngine,
    db: Database,
    alerter: Alerter,
    bio_checker: BioChecker,
):
    """Create the chat_member handler callback with injected dependencies."""

    async def handle_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.chat_member is None:
            return

        chat_id = update.chat_member.chat.id
        group = next((g for g in config.groups if g.chat_id == chat_id), None)
        if group is None:
            return

        was_member, is_member = _extract_status_change(update.chat_member)
        user = update.chat_member.new_chat_member.user

        if not was_member and is_member:
            # User joined — upsert and check
            logger.info("User %d (@%s) joined chat %d", user.id, user.username, chat_id)

            member = ObservedMember(
                user_id=user.id,
                chat_id=chat_id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                last_seen=datetime.now(timezone.utc),
            )
            await db.upsert_member(member)

            # Skip if admin or whitelisted
            if any(a.user_id == user.id for a in group.admins):
                return
            if await db.is_whitelisted(user.id, chat_id):
                return

            # Bio blacklist check
            try:
                chat_info = await context.bot.get_chat(user.id)
                bio = chat_info.bio
            except Exception:
                bio = None
            member.bio = bio
            await db.upsert_member(member)
            bio_result = bio_checker.check_bio(bio)
            if bio_result.matched:
                logger.warning(
                    "Bio blacklist match for user %d (@%s) joining chat %d — term %r found in bio",
                    user.id,
                    user.username,
                    chat_id,
                    bio_result.matched_term,
                )
                try:
                    await context.bot.ban_chat_member(chat_id, user.id)
                except Exception as exc:
                    logger.error("Failed to ban user %d: %s", user.id, exc)
                return

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

        elif was_member and not is_member:
            # User left — remove from observed members
            logger.info("User %d left chat %d", user.id, chat_id)
            await db.remove_member(user.id, chat_id)

    return handle_chat_member
