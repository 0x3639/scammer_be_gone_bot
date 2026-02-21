"""Entry point — Application setup, handler registration, and startup."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from telegram.error import Conflict
from telegram.ext import (
    Application,
    ChatMemberHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot.alerts.alerter import Alerter
from bot.config import BotConfig, load_config
from bot.detection.bio_checker import BioChecker
from bot.detection.engine import SimilarityEngine
from bot.handlers.member_handler import make_member_handler
from bot.handlers.message_handler import make_message_handler
from bot.jobs.periodic_scan import make_periodic_scan
from bot.persistence.database import Database

logger = logging.getLogger(__name__)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors — suppress transient 409 conflicts, log others."""
    if isinstance(context.error, Conflict):
        logger.warning("Polling conflict (409) — transient, will retry automatically")
        return
    logger.error("Unhandled exception: %s", context.error, exc_info=context.error)


async def post_init(application: Application) -> None:
    """Initialize database after the application starts."""
    db: Database = application.bot_data["db"]
    await db.initialize()
    logger.info("Database initialized")


async def post_shutdown(application: Application) -> None:
    """Clean up database connection on shutdown."""
    db: Database = application.bot_data["db"]
    await db.close()
    logger.info("Database closed")


def build_application(config: BotConfig) -> Application:
    """Build and configure the Telegram bot application."""
    # Core components
    db = Database()
    engine = SimilarityEngine(config.detection)
    bio_checker = BioChecker()

    # Build the application
    app = (
        Application.builder()
        .token(config.bot_token)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # Store shared state
    app.bot_data["db"] = db
    app.bot_data["config"] = config
    app.bot_data["engine"] = engine

    # Create alerter (needs bot reference)
    alerter = Alerter(bot=app.bot, db=db, config=config.alerts)
    app.bot_data["alerter"] = alerter

    # --- Register handlers ---

    # Admin commands (imported lazily to avoid circular deps)
    from bot.handlers.admin_commands import (
        check_command,
        protect_command,
        status_command,
        unprotect_command,
        whitelist_command,
    )

    app.add_handler(CommandHandler("protect", protect_command))
    app.add_handler(CommandHandler("unprotect", unprotect_command))
    app.add_handler(CommandHandler("whitelist", whitelist_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("check", check_command))

    # Chat member updates (join/leave)
    member_cb = make_member_handler(config, engine, db, alerter, bio_checker)
    app.add_handler(ChatMemberHandler(member_cb, ChatMemberHandler.CHAT_MEMBER))

    # Message handler — process all non-command text messages in groups
    message_cb = make_message_handler(config, engine, db, alerter, bio_checker)
    monitored_chat_ids = [g.chat_id for g in config.groups]
    app.add_handler(
        MessageHandler(
            filters.Chat(monitored_chat_ids) & ~filters.COMMAND & filters.ALL,
            message_cb,
        )
    )

    # Error handler
    app.add_error_handler(error_handler)

    # --- Periodic scan job ---
    scan_cb = make_periodic_scan(config, engine, db, alerter, bio_checker)
    app.job_queue.run_repeating(
        scan_cb,
        interval=config.periodic_scan_interval,
        first=config.periodic_scan_interval,
        name="periodic_scan",
    )

    return app


def main() -> None:
    """Load config and start the bot."""
    config_path = Path("config.yaml")
    if not config_path.exists():
        print("ERROR: config.yaml not found in current directory", file=sys.stderr)
        sys.exit(1)

    config = load_config(config_path)

    # Configure logging
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=getattr(logging, config.log_level.upper(), logging.INFO),
    )

    if not config.bot_token:
        logger.error("BOT_TOKEN not set in environment — check your .env file")
        sys.exit(1)

    logger.info("Starting Scammer Be Gone bot")
    logger.info("Monitoring %d group(s)", len(config.groups))

    app = build_application(config)

    # Run with allowed updates for messages and chat member events
    app.run_polling(
        allowed_updates=["message", "chat_member", "my_chat_member"],
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
