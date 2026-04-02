"""Armor Class management handler."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from bot.db.engine import get_session
from bot.db.models import Character
from bot.handlers.character import CHAR_AC_MENU, CHAR_AC_SET_BASE, CHAR_AC_SET_SHIELD, CHAR_AC_SET_MAGIC, CHAR_MENU
from bot.keyboards.character import build_ac_keyboard
from bot.utils.formatting import format_ac

logger = logging.getLogger(__name__)

_OP_KEY = "char_ac_pending_op"


async def show_ac_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int
) -> int:
    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            return CHAR_MENU

    keyboard = build_ac_keyboard(char_id)
    text = format_ac(char)
    await _edit_or_reply(update, text, keyboard)
    return CHAR_AC_MENU


async def ask_ac_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    ac_type: str,
) -> int:
    context.user_data[_OP_KEY] = {"char_id": char_id, "type": ac_type}
    prompts = {
        "set_base":   "✏️ Inserisci la *CA base* \\(es\\. 13\\):",
        "set_shield": "✏️ Inserisci il bonus *CA scudo* \\(es\\. 2\\):",
        "set_magic":  "✏️ Inserisci il bonus *CA magica* \\(es\\. 1\\):",
    }
    await _edit_or_reply(update, prompts.get(ac_type, "Inserisci un numero:"))
    state_map = {
        "set_base":   CHAR_AC_SET_BASE,
        "set_shield": CHAR_AC_SET_SHIELD,
        "set_magic":  CHAR_AC_SET_MAGIC,
    }
    return state_map.get(ac_type, CHAR_AC_MENU)


async def handle_ac_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    if update.message is None:
        return CHAR_AC_MENU

    pending = context.user_data.pop(_OP_KEY, None)
    if pending is None:
        return CHAR_AC_MENU

    char_id: int = pending["char_id"]
    ac_type: str = pending["type"]

    try:
        value = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text(
            "❌ Valore non valido\\.", parse_mode="MarkdownV2"
        )
        context.user_data[_OP_KEY] = pending
        return CHAR_AC_SET_BASE

    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            return CHAR_MENU
        if ac_type == "set_base":
            char.base_armor_class = max(0, value)
        elif ac_type == "set_shield":
            char.shield_armor_class = max(0, value)
        elif ac_type == "set_magic":
            char.magic_armor = max(0, value)

    await update.message.reply_text("✅ CA aggiornata\\!", parse_mode="MarkdownV2")
    return await show_ac_menu(update, context, char_id)


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
