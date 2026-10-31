"""Skill bonus and passive scores: one calculation shared by rolls, passives and the sheet."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from core.data.skills import SKILL_ABILITY_MAP
from core.data.spell_slots import normalize_class_name
from core.db.models import Character

PASSIVE_SKILLS = ("perception", "insight", "investigation")


def has_jack_of_all_trades(char: Character) -> bool:
    """Bard level 2+ (computed, never stored)."""
    return any(
        normalize_class_name(c.class_name) == "bard" and c.level >= 2
        for c in char.classes
    )


def skill_proficiency_part(char: Character, skill: str) -> int:
    """PB x {expert 2, proficient 1}; Jack of All Trades adds floor(PB/2) when not proficient."""
    level = (char.skills or {}).get(skill)
    pb = char.proficiency_bonus
    if level == "expert":
        return 2 * pb
    if level is True or level == 1:
        return pb
    return pb // 2 if has_jack_of_all_trades(char) else 0


async def skill_bonus(session: AsyncSession, char: Character, skill: str) -> int:
    # Lazy imports: api.* imports core.* at module load.
    from api.routers._helpers import effective_ability_mod
    from api.services.homebrew.passive import get_passive_modifiers

    return (
        effective_ability_mod(char, SKILL_ABILITY_MAP[skill])
        + skill_proficiency_part(char, skill)
        + await get_passive_modifiers(session, char, f"character.skill.{skill}")
    )


async def passive_score(session: AsyncSession, char: Character, skill: str) -> int:
    from api.services.homebrew.passive import passive_modifier

    return 10 + await skill_bonus(session, char, skill) + await passive_modifier(session, char, skill)
