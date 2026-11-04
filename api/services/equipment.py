"""Equipment slot business logic (compat mapping + atomic swap helper)."""
from __future__ import annotations

import json
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.data.equipment_slots import EQUIPMENT_SLOT_COMPAT
from core.db.models import EquipmentSlot, Item
from core.game.stats import sync_base_ac


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


def apply_equip_ac(char, item, displaced=None) -> None:
    """Armor/shield AC bookkeeping after `item` was (un)equipped, optionally displacing another piece.

    The base follows `computed_base_ac` (any equip change can matter: armor, shield, ability items).
    """
    meta = json.loads(item.item_metadata) if item.item_metadata else {}

    # Neutralize the displaced shield FIRST, then apply the new item's: on a same-slot
    # swap resetting it AFTER would clobber the value just set.
    if displaced is not None and displaced.item_type == "shield" and not char.shield_armor_class_override:
        char.shield_armor_class = 0

    if item.item_type == "shield" and not char.shield_armor_class_override:
        char.shield_armor_class = meta.get("ac_bonus", 2) if item.is_equipped else 0
    sync_base_ac(char)
