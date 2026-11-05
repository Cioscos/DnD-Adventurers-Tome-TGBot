"""Ability scores and AC endpoints."""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.auth import get_current_lang, get_current_user
from api.services.class_features import sync_cataloged_features
from api.database import get_db
from core.db.models import AbilityScore, Character
from core.game.stats import sync_base_ac
from api.schemas.character import CharacterFull
from api.schemas.common import AbilityScoreUpdate
from api.routers._helpers import effective_con_mod
from api.services.effects import cap_current_hp, sync_zero_hp
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


async def apply_ability_change(session: AsyncSession, char: Character, ability: str, old_con_mod: int) -> None:
    """Side effects of an ability score change; call after writing the new value.

    `old_con_mod` is effective_con_mod(char) taken before the change.
    """
    if ability == "strength":
        char.recalculate_carry_capacity()
    sync_base_ac(char)
    # CON change hook: retroactively adjust max HP and current HP
    if ability == "constitution" and (char.settings or {}).get("hp_auto_calc", True):
        delta = effective_con_mod(char) - old_con_mod
        if delta != 0:
            was_at_zero = char.current_hit_points == 0
            char.hit_points = max(0, char.hit_points + delta * char.total_level)
            char.current_hit_points = max(
                0,
                min(char.current_hit_points + delta * char.total_level, char.hit_points),
            )
            await cap_current_hp(session, char)
            await sync_zero_hp(session, char, was_at_zero)


async def _get_owned_full(char_id: int, user_id: int, session: AsyncSession) -> Character:
    from core.db.models import CharacterClass
    result = await session.execute(
        select(Character)
        .options(
            selectinload(Character.classes),
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
    lang: Annotated[str, Depends(get_current_lang)],
) -> CharacterFull:
    char = await _get_owned_full(char_id, user_id, session)

    if not 1 <= body.value <= 30:
        raise HTTPException(status_code=400, detail="Ability score must be between 1 and 30")

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

    await apply_ability_change(session, char, ability_name.lower(), old_con_mod)
    await sync_cataloged_features(session, char, lang)
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

    sync_base_ac(char)

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

    Enable ('wisdom'/'constitution'): without armor the base AC becomes 10 + DEX + that
    ability's mod and stays in sync; the manual base override is cleared (mutually
    exclusive). Disable (null): base AC follows `computed_base_ac` again.
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
    sync_base_ac(char)

    return await build_character_response(session, char)
