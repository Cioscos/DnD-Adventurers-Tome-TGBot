"""/start command handler.

Sends a welcome message with the top-level D&D category keyboard.
"""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from bot.keyboards.builder import build_categories_keyboard

logger = logging.getLogger(__name__)

WELCOME_TEXT = (
    "🎲 *Welcome to the D&D 5e Explorer\\!*\n\n"
    "Choose a category below to start browsing the world of "
    "Dungeons \\& Dragons\\."
)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /start command — greet user and show category buttons."""
    if update.message is None:
        return
    keyboard = build_categories_keyboard()
    await update.message.reply_text(
        WELCOME_TEXT,
        reply_markup=keyboard,
        parse_mode="MarkdownV2",
    )
