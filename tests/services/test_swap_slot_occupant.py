"""api.services.equipment.swap_slot_occupant — atomic paper-doll slot displacement.

When an item is equipped into an occupied slot, the prior occupant must be
cleared (``is_equipped`` → False, ``equipment_slot`` → None) and returned so the
caller can undo its AC contribution. The query is narrow on purpose: only an
*equipped* item in the *same* slot with a *different* id is displaced — items in
another slot, the incoming item itself, and unequipped items are all left alone.

Service-level test (mirrors ``tests/services/test_recalc_spell_slots.py``): a
fresh in-memory SQLite session, no FastAPI layer.
"""
from __future__ import annotations

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.db.models import Base, Character, EquipmentSlot, Item
from api.services.equipment import swap_slot_occupant


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


async def _char_with_items(session: AsyncSession, items: list[Item]) -> Character:
    char = Character(user_id=1, name="Fighter")
    char.items = items  # relationship cascade assigns character_id on flush
    session.add(char)
    await session.flush()
    return char


async def test_displaces_prior_occupant(session):
    occupant = Item(name="Longsword", item_type="weapon",
                    equipment_slot=EquipmentSlot.MAIN_HAND, is_equipped=True)
    incoming = Item(name="Warhammer", item_type="weapon",
                    equipment_slot=EquipmentSlot.MAIN_HAND, is_equipped=True)
    char = await _char_with_items(session, [occupant, incoming])

    displaced = await swap_slot_occupant(
        session, char.id, incoming.id, EquipmentSlot.MAIN_HAND
    )
    assert displaced is occupant
    assert occupant.is_equipped is False
    assert occupant.equipment_slot is None


async def test_returns_none_when_slot_empty(session):
    incoming = Item(name="Shield", item_type="shield",
                    equipment_slot=EquipmentSlot.OFF_HAND, is_equipped=True)
    char = await _char_with_items(session, [incoming])
    displaced = await swap_slot_occupant(
        session, char.id, incoming.id, EquipmentSlot.OFF_HAND
    )
    assert displaced is None


async def test_ignores_item_in_a_different_slot(session):
    helm = Item(name="Helm", item_type="gear",
                equipment_slot=EquipmentSlot.HEAD, is_equipped=True)
    incoming = Item(name="Boots", item_type="gear",
                    equipment_slot=EquipmentSlot.FEET, is_equipped=True)
    char = await _char_with_items(session, [helm, incoming])
    displaced = await swap_slot_occupant(
        session, char.id, incoming.id, EquipmentSlot.FEET
    )
    assert displaced is None
    assert helm.is_equipped is True  # untouched


async def test_does_not_displace_itself(session):
    item = Item(name="Ring of Protection", item_type="accessory",
                equipment_slot=EquipmentSlot.RING1, is_equipped=True)
    char = await _char_with_items(session, [item])
    displaced = await swap_slot_occupant(
        session, char.id, item.id, EquipmentSlot.RING1
    )
    assert displaced is None
    assert item.is_equipped is True


async def test_ignores_unequipped_occupant(session):
    stowed = Item(name="Old Sword", item_type="weapon",
                  equipment_slot=EquipmentSlot.MAIN_HAND, is_equipped=False)
    incoming = Item(name="New Sword", item_type="weapon",
                    equipment_slot=EquipmentSlot.MAIN_HAND, is_equipped=True)
    char = await _char_with_items(session, [stowed, incoming])
    displaced = await swap_slot_occupant(
        session, char.id, incoming.id, EquipmentSlot.MAIN_HAND
    )
    assert displaced is None
