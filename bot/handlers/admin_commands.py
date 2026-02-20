"""Admin commands for managing the bot.

Commands:
    /protect @user DisplayName  — Add user to protected list
    /unprotect @user            — Remove from protected list
    /whitelist @user reason     — Exempt user from detection
    /status                     — Show bot stats
    /check @user                — Manual similarity check
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from telegram import Update
from telegram.ext import ContextTypes

from bot.alerts.alerter import Alerter
from bot.config import AdminConfig, BotConfig, GroupConfig
from bot.detection.engine import SimilarityEngine
from bot.persistence.database import Database
from bot.persistence.models import WhitelistEntry

logger = logging.getLogger(__name__)


def _get_deps(context: ContextTypes.DEFAULT_TYPE):
    """Extract shared dependencies from bot_data."""
    db: Database = context.bot_data["db"]
    config: BotConfig = context.bot_data["config"]
    engine: SimilarityEngine = context.bot_data["engine"]
    alerter: Alerter = context.bot_data["alerter"]
    return db, config, engine, alerter


def _find_group(config: BotConfig, chat_id: int) -> GroupConfig | None:
    return next((g for g in config.groups if g.chat_id == chat_id), None)


async def _is_chat_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if the commanding user is a Telegram admin of this chat."""
    if update.effective_chat is None or update.effective_user is None:
        return False
    try:
        member = await context.bot.get_chat_member(
            update.effective_chat.id, update.effective_user.id
        )
        return member.status in ("administrator", "creator")
    except Exception:
        return False


async def protect_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/protect @username DisplayName — add a user to the protected admin list."""
    if not await _is_chat_admin(update, context):
        await update.effective_message.reply_text("Only chat admins can use this command.")
        return

    db, config, engine, alerter = _get_deps(context)
    chat_id = update.effective_chat.id
    group = _find_group(config, chat_id)

    if group is None:
        await update.effective_message.reply_text("This group is not monitored.")
        return

    args = context.args or []
    if len(args) < 2:
        await update.effective_message.reply_text(
            "Usage: /protect @username DisplayName\n"
            "Example: /protect @sugoibtc Sugoi"
        )
        return

    username = args[0].lstrip("@")
    display_name = " ".join(args[1:])

    # Try to resolve user_id via replied message or lookup
    user_id = 0
    if update.effective_message.reply_to_message and update.effective_message.reply_to_message.from_user:
        replied_user = update.effective_message.reply_to_message.from_user
        if replied_user.username and replied_user.username.lower() == username.lower():
            user_id = replied_user.id

    # Check if already protected
    existing = next(
        (a for a in group.admins if a.username.lower() == username.lower()),
        None,
    )
    if existing:
        await update.effective_message.reply_text(f"@{username} is already protected.")
        return

    new_admin = AdminConfig(user_id=user_id, username=username, display_name=display_name)
    # Mutate the admin list (GroupConfig is frozen, but the list itself is mutable)
    group.admins.append(new_admin)

    await update.effective_message.reply_text(
        f"Added @{username} (\"{display_name}\") to protected list.\n"
        f"User ID: {user_id if user_id else 'unknown (reply to their message to capture it)'}"
    )
    logger.info("Protected admin added: @%s (%s) by user %d", username, display_name, update.effective_user.id)


async def unprotect_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/unprotect @username — remove from protected list."""
    if not await _is_chat_admin(update, context):
        await update.effective_message.reply_text("Only chat admins can use this command.")
        return

    db, config, engine, alerter = _get_deps(context)
    chat_id = update.effective_chat.id
    group = _find_group(config, chat_id)

    if group is None:
        await update.effective_message.reply_text("This group is not monitored.")
        return

    args = context.args or []
    if len(args) < 1:
        await update.effective_message.reply_text("Usage: /unprotect @username")
        return

    username = args[0].lstrip("@")
    original_len = len(group.admins)
    group.admins[:] = [a for a in group.admins if a.username.lower() != username.lower()]

    if len(group.admins) < original_len:
        await update.effective_message.reply_text(f"Removed @{username} from protected list.")
        logger.info("Unprotected admin: @%s by user %d", username, update.effective_user.id)
    else:
        await update.effective_message.reply_text(f"@{username} was not in the protected list.")


