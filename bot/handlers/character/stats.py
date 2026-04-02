"""Ability scores handler (FOR, DES, COS, INT, SAG, CAR)."""

from __future__ import annotations

import logging

from sqlalchemy import select
from telegram import Update
from telegram.ext import ContextTypes

from bot.db.engine import get_session
from bot.db.models import ABILITY_NAMES, AbilityScore, Character
from bot.handlers.character import CHAR_STATS_MENU, CHAR_STATS_SET, CHAR_MENU
from bot.keyboards.character import build_stats_keyboard
from bot.utils.formatting import format_ability_scores

logger = logging.getLogger(__name__)

_OP_KEY = "char_stats_pending"


async def show_stats_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int
) -> int:
    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            return CHAR_MENU
        result = await session.execute(
            select(AbilityScore).where(AbilityScore.character_id == char_id)
        )
        scores = list(result.scalars().all())

    keyboard = build_stats_keyboard(char_id)
    text = format_ability_scores(scores)
    await _edit_or_reply(update, text, keyboard)
    return CHAR_STATS_MENU


async def ask_stat_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    stat_name: str,
) -> int:
    from bot.utils.formatting import ABILITY_LABELS
    label, emoji = ABILITY_LABELS.get(stat_name, (stat_name, "•"))
    context.user_data[_OP_KEY] = {"char_id": char_id, "stat": stat_name}
    text = f"{emoji} Inserisci il valore per *{label}* \\(1\\-30\\):"
    await _edit_or_reply(update, text)
    return CHAR_STATS_SET


async def handle_stat_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    if update.message is None:
        return CHAR_STATS_MENU

    pending = context.user_data.pop(_OP_KEY, None)
    if pending is None:
        return CHAR_STATS_MENU

    char_id: int = pending["char_id"]
    stat_name: str = pending["stat"]

    try:
        value = int(update.message.text.strip())
        if not 1 <= value <= 30:
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            "❌ Valore non valido\\. Inserisci un numero tra 1 e 30\\.",
            parse_mode="MarkdownV2",
        )
        context.user_data[_OP_KEY] = pending
        return CHAR_STATS_SET

    async with get_session() as session:
        result = await session.execute(
            select(AbilityScore).where(
                AbilityScore.character_id == char_id,
                AbilityScore.name == stat_name,
            )
        )
        score = result.scalar_one_or_none()
        if score is None:
            score = AbilityScore(character_id=char_id, name=stat_name, value=value)
            session.add(score)
        else:
            score.value = value

        # Recalculate carry capacity if strength changed
        if stat_name == "strength":
            char = await session.get(Character, char_id)
            if char:
                char.carry_capacity = value * 15

    await update.message.reply_text("✅ Punteggio aggiornato\\!", parse_mode="MarkdownV2")
    return await show_stats_menu(update, context, char_id)


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
