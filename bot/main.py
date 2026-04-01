"""Entry point for the D&D 5e Telegram Explorer Bot.

Loads configuration from ``.env``, builds the ``Application`` with
``arbitrary_callback_data`` enabled, initialises the
:class:`~bot.schema.registry.SchemaRegistry` via introspection, registers
all handlers, and starts long-polling.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler

from bot.handlers.navigation import navigation_callback
from bot.handlers.start import start_command
from bot.schema.registry import registry

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def post_init(application: Application) -> None:
    """Called after the Application has been fully initialised."""
    await registry.initialize()


def main() -> None:
    """Initialize and run the Telegram bot."""
    load_dotenv()
    token = os.getenv("BOT_TOKEN")
    if not token:
        logger.critical("BOT_TOKEN not set. Create a .env file (see .env.example).")
        sys.exit(1)

    application = (
        Application.builder()
        .token(token)
        .arbitrary_callback_data(True)
        .post_init(post_init)
        .build()
    )

    # Command handlers
    application.add_handler(CommandHandler("start", start_command))

    # Callback-query handler (catches all inline-button presses)
    application.add_handler(CallbackQueryHandler(navigation_callback))

    logger.info("Bot started — polling for updates…")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
