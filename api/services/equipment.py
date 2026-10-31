"""Equipment slot business logic (compat mapping + atomic swap helper)."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.data.equipment_slots import EQUIPMENT_SLOT_COMPAT
from core.db.models import EquipmentSlot, Item


def slot_allowed_for_type(item_type: str, slot: EquipmentSlot) -> bool:
    """Return True if a slot can hold an item of the given type."""
    return slot in EQUIPMENT_SLOT_COMPAT.get(item_type, set())


async def swap_slot_occupant(
    session: AsyncSession,
    char_id: int,
    new_item_id: int,
    target_slot: EquipmentSlot,
) -> Optional[Item]:
    """Unset is_equipped/equipment_slot on any other item in the same slot.

    Returns the displaced item (if any), or None.
    Caller is responsible for committing the session.
    """
    result = await session.execute(
        select(Item).where(
            Item.character_id == char_id,
            Item.equipment_slot == target_slot,
            Item.id != new_item_id,
            Item.is_equipped.is_(True),
        )
    )
    displaced = result.scalar_one_or_none()
    if displaced is not None:
        displaced.is_equipped = False
        displaced.equipment_slot = None
    return displaced
