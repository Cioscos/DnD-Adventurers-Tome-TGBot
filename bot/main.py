"""Entry point for the D&D 5e Telegram Bot.

Loads configuration from ``.env``, builds the ``Application`` with
``arbitrary_callback_data`` enabled, initialises the
:class:`~bot.schema.registry.SchemaRegistry` via introspection,
initialises the SQLite database, registers all handlers, and starts
long-polling.
"""

from __future__ import annotations

import asyncio
import html
import json
import logging
import logging.handlers
import os
import sys
import traceback
from pathlib import Path
from warnings import filterwarnings

from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes
from telegram.warnings import PTBUserWarning

from bot.db.engine import init_db
from bot.handlers.character.conversation import build_character_conversation_handler
from bot.handlers.navigation import navigation_callback
from bot.handlers.start import start_command
from bot.models.character_state import CharAction
from bot.schema.registry import registry

# ---------------------------------------------------------------------------
# Logging — console + rotating file, httpx silenced at INFO level
# ---------------------------------------------------------------------------
_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
_LOG_DIR = Path("logs")
_LOG_DIR.mkdir(exist_ok=True)

_console_handler = logging.StreamHandler()
_console_handler.setFormatter(logging.Formatter(_LOG_FORMAT))

_file_handler = logging.handlers.RotatingFileHandler(
    _LOG_DIR / "dnd_bot.log",
    mode="a",
    maxBytes=5 * 1024 * 1024,  # 5 MB
    backupCount=3,
    encoding="utf-8",
)
_file_handler.setFormatter(logging.Formatter(_LOG_FORMAT))

logging.basicConfig(level=logging.INFO, handlers=[_console_handler, _file_handler])

# Suppress noisy per-request INFO logs from httpx (Telegram API calls)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

filterwarnings(action="ignore", message=r".*CallbackQueryHandler", category=PTBUserWarning)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log exceptions and notify the developer via Telegram private message.

    The developer chat ID is read from the ``DEV_CHAT_ID`` env variable.
    If the variable is not set the error is only logged locally.
    Each log section is sent as a separate message so that HTML ``<pre>``
    tags are never split across chunk boundaries.
    """
    logger.error("Exception while handling an update:", exc_info=context.error)

    tb_string = "".join(
        traceback.format_exception(None, context.error, context.error.__traceback__)
    )

    dev_chat_id = os.getenv("DEV_CHAT_ID")
    if not dev_chat_id:
        return

    update_str = update.to_dict() if isinstance(update, Update) else str(update)

    _MAX = 4096

    def _pre_section(label: str, content: str) -> str:
        """Wrap *content* in a ``<pre>`` block, truncating to fit in one message."""
        prefix = f"<pre>{label}"
        suffix = "</pre>"
        available = _MAX - len(prefix) - len(suffix)
        if len(content) > available:
            content = content[: available - 20] + "\n…(troncato)"
        return prefix + content + suffix

    sections = [
        "⚠️ <b>Eccezione nel bot</b>",
        _pre_section(
            "update = ",
            html.escape(json.dumps(update_str, indent=2, ensure_ascii=False)),
        ),
        _pre_section("context.chat_data = ", html.escape(str(context.chat_data))),
        _pre_section("context.user_data = ", html.escape(str(context.user_data))),
        _pre_section("", html.escape(tb_string)),
    ]

    for section in sections:
        try:
            await context.bot.send_message(
                chat_id=int(dev_chat_id),
                text=section,
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            logger.exception("Impossibile inviare la notifica di errore allo sviluppatore.")


async def post_init(application: Application) -> None:
    """Called after the Application has been fully initialised."""
    await registry.initialize()
    await init_db()
    logger.info("Database initialised.")


async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /stop outside the character conversation (no active operation)."""
    if update.message:
        await update.message.reply_text(
            "✋ Nessuna operazione in corso da interrompere\\.",
            parse_mode="MarkdownV2",
        )


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
    application.add_handler(CommandHandler("stop", stop_command))

    # Character ConversationHandler (must come before the generic wiki callback)
    application.add_handler(build_character_conversation_handler())

    # Wiki callback-query handler (catches all NavAction inline-button presses)
    application.add_handler(
        CallbackQueryHandler(
            navigation_callback,
            pattern=lambda d: not isinstance(d, CharAction),
        )
    )

    # Global error handler — logs exceptions and notifies the developer
    application.add_error_handler(error_handler)

    logger.info("Bot started — polling for updates…")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