async def whitelist_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/whitelist @username reason — exempt user from detection."""
    if not await _is_chat_admin(update, context):
        await update.effective_message.reply_text("Only chat admins can use this command.")
        return

    db, config, engine, alerter = _get_deps(context)
    chat_id = update.effective_chat.id

    args = context.args or []
    if len(args) < 2:
        await update.effective_message.reply_text(
            "Usage: /whitelist @username reason\n"
            "Example: /whitelist @similar_user Legitimate community member"
        )
        return

    username = args[0].lstrip("@")
    reason = " ".join(args[1:])

    # Try to get user_id from reply
    user_id = 0
    if update.effective_message.reply_to_message and update.effective_message.reply_to_message.from_user:
        replied_user = update.effective_message.reply_to_message.from_user
        if replied_user.username and replied_user.username.lower() == username.lower():
            user_id = replied_user.id

    if user_id == 0:
        await update.effective_message.reply_text(
            f"Could not resolve user ID for @{username}. "
            "Reply to one of their messages while using this command."
        )
        return

    entry = WhitelistEntry(
        user_id=user_id,
        chat_id=chat_id,
        username=username,
        reason=reason,
        added_at=datetime.now(timezone.utc),
        added_by=update.effective_user.id,
    )
    await db.add_whitelist(entry)

    await update.effective_message.reply_text(
        f"Whitelisted @{username} (ID: {user_id}).\nReason: {reason}"
    )
    logger.info("Whitelisted: @%s (%d) by user %d — %s", username, user_id, update.effective_user.id, reason)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/status — show bot stats for this group."""
    db, config, engine, alerter = _get_deps(context)
    chat_id = update.effective_chat.id
    group = _find_group(config, chat_id)

    if group is None:
        await update.effective_message.reply_text("This group is not monitored.")
        return

    member_count = await db.get_member_count(chat_id)
    alert_count = await db.get_alert_count(chat_id)
    recent_alerts = await db.get_recent_alerts(chat_id, limit=5)
    whitelist = await db.get_whitelist(chat_id)

    admin_list = ", ".join(f"@{a.username}" for a in group.admins)

    lines = [
        f"Bot Status for {group.name}",
        f"{'─' * 30}",
        f"Protected admins: {admin_list}",
        f"Observed members: {member_count}",
        f"Total alerts sent: {alert_count}",
        f"Whitelisted users: {len(whitelist)}",
        f"Scan interval: {config.periodic_scan_interval}s",
    ]

    if recent_alerts:
        lines.append(f"\nRecent alerts:")
        for a in recent_alerts:
            lines.append(
                f"  • User {a.user_id} vs @{a.admin_username} "
                f"({int(a.similarity_score * 100)}%) — {a.alerted_at.strftime('%Y-%m-%d %H:%M')}"
            )

    await update.effective_message.reply_text("\n".join(lines))


async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/check @username — manually run similarity check with score breakdown."""
    db, config, engine, alerter = _get_deps(context)
    chat_id = update.effective_chat.id
    group = _find_group(config, chat_id)

    if group is None:
        await update.effective_message.reply_text("This group is not monitored.")
        return

    # Get target user from reply or argument
    target_username = None
    target_display_name = ""
    target_user_id = 0

    if update.effective_message.reply_to_message and update.effective_message.reply_to_message.from_user:
        user = update.effective_message.reply_to_message.from_user
        target_username = user.username
        target_display_name = " ".join(p for p in (user.first_name, user.last_name) if p)
        target_user_id = user.id
    elif context.args:
        target_username = context.args[0].lstrip("@")
    else:
        await update.effective_message.reply_text(
            "Usage: /check @username\nOr reply to a user's message with /check"
        )
        return

    result = engine.check_user(
        suspect_user_id=target_user_id,
        suspect_username=target_username,
        suspect_display_name=target_display_name,
        admins=group.admins,
    )

    admin_tag = f"@{result.matched_admin.username}" if result.matched_admin else "none"
    suspect_tag = f"@{target_username}" if target_username else f"user#{target_user_id}"

    lines = [
        f"Similarity Check: {suspect_tag}",
        f"{'─' * 30}",
        f"Matched admin: {admin_tag}",
        f"Flagged: {'YES' if result.flagged else 'No'}",
        f"Alert level: {result.alert_level.value}",
        f"Composite score: {result.composite_score:.2f}",
        "",
        "Score Breakdown:",
        f"  Canonical:    {result.canonical_score:.2f}",
        f"  Homoglyph:    {result.homoglyph_score:.2f}",
        f"  Levenshtein:  {result.fuzzy_scores.levenshtein:.2f}",
        f"  Jaro-Winkler: {result.fuzzy_scores.jaro_winkler:.2f}",
        f"  Partial ratio: {result.fuzzy_scores.partial_ratio:.2f}",
        f"  Display name: {result.display_name_score:.2f}",
    ]

    if result.details:
        lines.append("")
        lines.append("Detection details:")
        for d in result.details:
            lines.append(f"  • {d}")

    await update.effective_message.reply_text("\n".join(lines))
