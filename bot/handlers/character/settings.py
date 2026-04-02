"""Character settings handler."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from bot.db.engine import get_session
from bot.db.models import Character
from bot.handlers.character import CHAR_MENU, CHAR_SETTINGS_MENU
from bot.keyboards.character import build_settings_keyboard

logger = logging.getLogger(__name__)


async def show_settings_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int
) -> int:
    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            return CHAR_MENU
        settings = char.settings or {}

    spell_mgmt = settings.get("spell_management", "paginate_by_level")
    spell_label = (
        "Per livello ✅" if spell_mgmt == "paginate_by_level" else "Selezione diretta ✅"
    )

    text = (
        "⚙️ *Impostazioni*\n\n"
        f"Gestione incantesimi: {spell_label}"
    )
    keyboard = build_settings_keyboard(char_id, settings)
    await _edit_or_reply(update, text, keyboard)
    return CHAR_SETTINGS_MENU


async def toggle_spell_management(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int
) -> int:
    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            return CHAR_MENU
        settings = dict(char.settings or {})
        current = settings.get("spell_management", "paginate_by_level")
        settings["spell_management"] = (
            "select_level_directly"
            if current == "paginate_by_level"
            else "paginate_by_level"
        )
        char.settings = settings

    if update.callback_query:
        await update.callback_query.answer("Impostazione aggiornata.")
    return await show_settings_menu(update, context, char_id)


# ---------------------------------------------------------------------------

async def _edit_or_reply(update: Update, text: str, keyboard=None) -> None:
    kwargs = dict(text=text, parse_mode="MarkdownV2")
    if keyboard:
        kwargs["reply_markup"] = keyboard
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(**kwargs)
    elif update.message:
        await update.message.reply_text(**kwargs)
