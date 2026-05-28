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
from core.data.skills import SKILL_ABILITY_MAP
from core.db.models import ABILITY_NAMES, Character


async def build_character_response(
    session: AsyncSession, char: Character,
) -> CharacterFull:
    """Build a CharacterFull response with homebrew breakdown populated."""
    # TODO (perf): each get_passive_modifiers call issues 2 SELECTs (rules + items).
    # At 27 calls/response this is 54 SELECTs. Batch by preloading rules+items once
    # and exposing a sum_modifiers(rules, items, target_path) helper.
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

    for slug in SKILL_ABILITY_MAP:
        val = await get_passive_modifiers(session, char, f"character.skill.{slug}")
        if val:
            response.skills_homebrew_modifiers[slug] = val

    for slug in ABILITY_NAMES:
        val = await get_passive_modifiers(session, char, f"character.save.{slug}")
        if val:
            response.saves_homebrew_modifiers[slug] = val

    return response
