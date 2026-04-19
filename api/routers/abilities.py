"""Special abilities / features endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.auth import get_current_user
from api.database import get_db
from core.db.models import Ability, Character, CharacterClass
from api.schemas.character import CharacterFull
from api.schemas.common import AbilityCreate, AbilityRead, AbilityUpdate

router = APIRouter(prefix="/characters", tags=["abilities"])


async def _get_owned_full(char_id: int, user_id: int, session: AsyncSession) -> Character:
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
        raise HTTPException(status_code=404, detail="Character not found")
    if char.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not your character")
    return char


@router.get("/{char_id}/abilities", response_model=list[AbilityRead])
async def list_abilities(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[Ability]:
    char = await _get_owned_full(char_id, user_id, session)
    return char.abilities


@router.post("/{char_id}/abilities", response_model=AbilityRead, status_code=201)
async def add_ability(
    char_id: int,
    body: AbilityCreate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Ability:
    await _get_owned_full(char_id, user_id, session)
    ability = Ability(character_id=char_id, **body.model_dump())
    session.add(ability)
    await session.flush()
    return ability


@router.patch("/{char_id}/abilities/{ability_id}", response_model=AbilityRead)
async def update_ability(
    char_id: int,
    ability_id: int,
    body: AbilityUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Ability:
    await _get_owned_full(char_id, user_id, session)
    result = await session.execute(
        select(Ability).where(Ability.id == ability_id, Ability.character_id == char_id)
    )
    ability = result.scalar_one_or_none()
    if ability is None:
        raise HTTPException(status_code=404, detail="Ability not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(ability, field, value)
    return ability


@router.delete("/{char_id}/abilities/{ability_id}", status_code=204)
async def delete_ability(
    char_id: int,
    ability_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await _get_owned_full(char_id, user_id, session)
    result = await session.execute(
        select(Ability).where(Ability.id == ability_id, Ability.character_id == char_id)
    )
    ability = result.scalar_one_or_none()
    if ability is None:
        raise HTTPException(status_code=404, detail="Ability not found")
    await session.delete(ability)
