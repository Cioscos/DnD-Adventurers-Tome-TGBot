"""Skill bonus and passive scores including homebrew modifiers (pure parts live in core.game.skills)."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from api.routers._helpers import effective_ability_mod
from api.services.homebrew.passive import get_passive_modifiers, passive_modifier
from core.data.skills import SKILL_ABILITY_MAP
from core.db.models import Character
from core.game.skills import skill_proficiency_part


async def skill_bonus(session: AsyncSession, char: Character, skill: str) -> int:
    return (
        effective_ability_mod(char, SKILL_ABILITY_MAP[skill])
        + skill_proficiency_part(char, skill)
        + await get_passive_modifiers(session, char, f"character.skill.{skill}")
    )


async def passive_score(session: AsyncSession, char: Character, skill: str) -> int:
    return 10 + await skill_bonus(session, char, skill) + await passive_modifier(session, char, skill)
