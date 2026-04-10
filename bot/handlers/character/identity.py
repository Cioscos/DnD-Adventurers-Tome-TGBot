"""Identity handler — race and gender editing for a character."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from bot.db.engine import get_session
from bot.db.models import Character
from bot.handlers.character import CHAR_GENDER_INPUT, CHAR_MENU, CHAR_RACE_INPUT
from bot.keyboards.character import build_cancel_keyboard, build_identity_keyboard
from bot.utils.formatting import format_identity
from bot.utils.i18n import get_lang, translator

logger = logging.getLogger(__name__)

_OP_KEY = "char_identity_pending"


async def show_identity_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
) -> int:
    lang = get_lang(update)
    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            return CHAR_MENU

    text = format_identity(char, lang=lang)
    keyboard = build_identity_keyboard(char_id, lang=lang)
    await _edit_or_reply(update, text, keyboard)
    return CHAR_MENU


async def ask_race_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
) -> int:
    lang = get_lang(update)
    context.user_data[_OP_KEY] = {"char_id": char_id, "field": "race"}
    text = translator.t("character.identity.prompt_race", lang=lang)
    await _edit_or_reply(update, text, build_cancel_keyboard(char_id, "char_identity", lang=lang))
    return CHAR_RACE_INPUT


async def handle_race_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    if update.message is None:
        return CHAR_RACE_INPUT

    lang = get_lang(update)
    pending = context.user_data.pop(_OP_KEY, None)
    if pending is None:
        return CHAR_MENU

    char_id: int = pending["char_id"]
    value = update.message.text.strip()[:100]
    if not value:
        await update.message.reply_text(
            translator.t("character.identity.invalid", lang=lang),
            parse_mode="MarkdownV2",
        )
        context.user_data[_OP_KEY] = pending
        return CHAR_RACE_INPUT

    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            return CHAR_MENU
        old = char.race
        char.race = value

    import asyncio as _asyncio
    _asyncio.create_task(_log(char_id, "identity_change", f"Razza: {old or '—'} → {value}"))
    await update.message.reply_text(
        translator.t("character.identity.updated", lang=lang),
        parse_mode="MarkdownV2",
    )
    return await show_identity_menu(update, context, char_id)


async def ask_gender_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
) -> int:
    lang = get_lang(update)
    context.user_data[_OP_KEY] = {"char_id": char_id, "field": "gender"}
    text = translator.t("character.identity.prompt_gender", lang=lang)
    await _edit_or_reply(update, text, build_cancel_keyboard(char_id, "char_identity", lang=lang))
    return CHAR_GENDER_INPUT


async def handle_gender_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    if update.message is None:
        return CHAR_GENDER_INPUT

    lang = get_lang(update)
    pending = context.user_data.pop(_OP_KEY, None)
    if pending is None:
        return CHAR_MENU

    char_id: int = pending["char_id"]
    value = update.message.text.strip()[:50]
    if not value:
        await update.message.reply_text(
            translator.t("character.identity.invalid", lang=lang),
            parse_mode="MarkdownV2",
        )
        context.user_data[_OP_KEY] = pending
        return CHAR_GENDER_INPUT

    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            return CHAR_MENU
        old = char.gender
        char.gender = value

    import asyncio as _asyncio
    _asyncio.create_task(_log(char_id, "identity_change", f"Genere: {old or '—'} → {value}"))
    await update.message.reply_text(
        translator.t("character.identity.updated", lang=lang),
        parse_mode="MarkdownV2",
    )
    return await show_identity_menu(update, context, char_id)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _log(char_id: int, event_type: str, description: str) -> None:
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
