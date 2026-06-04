"""Ability scores and AC endpoints."""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.auth import get_current_user
from api.database import get_db
from core.db.models import AbilityScore, Character
from core.game.stats import ability_modifier, unarmored_defense_ac
from api.schemas.character import CharacterFull
from api.schemas.common import AbilityScoreUpdate
from api.routers._helpers import effective_con_mod
from api.services.character_response import build_character_response
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/characters", tags=["stats"])

# Abilities allowed as the Unarmored Defense second stat (DEX is always the first).
_UNARMORED_SECOND_ABILITIES = ("wisdom", "constitution")


class ACUpdate(BaseModel):
    base: Optional[int] = None
    shield: Optional[int] = None
    magic: Optional[int] = None


class CarryCapacityUpdate(BaseModel):
    value: int


class UnarmoredDefenseUpdate(BaseModel):
    # 'wisdom' (Monk) or 'constitution' (Barbarian) to enable; null to disable.
    ability: Optional[str] = None


def _ability_mod(char: Character, name: str) -> int:
    score = next((s for s in char.ability_scores if s.name == name), None)
    return ability_modifier(score.value) if score else 0


def _base_ac_from_equipment(char: Character) -> int:
    """Base AC derived from the equipped body armor (or 10 when unarmored)."""
    equipped_armor = next(
        (i for i in (char.items or [])
         if i.is_equipped and i.equipment_slot == "body" and i.item_type == "armor"),
        None,
    )
    if equipped_armor is not None:
        meta = json.loads(equipped_armor.item_metadata) if equipped_armor.item_metadata else {}
        return int(meta.get("ac_value", 10))
    return 10


def _recompute_unarmored_base(char: Character) -> None:
    """Sync base_armor_class to 10 + DEX + second-ability mod (Unarmored Defense)."""
    if not char.unarmored_defense_ability:
        return
    char.base_armor_class = unarmored_defense_ac(
        _ability_mod(char, "dexterity"),
        _ability_mod(char, char.unarmored_defense_ability),
    )


async def _get_owned_full(char_id: int, user_id: int, session: AsyncSession) -> Character:
    from core.db.models import CharacterClass
    result = await session.execute(
        select(Character)
        .options(
            selectinload(Character.classes).selectinload(CharacterClass.resources),
            selectinload(Character.ability_scores),
            selectinload(Character.spells),
            selectinload(Character.spell_slots),
            selectinload(Character.items),
            selectinload(Character.currency),
            selectinload(Character.abilities),
            selectinload(Character.maps),
        )
        .where(Character.id == char_id)
    )
    char = result.scalar_one_or_none()
    if char is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character not found")
    if char.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your character")
    return char


