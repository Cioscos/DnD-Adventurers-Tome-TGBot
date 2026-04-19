"""Multiclass and class resource endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.auth import get_current_user
from api.database import get_db
from core.db.models import Character, CharacterClass, ClassResource
from api.schemas.character import CharacterFull
from api.schemas.common import (
    CharacterClassCreate,
    CharacterClassRead,
    CharacterClassUpdate,
    ClassResourceCreate,
    ClassResourceRead,
    ClassResourceUpdate,
)
from core.data.classes import (
    CLASS_HIT_DIE,
    CLASS_SPELLCASTING,
    get_resources_for_class,
    update_resources_for_level,
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

    # Auto-fill hit_die and spellcasting_ability for predefined classes.
    hit_die = body.hit_die
    spellcasting_ability = body.spellcasting_ability
    if body.class_name in CLASS_HIT_DIE:
        if hit_die is None:
            hit_die = CLASS_HIT_DIE[body.class_name]
        if spellcasting_ability is None:
            spellcasting_ability = CLASS_SPELLCASTING.get(body.class_name)

    cls = CharacterClass(
        character_id=char_id,
        class_name=body.class_name,
        level=body.level,
        subclass=body.subclass,
        spellcasting_ability=spellcasting_ability,
        hit_die=hit_die,
    )
    session.add(cls)
    await session.flush()

    # Auto-create class resources for predefined classes.
    for res_data in get_resources_for_class(body.class_name, body.level, char):
        session.add(ClassResource(class_id=cls.id, **res_data))

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
    old_level = cls.level
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(cls, field, value)

    # When level changes, sync resources for predefined classes.
    if body.level is not None and body.level != old_level:
        new_level = cls.level  # already updated by setattr
        update_resources_for_level(cls.class_name, new_level, list(cls.resources), char)
        existing_names = {r.name for r in cls.resources}
        for res_data in get_resources_for_class(cls.class_name, new_level, char):
            if res_data["name"] not in existing_names:
                session.add(ClassResource(class_id=cls.id, **res_data))

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
