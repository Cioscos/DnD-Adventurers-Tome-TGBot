"""Item type -> allowed equipment slots (shared by api and core)."""
from __future__ import annotations

from core.db.models import EquipmentSlot

# Mapping from item_type to set of allowed equipment slots.
EQUIPMENT_SLOT_COMPAT: dict[str, set[EquipmentSlot]] = {
    "weapon": {EquipmentSlot.MAIN_HAND, EquipmentSlot.OFF_HAND},
    "armor": {EquipmentSlot.BODY},
    "shield": {EquipmentSlot.OFF_HAND},
    "accessory": {EquipmentSlot.NECK, EquipmentSlot.CLOAK,
                  EquipmentSlot.RING1, EquipmentSlot.RING2},
    "gear": {EquipmentSlot.HEAD, EquipmentSlot.HANDS,
             EquipmentSlot.FEET, EquipmentSlot.AMMUNITION},
    "ammunition": {EquipmentSlot.AMMUNITION},
}
