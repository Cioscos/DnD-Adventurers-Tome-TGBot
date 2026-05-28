"""Canonical CharacterFull response builder.

Populates the homebrew passive-modifier breakdown fields (ac_breakdown,
hp_max_homebrew_modifier, speed_homebrew_modifier, skills_homebrew_modifiers,
saves_homebrew_modifiers) by calling get_passive_modifiers for each relevant
target_path. Replaces bare CharacterFull.model_validate(char) usages across
the routers.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.character import AcBreakdown, CharacterFull
from api.services.homebrew.passive import get_passive_modifiers
from core.db.models import ABILITY_NAMES, Character

_SKILL_SLUGS = (
    "acrobatics", "animal_handling", "arcana", "athletics", "deception",
    "history", "insight", "intimidation", "investigation", "medicine",
    "nature", "perception", "performance", "persuasion", "religion",
    "sleight_of_hand", "stealth", "survival",
)


async def build_character_response(
    session: AsyncSession, char: Character,
) -> CharacterFull:
    """Build a CharacterFull response with homebrew breakdown populated."""
    response = CharacterFull.model_validate(char)

    hb_ac = await get_passive_modifiers(session, char, "character.ac")
    response.ac_breakdown = AcBreakdown(
        base=char.base_armor_class,
        shield=char.shield_armor_class,
        magic=char.magic_armor,
        homebrew=hb_ac,
    )

    response.hp_max_homebrew_modifier = await get_passive_modifiers(
        session, char, "character.hit_points_max"
    )
    response.speed_homebrew_modifier = await get_passive_modifiers(
        session, char, "character.speed"
    )

    for slug in _SKILL_SLUGS:
        val = await get_passive_modifiers(session, char, f"character.skill.{slug}")
        if val:
            response.skills_homebrew_modifiers[slug] = val

    for slug in ABILITY_NAMES:
        val = await get_passive_modifiers(session, char, f"character.save.{slug}")
        if val:
            response.saves_homebrew_modifiers[slug] = val

    return response
