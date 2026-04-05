"""Dice rolling handler with history tracking."""

from __future__ import annotations

import asyncio
import logging
import random

from telegram import Update
from telegram.ext import ContextTypes

from bot.db.engine import get_session
from bot.db.models import Character
from bot.handlers.character import CHAR_DICE_MENU, CHAR_MENU
from bot.keyboards.character import build_dice_count_keyboard, build_dice_keyboard
from bot.utils.formatting import format_dice_history
from bot.utils.i18n import get_lang, translator

logger = logging.getLogger(__name__)


async def show_dice_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int
) -> int:
    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            return CHAR_MENU
        history = char.rolls_history or []

    lang = get_lang(update)
    keyboard = build_dice_keyboard(char_id)
    history_text = format_dice_history(history, lang=lang)
    text = translator.t("character.dice.title", lang=lang) + "\n\n" + history_text
    await _edit_or_reply(update, text, keyboard)
    return CHAR_DICE_MENU


async def show_dice_count_picker(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int, die: str
) -> int:
    lang = get_lang(update)
    keyboard = build_dice_count_keyboard(char_id, die)
    await _edit_or_reply(update, translator.t("character.dice.prompt_count", lang=lang, die=die), keyboard)
    return CHAR_DICE_MENU


async def roll_dice(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    count: int,
    die: str,
) -> int:
    sides = int(die[1:])
    results = [random.randint(1, sides) for _ in range(count)]
    total = sum(results)

    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            return CHAR_MENU
        history = list(char.rolls_history or [])
        history.append([f"{count}{die}", results])
        # Keep last 50 rolls
        if len(history) > 50:
            history = history[-50:]
        char.rolls_history = history

    result_str = ", ".join(str(r) for r in results)
    lang = get_lang(update)
    text = (
        translator.t("character.dice.results_title", lang=lang, count=count, die=die) + "\n\n"
        + translator.t("character.dice.results_line", lang=lang, results=_esc(result_str)) + "\n"
        + translator.t("character.dice.total_line", lang=lang, total=total)
    )
    if update.callback_query:
        await update.callback_query.answer(f"{count}{die} = {total}")

    asyncio.create_task(_trigger_party_update(char_id, context))
    await _edit_or_reply(update, text)
    return await show_dice_menu(update, context, char_id)


async def clear_dice_history(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int
) -> int:
    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char:
            char.rolls_history = []

    if update.callback_query:
        await update.callback_query.answer("Storico cancellato.")
    return await show_dice_menu(update, context, char_id)


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


def _esc(text: str) -> str:
    special = r"\_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{c}" if c in special else c for c in str(text))
