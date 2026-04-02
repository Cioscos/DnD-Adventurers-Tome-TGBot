"""Character main menu handler."""

from __future__ import annotations

import logging

from sqlalchemy import select
from telegram import Update
from telegram.ext import ContextTypes

from bot.db.engine import get_session
from bot.db.models import Character
from bot.handlers.character import CHAR_MENU
from bot.keyboards.character import build_character_main_menu_keyboard
from bot.utils.formatting import format_character_summary

logger = logging.getLogger(__name__)


async def show_character_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int | None = None,
) -> int:
    """Display the character's main menu."""
    from bot.handlers.character.selection import ACTIVE_CHAR_KEY

    if char_id is None:
        char_id = context.user_data.get(ACTIVE_CHAR_KEY)

    if char_id is None:
        from bot.handlers.character.selection import show_character_selection
        return await show_character_selection(update, context)

    context.user_data[ACTIVE_CHAR_KEY] = char_id

    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            from bot.handlers.character.selection import show_character_selection
            return await show_character_selection(update, context)
        # Load relationships needed for summary
        await session.refresh(char, ["classes", "ability_scores"])

    keyboard = build_character_main_menu_keyboard(char_id)
    text = format_character_summary(char)

    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(
                text=text,
                reply_markup=keyboard,
                parse_mode="MarkdownV2",
            )
        except Exception:
            await update.callback_query.message.reply_text(
                text=text,
                reply_markup=keyboard,
                parse_mode="MarkdownV2",
            )
    elif update.message:
        await update.message.reply_text(
            text=text,
            reply_markup=keyboard,
            parse_mode="MarkdownV2",
        )

    return CHAR_MENU
