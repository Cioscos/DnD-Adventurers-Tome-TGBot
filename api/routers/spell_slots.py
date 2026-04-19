"""Spell slot endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.auth import get_current_user
from api.database import get_db
from core.db.models import Character, CharacterClass, SpellSlot
from api.schemas.character import CharacterFull
from api.schemas.spell import SpellSlotCreate, SpellSlotRead, SpellSlotUpdate

router = APIRouter(prefix="/characters", tags=["spell_slots"])


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


@router.post("/{char_id}/spell_slots", response_model=SpellSlotRead, status_code=201)
async def add_spell_slot(
    char_id: int,
    body: SpellSlotCreate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SpellSlot:
    await _get_owned_full(char_id, user_id, session)
    slot = SpellSlot(character_id=char_id, level=body.level, total=body.total, used=body.used)
    session.add(slot)
    await session.flush()
    return slot


@router.patch("/{char_id}/spell_slots/{slot_id}", response_model=SpellSlotRead)
async def update_spell_slot(
    char_id: int,
    slot_id: int,
    body: SpellSlotUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SpellSlot:
    await _get_owned_full(char_id, user_id, session)
    result = await session.execute(
        select(SpellSlot).where(SpellSlot.id == slot_id, SpellSlot.character_id == char_id)
    )
    slot = result.scalar_one_or_none()
    if slot is None:
        raise HTTPException(status_code=404, detail="Slot not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(slot, field, value)
    return slot


@router.delete("/{char_id}/spell_slots/{slot_id}", status_code=204)
async def delete_spell_slot(
    char_id: int,
    slot_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await _get_owned_full(char_id, user_id, session)
    result = await session.execute(
        select(SpellSlot).where(SpellSlot.id == slot_id, SpellSlot.character_id == char_id)
    )
    slot = result.scalar_one_or_none()
    if slot is None:
        raise HTTPException(status_code=404, detail="Slot not found")
    await session.delete(slot)


@router.post("/{char_id}/spell_slots/reset", response_model=CharacterFull)
async def reset_spell_slots(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Character:
    char = await _get_owned_full(char_id, user_id, session)
    for slot in char.spell_slots:
        slot.used = 0
    return char
