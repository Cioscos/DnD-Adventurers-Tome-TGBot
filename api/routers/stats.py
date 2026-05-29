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
from api.schemas.character import CharacterFull
from api.schemas.common import AbilityScoreUpdate
from api.routers._helpers import effective_con_mod
from api.services.character_response import build_character_response
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/characters", tags=["stats"])


class ACUpdate(BaseModel):
    base: Optional[int] = None
    shield: Optional[int] = None
    magic: Optional[int] = None


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

    equipped_armor = next(
        (i for i in (char.items or []) if i.is_equipped and i.equipment_slot == "body" and i.item_type == "armor"),
        None,
    )
    equipped_shield = next(
        (i for i in (char.items or []) if i.is_equipped and i.equipment_slot == "off_hand" and i.item_type == "shield"),
        None,
    )

    if equipped_armor is not None:
        meta = json.loads(equipped_armor.item_metadata) if equipped_armor.item_metadata else {}
        char.base_armor_class = int(meta.get("ac_value", 10))
    else:
        char.base_armor_class = 10

    if equipped_shield is not None:
        meta = json.loads(equipped_shield.item_metadata) if equipped_shield.item_metadata else {}
        char.shield_armor_class = int(meta.get("ac_bonus", 2))
    else:
        char.shield_armor_class = 0

    return await build_character_response(session, char)
