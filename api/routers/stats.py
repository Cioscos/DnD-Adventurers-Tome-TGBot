"""Ability scores and AC endpoints."""

from __future__ import annotations

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
) -> Character:
    char = await _get_owned_full(char_id, user_id, session)

    if not 1 <= body.value <= 30:
        raise HTTPException(status_code=400, detail="Ability score must be between 1 and 30")

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

    return char


@router.patch("/{char_id}/ac", response_model=CharacterFull)
async def update_ac(
    char_id: int,
    body: ACUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Character:
    char = await _get_owned_full(char_id, user_id, session)
    if body.base is not None:
        char.base_armor_class = max(0, body.base)
    if body.shield is not None:
        char.shield_armor_class = max(0, body.shield)
    if body.magic is not None:
        char.magic_armor = max(0, body.magic)
    return char
