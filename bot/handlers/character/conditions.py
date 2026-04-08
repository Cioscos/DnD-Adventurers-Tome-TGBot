"""Character conditions handler.

Handles the conditions screen where players can track active D&D 5e conditions
(Blinded, Charmed, Deafened, etc.) and Exhaustion level (0–6).

Conditions are stored as a JSON dict in ``Character.conditions``.
"""

from __future__ import annotations

import asyncio
import logging

from telegram import Update
from telegram.ext import ContextTypes

from bot.db.engine import get_session
from bot.db.models import Character
from bot.handlers.character import CHAR_CONDITIONS_MENU
from bot.keyboards.character import build_condition_detail_keyboard, build_conditions_keyboard
from bot.utils.formatting import format_condition_detail, format_conditions
from bot.utils.i18n import get_lang, translator

logger = logging.getLogger(__name__)


def _get_conditions(char: Character) -> dict:
    """Return the conditions dict, defaulting to empty if not set."""
    return dict(char.conditions) if char.conditions else {}


async def show_conditions_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int
) -> int:
    """Display the full list of conditions with their current state."""
    lang = get_lang(update)
    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            if update.callback_query:
                await update.callback_query.answer(
                    translator.t("character.common.error_not_found", lang=lang)
                )
            return CHAR_CONDITIONS_MENU
        conditions = _get_conditions(char)

    text = format_conditions(conditions, lang=lang)
    keyboard = build_conditions_keyboard(char_id, conditions, lang=lang)
    await _edit_or_reply(update, text, keyboard)
    return CHAR_CONDITIONS_MENU


async def show_condition_detail(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int, slug: str
) -> int:
    """Display detail view for a single condition."""
    lang = get_lang(update)
    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            return await show_conditions_menu(update, context, char_id)
        conditions = _get_conditions(char)

    text = format_condition_detail(slug, conditions, lang=lang)
    keyboard = build_condition_detail_keyboard(char_id, slug, conditions, lang=lang)
    await _edit_or_reply(update, text, keyboard)
    return CHAR_CONDITIONS_MENU


async def toggle_condition(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int, slug: str
) -> int:
    """Toggle a binary condition on/off."""
    lang = get_lang(update)
    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            return await show_conditions_menu(update, context, char_id)
        conditions = _get_conditions(char)
        conditions[slug] = not bool(conditions.get(slug, False))
        new_val = conditions[slug]
        char.conditions = conditions

    asyncio.create_task(_trigger_party_update(char_id, context))
    state_label = "attivata" if new_val else "disattivata"
    asyncio.create_task(_log(char_id, "condition_change", f"{slug} {state_label}"))
    if update.callback_query:
        await update.callback_query.answer(
            translator.t("character.conditions.updated", lang=lang)
        )
    return await show_condition_detail(update, context, char_id, slug)


async def adjust_exhaustion(
    update: Update, context: ContextTypes.DEFAULT_TYPE, char_id: int, direction: str
) -> int:
    """Increase or decrease Exhaustion level (0–6)."""
    lang = get_lang(update)
    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            return await show_conditions_menu(update, context, char_id)
        conditions = _get_conditions(char)
        current = int(conditions.get("exhaustion", 0))

        if direction == "up":
            if current >= 6:
                if update.callback_query:
                    await update.callback_query.answer(
                        translator.t("character.conditions.exhaustion_at_max", lang=lang)
                    )
                return await show_condition_detail(update, context, char_id, "exhaustion")
            conditions["exhaustion"] = current + 1
        else:  # down
            if current <= 0:
                if update.callback_query:
                    await update.callback_query.answer(
                        translator.t("character.conditions.exhaustion_at_min", lang=lang)
                    )
                return await show_condition_detail(update, context, char_id, "exhaustion")
            conditions["exhaustion"] = current - 1

        char.conditions = conditions

    asyncio.create_task(_trigger_party_update(char_id, context))
    new_level = conditions["exhaustion"]
    asyncio.create_task(_log(char_id, "condition_change", f"Esaurimento: {current} → {new_level}"))
    if update.callback_query:
        await update.callback_query.answer(
            translator.t("character.conditions.updated", lang=lang)
        )
    return await show_condition_detail(update, context, char_id, "exhaustion")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _trigger_party_update(char_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fire-and-forget wrapper that calls maybe_update_party_message."""
    try:
        from bot.handlers.party import maybe_update_party_message
        await maybe_update_party_message(char_id, context.bot)
    except Exception as e:
        logger.warning("Party update trigger failed for char %s: %s", char_id, e)


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