@router.patch("/{char_id}/ability_scores/{ability_name}", response_model=CharacterFull)
async def update_ability_score(
    char_id: int,
    ability_name: str,
    body: AbilityScoreUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CharacterFull:
    char = await _get_owned_full(char_id, user_id, session)

    if not 1 <= body.value <= 30:
        raise HTTPException(status_code=400, detail="Ability score must be between 1 and 30")

    is_constitution = ability_name.lower() == "constitution"
    settings = char.settings or {}
    auto_calc = settings.get("hp_auto_calc", True)

    old_con_mod = 0
    if is_constitution and auto_calc:
        old_con_mod = effective_con_mod(char)

    result = await session.execute(
        select(AbilityScore).where(
            AbilityScore.character_id == char_id,
            AbilityScore.name == ability_name.lower(),
        )
    )
    score = result.scalar_one_or_none()
    if score is None:
        score = AbilityScore(character_id=char_id, name=ability_name.lower(), value=body.value)
        session.add(score)
    else:
        score.value = body.value

    # Recalculate carry capacity if STR changed
    if ability_name.lower() == "strength":
        char.recalculate_carry_capacity()

    # Unarmored Defense keeps base AC in sync with DEX and the chosen second ability.
    if char.unarmored_defense_ability and ability_name.lower() in (
        "dexterity", char.unarmored_defense_ability,
    ):
        _recompute_unarmored_base(char)

    # CON change hook: retroactively adjust max HP and current HP
    if is_constitution and auto_calc:
        new_con_mod = effective_con_mod(char)
        delta = new_con_mod - old_con_mod
        if delta != 0:
            char.hit_points = max(0, char.hit_points + delta * char.total_level)
            char.current_hit_points = max(
                0,
                min(char.current_hit_points + delta * char.total_level, char.hit_points),
            )

    return await build_character_response(session, char)


@router.patch("/{char_id}/ac", response_model=CharacterFull)
async def update_ac(
    char_id: int,
    body: ACUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CharacterFull:
    char = await _get_owned_full(char_id, user_id, session)
    if body.base is not None:
        char.base_armor_class = max(0, body.base)
        char.base_armor_class_override = True
    if body.shield is not None:
        char.shield_armor_class = max(0, body.shield)
        char.shield_armor_class_override = True
    if body.magic is not None:
        char.magic_armor = max(0, body.magic)
    return await build_character_response(session, char)


@router.post("/{char_id}/ac/reset-override", response_model=CharacterFull)
async def reset_ac_override(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CharacterFull:
    """Clear AC manual override flags and recompute Base/Shield from currently equipped items."""
    char = await _get_owned_full(char_id, user_id, session)
    char.base_armor_class_override = False
    char.shield_armor_class_override = False

    equipped_shield = next(
        (i for i in (char.items or []) if i.is_equipped and i.equipment_slot == "off_hand" and i.item_type == "shield"),
        None,
    )

    # Unarmored Defense (when active) owns the base AC; otherwise derive from armor.
    if char.unarmored_defense_ability:
        _recompute_unarmored_base(char)
    else:
        char.base_armor_class = _base_ac_from_equipment(char)

    if equipped_shield is not None:
        meta = json.loads(equipped_shield.item_metadata) if equipped_shield.item_metadata else {}
        char.shield_armor_class = int(meta.get("ac_bonus", 2))
    else:
        char.shield_armor_class = 0

    return await build_character_response(session, char)


@router.patch("/{char_id}/carry-capacity", response_model=CharacterFull)
async def update_carry_capacity(
    char_id: int,
    body: CarryCapacityUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CharacterFull:
    """Set a manual carry capacity and lock it against Strength recomputation."""
    char = await _get_owned_full(char_id, user_id, session)
    char.carry_capacity = max(0, body.value)
    char.carry_capacity_override = True
    return await build_character_response(session, char)


@router.post("/{char_id}/carry-capacity/reset-override", response_model=CharacterFull)
async def reset_carry_capacity_override(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CharacterFull:
    """Clear the manual override and recompute carry capacity from Strength (STR x 15)."""
    char = await _get_owned_full(char_id, user_id, session)
    char.carry_capacity_override = False
    char.recalculate_carry_capacity()
    return await build_character_response(session, char)


@router.post("/{char_id}/ac/unarmored-defense", response_model=CharacterFull)
async def set_unarmored_defense(
    char_id: int,
    body: UnarmoredDefenseUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CharacterFull:
    """Enable/disable Unarmored Defense.

    Enable ('wisdom'/'constitution'): base AC becomes 10 + DEX + that ability's mod and
    stays in sync with ability changes; the manual base override is cleared (mutually
    exclusive). Disable (null): base AC reverts to the equipped armor (or 10).
    """
    char = await _get_owned_full(char_id, user_id, session)
    ability = body.ability.lower() if body.ability else None

    if ability is not None and ability not in _UNARMORED_SECOND_ABILITIES:
        raise HTTPException(
            status_code=400,
            detail=f"ability must be one of {_UNARMORED_SECOND_ABILITIES} or null",
        )

    char.unarmored_defense_ability = ability
    if ability is not None:
        char.base_armor_class_override = False
        _recompute_unarmored_base(char)
    else:
        char.base_armor_class = _base_ac_from_equipment(char)

    return await build_character_response(session, char)
