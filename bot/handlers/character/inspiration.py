"""Heroic Inspiration handler.

Allows toggling the D&D 5e 2024 Heroic Inspiration token on a character.
The token is a simple boolean: the character either has it or they don't.
"""

from __future__ import annotations

import asyncio
import logging

from telegram import Update
from telegram.ext import ContextTypes

from bot.db.engine import get_session
from bot.db.models import Character
from bot.handlers.character import CHAR_INSPIRATION_MENU, CHAR_MENU
from bot.keyboards.character import build_inspiration_keyboard
from bot.utils.formatting import format_inspiration
from bot.utils.i18n import get_lang, translator

logger = logging.getLogger(__name__)


async def show_inspiration_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int
) -> int:
    """Display the Heroic Inspiration screen."""
    lang = get_lang(update)
    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            return CHAR_MENU

    text = format_inspiration(char, lang=lang)
    keyboard = build_inspiration_keyboard(char_id, char.heroic_inspiration, lang=lang)
    await _edit_or_reply(update, text, keyboard)
    return CHAR_INSPIRATION_MENU


async def toggle_heroic_inspiration(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int
) -> int:
    """Grant or spend the Heroic Inspiration token."""
    lang = get_lang(update)
    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            return CHAR_MENU
        char.heroic_inspiration = not char.heroic_inspiration
        new_state = char.heroic_inspiration

    if new_state:
        toast = translator.t("character.inspiration.granted", lang=lang)
        desc = "Ispirazione Eroica ottenuta"
    else:
        toast = translator.t("character.inspiration.spent", lang=lang)
        desc = "Ispirazione Eroica usata"

    if update.callback_query:
        await update.callback_query.answer(toast)

    asyncio.create_task(_log(char_id, "inspiration_change", desc))
    return await show_inspiration_menu(update, context, char_id)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _log(char_id: int, event_type: str, description: str) -> None:
    """Fire-and-forget wrapper for history logging."""
    try:
        from bot.db.history import log_history_event
        await log_history_event(char_id, event_type, description)
    except Exception as exc:
        logger.warning("History log failed for char %s: %s", char_id, exc)


async def _edit_or_reply(update: Update, text: str, keyboard=None) -> None:
    kwargs = dict(text=text, parse_mode="MarkdownV2")
    if keyboard:
        kwargs["reply_markup"] = keyboard
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(**kwargs)
    elif update.message:
        await update.message.reply_text(**kwargs)
