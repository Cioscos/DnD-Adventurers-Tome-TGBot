"""Multiclass and class resource endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.auth import get_current_user
from api.database import get_db
from bot.db.models import Character, CharacterClass, ClassResource
from api.schemas.character import CharacterFull
from api.schemas.common import (
    CharacterClassCreate,
    CharacterClassRead,
    CharacterClassUpdate,
    ClassResourceCreate,
    ClassResourceRead,
    ClassResourceUpdate,
)

router = APIRouter(prefix="/characters", tags=["classes"])


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


async def _get_class(class_id: int, char_id: int, session: AsyncSession) -> CharacterClass:
    result = await session.execute(
        select(CharacterClass)
        .options(selectinload(CharacterClass.resources))
        .where(CharacterClass.id == class_id, CharacterClass.character_id == char_id)
    )
    cls = result.scalar_one_or_none()
    if cls is None:
        raise HTTPException(status_code=404, detail="Class not found")
    return cls


# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------

@router.post("/{char_id}/classes", response_model=CharacterFull, status_code=201)
async def add_class(
    char_id: int,
    body: CharacterClassCreate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Character:
    char = await _get_owned_full(char_id, user_id, session)
    cls = CharacterClass(
        character_id=char_id,
        class_name=body.class_name,
        level=body.level,
        subclass=body.subclass,
        spellcasting_ability=body.spellcasting_ability,
        hit_die=body.hit_die,
    )
    session.add(cls)
    await session.flush()
    session.expire(char)
    return await _get_owned_full(char_id, user_id, session)


@router.patch("/{char_id}/classes/{class_id}", response_model=CharacterFull)
async def update_class(
    char_id: int,
    class_id: int,
    body: CharacterClassUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Character:
    char = await _get_owned_full(char_id, user_id, session)
    cls = await _get_class(class_id, char_id, session)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(cls, field, value)
    return char


@router.delete("/{char_id}/classes/{class_id}", response_model=CharacterFull)
async def remove_class(
    char_id: int,
    class_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Character:
    char = await _get_owned_full(char_id, user_id, session)
    cls = await _get_class(class_id, char_id, session)
    await session.delete(cls)
    await session.flush()
    session.expire(char)
    return await _get_owned_full(char_id, user_id, session)


# ---------------------------------------------------------------------------
# Class Resources
# ---------------------------------------------------------------------------

@router.post(
    "/{char_id}/classes/{class_id}/resources",
    response_model=ClassResourceRead,
    status_code=201,
)
async def add_resource(
    char_id: int,
    class_id: int,
    body: ClassResourceCreate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ClassResource:
    # Ownership check
    await _get_owned_full(char_id, user_id, session)
    await _get_class(class_id, char_id, session)
    res = ClassResource(
        class_id=class_id,
        name=body.name,
        current=body.current,
        total=body.total,
        restoration_type=body.restoration_type,
        note=body.note,
    )
    session.add(res)
    await session.flush()
    return res


@router.patch(
    "/{char_id}/classes/{class_id}/resources/{res_id}",
    response_model=ClassResourceRead,
)
async def update_resource(
    char_id: int,
    class_id: int,
    res_id: int,
    body: ClassResourceUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ClassResource:
    await _get_owned_full(char_id, user_id, session)
    result = await session.execute(
        select(ClassResource).where(
            ClassResource.id == res_id, ClassResource.class_id == class_id
        )
    )
    res = result.scalar_one_or_none()
    if res is None:
        raise HTTPException(status_code=404, detail="Resource not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(res, field, value)
    return res


@router.delete(
    "/{char_id}/classes/{class_id}/resources/{res_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_resource(
    char_id: int,
    class_id: int,
    res_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await _get_owned_full(char_id, user_id, session)
    result = await session.execute(
        select(ClassResource).where(
            ClassResource.id == res_id, ClassResource.class_id == class_id
        )
    )
    res = result.scalar_one_or_none()
    if res is None:
        raise HTTPException(status_code=404, detail="Resource not found")
    await session.delete(res)
