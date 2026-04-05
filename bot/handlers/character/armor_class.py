"""Armor Class management handler."""

from __future__ import annotations

import asyncio
import logging

from telegram import Update
from telegram.ext import ContextTypes

from bot.db.engine import get_session
from bot.db.models import Character
from bot.handlers.character import CHAR_AC_MENU, CHAR_AC_SET_BASE, CHAR_AC_SET_SHIELD, CHAR_AC_SET_MAGIC, CHAR_MENU
from bot.keyboards.character import build_ac_keyboard, build_cancel_keyboard
from bot.utils.formatting import format_ac
from bot.utils.i18n import get_lang, translator

logger = logging.getLogger(__name__)

_OP_KEY = "char_ac_pending_op"


async def show_ac_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int
) -> int:
    lang = get_lang(update)
    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            return CHAR_MENU

    keyboard = build_ac_keyboard(char_id, lang=lang)
    text = format_ac(char, lang=lang)
    await _edit_or_reply(update, text, keyboard)
    return CHAR_AC_MENU


async def ask_ac_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    ac_type: str,
) -> int:
    lang = get_lang(update)
    context.user_data[_OP_KEY] = {"char_id": char_id, "type": ac_type}
    prompts = {
        "set_base":   translator.t("character.ac.prompt_base", lang=lang),
        "set_shield": translator.t("character.ac.prompt_shield", lang=lang),
        "set_magic":  translator.t("character.ac.prompt_magic", lang=lang),
    }
    await _edit_or_reply(update, prompts.get(ac_type, translator.t("character.ac.prompt_base", lang=lang)), build_cancel_keyboard(char_id, "char_ac", lang=lang))
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

    lang = get_lang(update)
    pending = context.user_data.pop(_OP_KEY, None)
    if pending is None:
        return CHAR_AC_MENU

    char_id: int = pending["char_id"]
    ac_type: str = pending["type"]

    try:
        value = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text(
            translator.t("character.common.invalid_number", lang=lang), parse_mode="MarkdownV2"
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

    await update.message.reply_text(translator.t("character.ac.updated", lang=lang), parse_mode="MarkdownV2")
    asyncio.create_task(_trigger_party_update(char_id, context))
    return await show_ac_menu(update, context, char_id)


# ---------------------------------------------------------------------------

async def _trigger_party_update(char_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fire-and-forget wrapper that calls maybe_update_party_message."""
    try:
        from bot.handlers.party import maybe_update_party_message
        await maybe_update_party_message(char_id, context.bot)
    except Exception as e:
        logger.warning("Party update trigger failed for char %s: %s", char_id, e)


async def _edit_or_reply(update: Update, text: str, keyboard=None) -> None:
    kwargs = dict(text=text, parse_mode="MarkdownV2")
    if keyboard:
        kwargs["reply_markup"] = keyboard
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(**kwargs)
    elif update.message:
        await update.message.reply_text(**kwargs)
