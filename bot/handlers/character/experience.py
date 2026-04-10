"""Experience points (XP) handler — track XP and suggest level-up."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from bot.data.xp_thresholds import XP_THRESHOLDS, xp_for_next_level, xp_to_level
from bot.db.engine import get_session
from bot.db.models import Character
from bot.handlers.character import CHAR_MENU, CHAR_XP_ADD, CHAR_XP_MENU
from bot.keyboards.character import build_cancel_keyboard, build_xp_keyboard
from bot.utils.formatting import format_experience
from bot.utils.i18n import get_lang, translator

logger = logging.getLogger(__name__)

_OP_KEY = "char_xp_pending"


async def show_xp_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
) -> int:
    lang = get_lang(update)

    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            return CHAR_MENU
        await session.refresh(char, ["classes"])

    text = format_experience(char, lang=lang)
    keyboard = build_xp_keyboard(char_id, char, lang=lang)

    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(
                text=text, reply_markup=keyboard, parse_mode="MarkdownV2"
            )
        except Exception:
            await update.callback_query.message.reply_text(
                text=text, reply_markup=keyboard, parse_mode="MarkdownV2"
            )
    elif update.message:
        await update.message.reply_text(
            text=text, reply_markup=keyboard, parse_mode="MarkdownV2"
        )

    return CHAR_XP_MENU


async def ask_add_xp(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
) -> int:
    lang = get_lang(update)
    context.user_data[_OP_KEY] = {"char_id": char_id}
    text = translator.t("character.xp.prompt_add", lang=lang)
    await _edit_or_reply(update, text, build_cancel_keyboard(char_id, "char_xp", lang=lang))
    return CHAR_XP_ADD


async def handle_xp_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    if update.message is None:
        return CHAR_XP_ADD

    lang = get_lang(update)
    pending = context.user_data.pop(_OP_KEY, None)
    if pending is None:
        return CHAR_MENU

    char_id: int = pending["char_id"]

    try:
        amount = int(update.message.text.strip())
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            translator.t("character.xp.invalid", lang=lang),
            parse_mode="MarkdownV2",
        )
        context.user_data[_OP_KEY] = pending
        return CHAR_XP_ADD

    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            return CHAR_MENU
        await session.refresh(char, ["classes"])

        old_xp = char.experience_points or 0
        old_level_from_xp = xp_to_level(old_xp)
        char.experience_points = old_xp + amount
        new_xp = char.experience_points
        new_level_from_xp = xp_to_level(new_xp)

    import asyncio as _asyncio
    _asyncio.create_task(_log(char_id, "xp_change", f"XP: {old_xp} → {new_xp} (+{amount})"))

    # Notify if level threshold crossed
    actual_level = char.total_level
    if new_level_from_xp > old_level_from_xp and new_level_from_xp > actual_level:
        await update.message.reply_text(
            translator.t(
                "character.xp.level_up_hint",
                lang=lang,
                level=new_level_from_xp,
            ),
            parse_mode="MarkdownV2",
        )

    return await show_xp_menu(update, context, char_id)


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
