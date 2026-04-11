"""Skills (Abilità) handler for the character manager.

Provides a list view of all 18 standard D&D 5e skills (with computed bonus and
proficiency indicator) and a detail view per skill where the user can:
  - Toggle proficiency on/off
  - Auto-roll a d20 + computed bonus and log it to character history
  - Navigate back to the list

The bonus is calculated dynamically as:

    bonus = ability_modifier + (proficiency_bonus  if  proficient  else  0)

No text-input states are needed — everything is driven by inline buttons.
"""

from __future__ import annotations

import logging
import random

from sqlalchemy import select
from telegram import Update
from telegram.ext import ContextTypes

from bot.data.skills import SKILL_ABILITY_MAP, SKILLS
from bot.db.engine import get_session
from bot.db.models import AbilityScore, Character
from bot.handlers.character import CHAR_MENU, CHAR_SKILLS_MENU
from bot.keyboards.character import build_skill_detail_keyboard, build_skills_keyboard
from bot.utils.formatting import format_skill_detail, format_skills
from bot.utils.i18n import get_lang, translator

logger = logging.getLogger(__name__)


async def show_skills_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
) -> int:
    """Render the skills list screen with all 18 skills and their computed bonuses."""
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


async def show_skill_detail(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    skill_slug: str,
    last_roll: "tuple[int, int] | None" = None,
) -> int:
    """Render the detail screen for a single skill."""
    lang = get_lang(update)

    if skill_slug not in SKILL_ABILITY_MAP:
        return await show_skills_menu(update, context, char_id)

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

    ability = SKILL_ABILITY_MAP[skill_slug]
    score_map = {s.name: s.value for s in scores}
    mod = (score_map.get(ability, 10) - 10) // 2
    skill_level = _get_skill_level(char, skill_slug)
    is_proficient = skill_level in ("proficient", "expert")
    bonus = mod + _skill_bonus(char, skill_slug, mod)

    text = format_skill_detail(skill_slug, char, scores, lang=lang, last_roll=last_roll)
    keyboard = build_skill_detail_keyboard(char_id, skill_slug, skill_level, bonus, lang=lang)

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


async def roll_skill(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    skill_slug: str,
) -> int:
    """Roll d20 + skill bonus, log to history, then show the updated detail screen."""
    lang = get_lang(update)

    if skill_slug not in SKILL_ABILITY_MAP:
        return await show_skills_menu(update, context, char_id)

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

    ability = SKILL_ABILITY_MAP[skill_slug]
    score_map = {s.name: s.value for s in scores}
    mod = (score_map.get(ability, 10) - 10) // 2
    bonus = _skill_bonus(char, skill_slug, mod)

    die_result = random.randint(1, 20)
    total = die_result + bonus

    skill_name = translator.t(f"character.skills.names.{skill_slug}", lang=lang)
    bonus_str = f"+{bonus}" if bonus >= 0 else str(bonus)
    log_desc = translator.t(
        "character.skills.roll_logged",
        lang=lang,
        skill_name=skill_name,
        die=die_result,
        bonus=bonus_str,
        total=total,
    )
    import asyncio as _asyncio
    _asyncio.create_task(_log(char_id, "dice_roll", log_desc))

    return await show_skill_detail(update, context, char_id, skill_slug, last_roll=(die_result, total))


async def toggle_skill_proficiency(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    char_id: int,
    skill_slug: str,
) -> int:
    """Cycle skill level: none → proficient → expert → none."""
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
        current = _get_skill_level_from_dict(skills, skill_slug)
        if current == "none":
            new_level = "proficient"
        elif current == "proficient":
            new_level = "expert"
        else:
            new_level = "none"
        skills[skill_slug] = new_level
        char.skills = skills

    skill_name = translator.t(f"character.skills.names.{skill_slug}", lang=lang)
    level_icons = {"none": "⬛", "proficient": "🎯", "expert": "⭐"}
    state = level_icons.get(new_level, "")
    import asyncio as _asyncio
    _asyncio.create_task(_log(char_id, "skill_change", f"{skill_name} → {new_level} {state}"))

    if update.callback_query:
        await update.callback_query.answer(
            translator.t("character.skills.updated", lang=lang)
        )

    return await show_skill_detail(update, context, char_id, skill_slug)


# ---------------------------------------------------------------------------
# Expertise / proficiency helpers
# ---------------------------------------------------------------------------

def _get_skill_level_from_dict(skills_dict: dict, skill_slug: str) -> str:
    """Return 'none', 'proficient', or 'expert' from a raw skills dict."""
    val = skills_dict.get(skill_slug, False)
    if val == "expert":
        return "expert"
    if val == "proficient" or val is True:
        return "proficient"
    return "none"


def _get_skill_level(char, skill_slug: str) -> str:
    """Return 'none', 'proficient', or 'expert' for *skill_slug* on *char*."""
    return _get_skill_level_from_dict(char.skills or {}, skill_slug)


def _skill_bonus(char, skill_slug: str, ability_mod: int) -> int:
    """Return the total skill bonus considering expertise."""
    level = _get_skill_level(char, skill_slug)
    if level == "expert":
        return ability_mod + char.proficiency_bonus * 2
    if level == "proficient":
        return ability_mod + char.proficiency_bonus
    return ability_mod


def get_passive_perception(char, scores: list) -> int:
    """Return the character's passive Perception score."""
    score_map = {s.name: s.value for s in scores}
    wis_mod = (score_map.get("wisdom", 10) - 10) // 2
    bonus = _skill_bonus(char, "perception", wis_mod)
    return 10 + bonus


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
