"""Skill bonus and passive scores including homebrew modifiers (pure parts live in core.game.skills)."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from core.game.stats import roll_ability_mod
from api.services.homebrew.passive import get_passive_modifiers, passive_modifier
from core.data.skills import SKILL_ABILITY_MAP
from core.db.models import Character
from core.game.skills import jack_of_all_trades_part, skill_proficiency_part
from core.rules.modifiers import modifiers_for, passive_adjustment


async def check_bonus(session: AsyncSession, char: Character, ability: str, skill: str | None = None) -> int:
    """Bonus fisso di una prova: unica formula per le abilità e per le prove di caratteristica pure. La pura non ha
    competenza (solo il Factotum), né regole homebrew per abilità."""
    if skill is None:
        return roll_ability_mod(char, ability) + jack_of_all_trades_part(char) + modifiers_for(char, "ability", ability=ability).flat
    return (
        roll_ability_mod(char, ability)
        + skill_proficiency_part(char, skill)
        + await get_passive_modifiers(session, char, f"character.skill.{skill}")
        + modifiers_for(char, "skill", skill=skill, ability=ability).flat
    )


async def skill_bonus(session: AsyncSession, char: Character, skill: str) -> int:
    return await check_bonus(session, char, SKILL_ABILITY_MAP[skill], skill)


async def passive_score(session: AsyncSession, char: Character, skill: str) -> int:
    return (
        10 + await skill_bonus(session, char, skill) + await passive_modifier(session, char, skill)
        + passive_adjustment(char, skill)
    )
