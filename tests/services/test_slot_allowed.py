"""api.services.equipment.slot_allowed_for_type — item_type → allowed slots.

Pure mapping check (no DB, no FastAPI). ``EQUIPMENT_SLOT_COMPAT`` is the single
source of truth the slot-aware PATCH endpoint and the webapp paper-doll both
depend on, so this pins the D&D 5e slot rules: weapons go in hands, armor on
the body, shields in the off-hand, accessories on neck/cloak/rings, and the
rest (head/hands/feet/ammunition) is generic gear. Unknown types match nothing.
"""
from __future__ import annotations

import pytest

from core.db.models import EquipmentSlot
from api.services.equipment import EQUIPMENT_SLOT_COMPAT, slot_allowed_for_type


@pytest.mark.parametrize(
    ("item_type", "slot"),
    [
        ("weapon", EquipmentSlot.MAIN_HAND),
        ("weapon", EquipmentSlot.OFF_HAND),
        ("armor", EquipmentSlot.BODY),
        ("shield", EquipmentSlot.OFF_HAND),
        ("accessory", EquipmentSlot.NECK),
        ("accessory", EquipmentSlot.CLOAK),
        ("accessory", EquipmentSlot.RING1),
        ("accessory", EquipmentSlot.RING2),
        ("gear", EquipmentSlot.HEAD),
        ("gear", EquipmentSlot.HANDS),
        ("gear", EquipmentSlot.FEET),
        ("gear", EquipmentSlot.AMMUNITION),
    ],
)
def test_allowed_pairs(item_type: str, slot: EquipmentSlot) -> None:
    assert slot_allowed_for_type(item_type, slot) is True


@pytest.mark.parametrize(
    ("item_type", "slot"),
    [
        ("armor", EquipmentSlot.MAIN_HAND),   # armor is body-only
        ("weapon", EquipmentSlot.BODY),       # a sword is not body armor
        ("shield", EquipmentSlot.MAIN_HAND),  # shields are off-hand only
        ("accessory", EquipmentSlot.HEAD),    # rings/cloaks are not head gear
        ("gear", EquipmentSlot.BODY),         # generic gear is not body armor
    ],
)
def test_rejected_pairs(item_type: str, slot: EquipmentSlot) -> None:
    assert slot_allowed_for_type(item_type, slot) is False


def test_unknown_item_type_allows_no_slot() -> None:
    # Unmapped types must never satisfy any slot (no accidental empty-set truthiness).
    for slot in EquipmentSlot:
        assert slot_allowed_for_type("totally-made-up", slot) is False


def test_compat_only_references_real_enum_members() -> None:
    # Guards against a typo'd slot string slipping into the mapping.
    for slots in EQUIPMENT_SLOT_COMPAT.values():
        for slot in slots:
            assert isinstance(slot, EquipmentSlot)
