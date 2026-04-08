"""Skills (Abilità) handler for the character manager.

Displays all 18 standard D&D 5e skills with their computed bonus and lets
the user toggle proficiency on/off for any skill.  The bonus is calculated
dynamically as:

    bonus = ability_modifier + (proficiency_bonus  if  proficient  else  0)

No text-input states are needed — everything is driven by inline buttons.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from telegram import Update
from telegram.ext import ContextTypes

from bot.data.skills import SKILL_ABILITY_MAP, SKILLS
from bot.db.engine import get_session
from bot.db.models import AbilityScore, Character
from bot.handlers.character import CHAR_MENU, CHAR_SKILLS_MENU
from bot.keyboards.character import build_skills_keyboard
from bot.utils.formatting import format_skills
from bot.utils.i18n import get_lang, translator

logger = logging.getLogger(__name__)


async def show_skills_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
) -> int:
    """Render the skills screen with all 18 skills and their computed bonuses."""
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

    text = format_skills(char, scores, lang=lang)
    keyboard = build_skills_keyboard(char_id, char, scores, lang=lang)

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

    return CHAR_SKILLS_MENU


async def toggle_skill_proficiency(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    skill_slug: str,
) -> int:
    """Toggle the proficiency flag for *skill_slug* and refresh the skills screen."""
    lang = get_lang(update)

    if skill_slug not in SKILL_ABILITY_MAP:
        if update.callback_query:
            await update.callback_query.answer()
        return await show_skills_menu(update, context, char_id)

    async with get_session() as session:
        char = await session.get(Character, char_id)
        if char is None:
            if update.callback_query:
                await update.callback_query.answer()
            return CHAR_MENU

        skills: dict = dict(char.skills or {})
        was_proficient = bool(skills.get(skill_slug, False))
        skills[skill_slug] = not was_proficient
        char.skills = skills

    skill_name = translator.t(f"character.skills.names.{skill_slug}", lang=lang)
    state = "✅" if not was_proficient else "❌"
    import asyncio as _asyncio
    _asyncio.create_task(_log(char_id, "skill_change", f"{skill_name} {state}"))

    if update.callback_query:
        await update.callback_query.answer(
            translator.t("character.skills.updated", lang=lang)
        )

    return await show_skills_menu(update, context, char_id)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _log(char_id: int, event_type: str, description: str) -> None:
    """Fire-and-forget wrapper for history logging."""
    try:
        from bot.db.history import log_history_event
        await log_history_event(char_id, event_type, description)
    except Exception as exc:
        logger.warning("History log failed for char %s: %s", char_id, exc)
