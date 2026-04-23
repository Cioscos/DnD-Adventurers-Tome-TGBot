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
    ClassDistribute,
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
from core.data.xp_thresholds import xp_to_level
from core.game.stats import hit_points_for_level, total_base_hp
from api.routers._helpers import effective_con_mod

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

    # Capture before adding the new class — used for auto-HP bootstrap below.
    is_first_class = len(char.classes) == 0

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

    # Auto-HP bootstrap: only if this is the FIRST class and HP are still 0.
    settings = char.settings or {}
    auto_calc = settings.get("hp_auto_calc", True)
    if is_first_class and char.hit_points == 0 and auto_calc and hit_die:
        con_row = next((a for a in char.ability_scores if a.name == "constitution"), None)
        con_mod = (con_row.value - 10) // 2 if con_row else 0
        hp = hit_points_for_level(hit_die, con_mod, 1)
        char.hit_points = hp
        char.current_hit_points = hp
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


@router.patch("/{char_id}/classes/distribute", response_model=CharacterFull)
async def distribute_class_levels(
    char_id: int,
    body: ClassDistribute,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CharacterFull:
    """Atomically redistribute class levels.

    Validates that:
    1. Every entry's `class_id` belongs to the character.
    2. The body covers every existing class (no missing nor extra ids).
    3. `sum(level)` equals `xp_to_level(char.experience_points)`.

    On success, updates each class's level, syncs predefined class
    resources (grow or shrink via `update_resources_for_level`),
    and recalculates HP proportionally if `settings.hp_auto_calc` is true.
    """
    char = await _get_owned_full(char_id, user_id, session)

    existing_ids = {cls.id for cls in char.classes}
    body_ids = {entry.class_id for entry in body.classes}
    if existing_ids != body_ids:
        raise HTTPException(status_code=400, detail="classes_mismatch")

    target_sum = xp_to_level(char.experience_points or 0)
    new_sum = sum(entry.level for entry in body.classes)
    if new_sum != target_sum:
        raise HTTPException(status_code=400, detail="sum_mismatch")

    # Map id -> new_level for O(1) lookup
    new_levels = {entry.class_id: entry.level for entry in body.classes}

    # Snapshot old total HP for ratio scaling
    old_total_hp = char.hit_points or 0
    old_current_hp = char.current_hit_points or 0

    # Apply level changes + resource sync
    for cls in char.classes:
        new_level = new_levels[cls.id]
        if new_level == cls.level:
            continue
        cls.level = new_level
        update_resources_for_level(
            cls.class_name, new_level, list(cls.resources), char
        )
        existing_names = {r.name for r in cls.resources}
        for res_data in get_resources_for_class(cls.class_name, new_level, char):
            if res_data["name"] not in existing_names:
                session.add(ClassResource(class_id=cls.id, **res_data))

    # HP recalc (respecting hp_auto_calc); populate hp_gained for toast parity with PATCH /xp
    settings = char.settings or {}
    hp_gained = 0
    if settings.get("hp_auto_calc", True):
        con_mod = effective_con_mod(char)
        new_total_hp = total_base_hp(char.classes, con_mod)
        if old_total_hp > 0:
            ratio = old_current_hp / old_total_hp
            new_current = round(ratio * new_total_hp)
        else:
            new_current = old_current_hp
        hp_gained = max(0, new_total_hp - old_total_hp)
        char.hit_points = new_total_hp
        char.current_hit_points = max(0, min(new_current, new_total_hp))

    await session.flush()
    result = CharacterFull.model_validate(char)
    if hp_gained > 0:
        result.hp_gained = hp_gained
    return result


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
