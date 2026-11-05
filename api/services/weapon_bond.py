"""Arma Vincolata del Cavaliere Mistico: fino a due armi vincolate col rituale, evocate in mano con l'azione bonus."""
from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException, status

from api.services.rules_turn import spend
from core.db.models import EquipmentSlot
from core.game.item_bonuses import item_meta
from core.rules.catalog import active_features
from core.rules.weapons import has_property

FEATURE = "fighter.weapon_bond"
MAX_BONDS = 2
BONDED = "bonded"


def _err(code: int, name: str) -> HTTPException:
    return HTTPException(code, detail={"code": name})


def is_bonded(item: Any) -> bool:
    return bool(item_meta(item).get(BONDED))


def _set(item: Any, value: bool) -> None:
    meta = dict(item_meta(item))
    if value:
        meta[BONDED] = True
    else:
        meta.pop(BONDED, None)
    item.item_metadata = json.dumps(meta)


def _require(char: Any, item: Any) -> None:
    if not any(spec.key == FEATURE for spec, _row in active_features(char)):
        raise _err(status.HTTP_409_CONFLICT, "bond_unavailable")
    if item.item_type != "weapon":
        raise _err(status.HTTP_422_UNPROCESSABLE_ENTITY, "not_a_weapon")


def bond(char: Any, item: Any, replace_id: int | None = None) -> None:
    """Il rituale è concluso: ``item`` è vincolata. Con due armi già vincolate ne serve una da spezzare (``replace_id``)."""
    _require(char, item)
    if is_bonded(item):
        return
    bonded = [i for i in char.items if i.item_type == "weapon" and is_bonded(i)]
    if len(bonded) >= MAX_BONDS:
        if replace_id is None:
            raise _err(status.HTTP_409_CONFLICT, "bond_limit")
        old = next((i for i in bonded if i.id == replace_id), None)
        if old is None:
            raise _err(status.HTTP_422_UNPROCESSABLE_ENTITY, "invalid_replacement")
        _set(old, False)
    _set(item, True)


def break_bond(item: Any) -> None:
    _set(item, False)


def summon(char: Any, item: Any) -> str:
    """Evoca l'arma vincolata nella prima mano libera e spende l'azione bonus. Restituisce lo slot occupato.

    Tutti i controlli prima di spendere: un rifiuto non costa l'azione bonus."""
    _require(char, item)
    if not is_bonded(item):
        raise _err(status.HTTP_409_CONFLICT, "not_bonded")
    if item.is_equipped and item.equipment_slot in (EquipmentSlot.MAIN_HAND, EquipmentSlot.OFF_HAND):
        raise _err(status.HTTP_409_CONFLICT, "already_in_hand")
    busy = {i.equipment_slot for i in char.items if i.is_equipped and i.id != item.id}
    free = [s for s in (EquipmentSlot.MAIN_HAND, EquipmentSlot.OFF_HAND) if s not in busy]
    if not free or (has_property(item, "two_handed") and len(free) < 2):
        raise _err(status.HTTP_409_CONFLICT, "no_free_hand")
    spend(char, "bonus")  # 409 turn_slot_used
    item.is_equipped = True
    item.equipment_slot = free[0]
    return free[0].value
