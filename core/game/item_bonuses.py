"""Conditional bonuses granted by (magic) items."""

from __future__ import annotations

import json
from typing import Iterable

from core.data.equipment_slots import EQUIPMENT_SLOT_COMPAT

_EQUIPPABLE_TYPES = set(EQUIPMENT_SLOT_COMPAT) | {"clothing"}


def item_meta(item) -> dict:
    raw = item.item_metadata
    if isinstance(raw, dict):
        return raw
    try:
        meta = json.loads(raw) if raw else {}
    except (TypeError, ValueError):
        return {}
    return meta if isinstance(meta, dict) else {}


_MAGIC_FLAGS = ("is_magic", "magical", "requires_attunement", "attuned", "rarity", "bonuses", "charges", "granted_spells")


def is_magic_item(item) -> bool:
    """Un oggetto magico: bonus magico diverso da zero (anche non numerico) o uno dei segni che l'inventario e l'import gli danno."""
    meta = item_meta(item)
    try:
        bonus = int(meta.get("magic_bonus") or 0)
    except (TypeError, ValueError):
        bonus = 1
    return bonus != 0 or any(meta.get(k) for k in _MAGIC_FLAGS)


def is_attuned(item) -> bool:
    return bool(item_meta(item).get("attuned"))


def is_active_for_bonuses(item) -> bool:
    # Invariant: container_id never dangles (delete/un-container always re-parent), so non-null == contained.
    if getattr(item, "container_id", None) is not None:
        return False
    meta = item_meta(item)
    if meta.get("requires_attunement") and not meta.get("attuned"):
        return False
    return bool(item.is_equipped) or item.item_type not in _EQUIPPABLE_TYPES


def attack_bonus_total(items: Iterable, weapon, target: str) -> int:
    """`attack`/`damage` bonus for a swing: the weapon's own bonus (if active) plus
    bonuses of active non-weapon items. `weapon=None` = unarmed (non-weapon items only)."""
    others = [i for i in items if i.item_type != "weapon"]
    own = [weapon] if weapon is not None else []
    return item_bonus_total(own, target) + item_bonus_total(others, target)


def item_bonus_total(items: Iterable, target: str) -> int:
    """Sum active item bonuses for `target`; `save.<ab>` also includes `saves`."""
    targets = {target, "saves"} if target.startswith("save.") else {target}
    total = 0
    for item in items:
        if not is_active_for_bonuses(item):
            continue
        for b in item_meta(item).get("bonuses") or []:
            if isinstance(b, dict) and b.get("target") in targets and isinstance(b.get("value"), int):
                total += b["value"]
    return total
