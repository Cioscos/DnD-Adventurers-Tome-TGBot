"""Inventory (bag) endpoints."""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.auth import get_current_user
from api.database import get_db
from bot.db.models import Character, CharacterClass, Item
from api.schemas.character import CharacterFull
from api.schemas.item import ItemCreate, ItemRead, ItemUpdate

router = APIRouter(prefix="/characters", tags=["items"])


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


@router.get("/{char_id}/items", response_model=list[ItemRead])
async def list_items(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[Item]:
    char = await _get_owned_full(char_id, user_id, session)
    return char.items


@router.post("/{char_id}/items", response_model=CharacterFull, status_code=201)
async def add_item(
    char_id: int,
    body: ItemCreate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Character:
    char = await _get_owned_full(char_id, user_id, session)

    # Deduplication for generic items: merge quantity if same name exists
    if body.item_type == "generic":
        existing_result = await session.execute(
            select(Item).where(
                Item.character_id == char_id,
                Item.item_type == "generic",
                Item.name == body.name,
            )
        )
        existing = existing_result.scalar_one_or_none()
        if existing is not None:
            existing.quantity += body.quantity
            await session.flush()
            char.recalculate_encumbrance()
            await session.refresh(char, attribute_names=["items"])
            return char

    metadata_str = json.dumps(body.item_metadata) if body.item_metadata else None
    item = Item(
        character_id=char_id,
        name=body.name,
        description=body.description,
        weight=body.weight,
        quantity=body.quantity,
        item_type=body.item_type,
        item_metadata=metadata_str,
        is_equipped=body.is_equipped,
    )
    session.add(item)
    await session.flush()
    char.recalculate_encumbrance()
    await session.refresh(char, attribute_names=["items"])
    return char


@router.patch("/{char_id}/items/{item_id}", response_model=CharacterFull)
async def update_item(
    char_id: int,
    item_id: int,
    body: ItemUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Character:
    char = await _get_owned_full(char_id, user_id, session)
    result = await session.execute(
        select(Item).where(Item.id == item_id, Item.character_id == char_id)
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")

    data = body.model_dump(exclude_unset=True)
    if "item_metadata" in data:
        data["item_metadata"] = json.dumps(data["item_metadata"]) if data["item_metadata"] else None
    for field, value in data.items():
        setattr(item, field, value)

    # Auto-update character AC when equipping/unequipping armor or shields
    if "is_equipped" in data:
        item_meta = json.loads(item.item_metadata) if item.item_metadata else {}
        if item.item_type == "armor":
            if item.is_equipped:
                # Unequip any other armor first
                for other in char.items:
                    if other.id != item.id and other.item_type == "armor" and other.is_equipped:
                        other.is_equipped = False
                char.base_armor_class = item_meta.get("ac_value", 10)
            else:
                char.base_armor_class = 10
        elif item.item_type == "shield":
            if item.is_equipped:
                # Unequip any other shield first
                for other in char.items:
                    if other.id != item.id and other.item_type == "shield" and other.is_equipped:
                        other.is_equipped = False
                char.shield_armor_class = item_meta.get("ac_bonus", 2)
            else:
                char.shield_armor_class = 0

    char.recalculate_encumbrance()
    return char


@router.delete("/{char_id}/items/{item_id}", response_model=CharacterFull)
async def delete_item(
    char_id: int,
    item_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Character:
    char = await _get_owned_full(char_id, user_id, session)
    result = await session.execute(
        select(Item).where(Item.id == item_id, Item.character_id == char_id)
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    await session.delete(item)
    await session.flush()
    char.recalculate_encumbrance()
    await session.refresh(char, attribute_names=["items"])
    return char
