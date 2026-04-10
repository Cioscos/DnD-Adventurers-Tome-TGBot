"""Saving throws handler — proficiency toggles and d20 rolls for the 6 ability saves."""

from __future__ import annotations

import logging
import random

from sqlalchemy import select
from telegram import Update
from telegram.ext import ContextTypes

from bot.db.models import ABILITY_NAMES, AbilityScore, Character
from bot.db.engine import get_session
from bot.handlers.character import CHAR_MENU, CHAR_SAVING_THROWS_MENU
from bot.keyboards.character import build_saving_throw_detail_keyboard, build_saving_throws_keyboard
from bot.utils.formatting import format_saving_throw_detail, format_saving_throws
from bot.utils.i18n import get_lang, translator

logger = logging.getLogger(__name__)


async def show_saving_throws_menu(
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
        scores_result = await session.execute(
            select(AbilityScore).where(AbilityScore.character_id == char_id)
        )
        scores = list(scores_result.scalars().all())

    text = format_saving_throws(char, scores, lang=lang)
    keyboard = build_saving_throws_keyboard(char_id, char, scores, lang=lang)

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

    return CHAR_SAVING_THROWS_MENU


async def show_saving_throw_detail(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    ability_slug: str,
    last_roll: "tuple[int, int] | None" = None,
) -> int:
    lang = get_lang(update)

    if ability_slug not in ABILITY_NAMES:
        return await show_saving_throws_menu(update, context, char_id)

    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            if update.callback_query:
                await update.callback_query.answer()
            return CHAR_MENU
        await session.refresh(char, ["classes"])
        scores_result = await session.execute(
            select(AbilityScore).where(AbilityScore.character_id == char_id)
        )
        scores = list(scores_result.scalars().all())

    score_map = {s.name: s.value for s in scores}
    mod = (score_map.get(ability_slug, 10) - 10) // 2
    is_proficient = bool((char.saving_throws or {}).get(ability_slug, False))
    bonus = mod + (char.proficiency_bonus if is_proficient else 0)

    text = format_saving_throw_detail(ability_slug, char, scores, lang=lang, last_roll=last_roll)
    keyboard = build_saving_throw_detail_keyboard(char_id, ability_slug, is_proficient, bonus, lang=lang)

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

    return CHAR_SAVING_THROWS_MENU


async def toggle_saving_throw_proficiency(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    ability_slug: str,
) -> int:
    lang = get_lang(update)

    if ability_slug not in ABILITY_NAMES:
        if update.callback_query:
            await update.callback_query.answer()
        return await show_saving_throws_menu(update, context, char_id)

    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            if update.callback_query:
                await update.callback_query.answer()
            return CHAR_MENU

        saves: dict = dict(char.saving_throws or {})
        was_proficient = bool(saves.get(ability_slug, False))
        saves[ability_slug] = not was_proficient
        char.saving_throws = saves

    ability_name = translator.t(f"character.saving_throws.names.{ability_slug}", lang=lang)
    state = "✅" if not was_proficient else "❌"
    import asyncio as _asyncio
    _asyncio.create_task(_log(char_id, "saving_throw_change", f"{ability_name} {state}"))

    if update.callback_query:
        await update.callback_query.answer(
            translator.t("character.saving_throws.updated", lang=lang)
        )

    return await show_saving_throw_detail(update, context, char_id, ability_slug)


async def roll_saving_throw(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    ability_slug: str,
) -> int:
    lang = get_lang(update)

    if ability_slug not in ABILITY_NAMES:
        return await show_saving_throws_menu(update, context, char_id)

    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            if update.callback_query:
                await update.callback_query.answer()
            return CHAR_MENU
        await session.refresh(char, ["classes"])
        scores_result = await session.execute(
            select(AbilityScore).where(AbilityScore.character_id == char_id)
        )
        scores = list(scores_result.scalars().all())

    score_map = {s.name: s.value for s in scores}
    mod = (score_map.get(ability_slug, 10) - 10) // 2
    is_proficient = bool((char.saving_throws or {}).get(ability_slug, False))
    bonus = mod + (char.proficiency_bonus if is_proficient else 0)

    die_result = random.randint(1, 20)
    total = die_result + bonus

    ability_name = translator.t(f"character.saving_throws.names.{ability_slug}", lang=lang)
    bonus_str = f"+{bonus}" if bonus >= 0 else str(bonus)
    log_desc = translator.t(
        "character.saving_throws.roll_logged",
        lang=lang,
        ability_name=ability_name,
        die=die_result,
        bonus=bonus_str,
        total=total,
    )
    import asyncio as _asyncio
    _asyncio.create_task(_log(char_id, "dice_roll", log_desc))

    return await show_saving_throw_detail(
        update, context, char_id, ability_slug, last_roll=(die_result, total)
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _log(char_id: int, event_type: str, description: str) -> None:
    try:
        from bot.db.history import log_history_event
        await log_history_event(char_id, event_type, description)
    except Exception as exc:
        logger.warning("History log failed for char %s: %s", char_id, exc)
