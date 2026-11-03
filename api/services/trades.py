"""Giving items, whole containers and loose coins from one character to another."""
from __future__ import annotations

import json

from fastapi import HTTPException

from api.services.containers import withdraw
from api.services.equipment import apply_equip_ac
from core.db.models import Currency, EquipmentSlot, Item
from core.game.containers import COINS, allocate, descendant_ids, is_container, trade_snapshot
from core.game.item_bonuses import item_meta


def _pick(owner, item_id: int, quantity: int | None):
    """Validate an item/quantity request; returns (item, partial quantity or None, snapshot)."""
    item = next((i for i in owner.items if i.id == item_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    if quantity is not None and not 1 <= quantity <= item.quantity:
        raise HTTPException(status_code=422, detail="invalid_quantity")
    if quantity == item.quantity:
        quantity = None
    if quantity is not None and is_container(item):  # lo split duplicherebbe le monete
        raise HTTPException(status_code=422, detail="invalid_quantity")
    return item, quantity, trade_snapshot(owner.items, item.id, item.quantity if quantity is None else quantity)


async def remove_item(db, owner, item_id: int, quantity: int | None) -> dict:
    """Destroy an item (whole subtree if a container) or shrink its stack; returns the snapshot."""
    item, quantity, snapshot = _pick(owner, item_id, quantity)
    if quantity is not None:
        item.quantity -= quantity
    else:
        for row in [i for i in owner.items if i.id == item.id or i.id in descendant_ids(owner.items, item.id)]:
            await db.delete(row)
    await db.flush()
    return snapshot


async def give_item(db, sender, recipient, item_id: int, quantity: int | None):
    """Hand an item (with its whole subtree if a container) to `recipient`, at their root.

    Returns (snapshot, rows taken off the sender's paper-doll with their previous slot).
    """
    item, quantity, snapshot = _pick(sender, item_id, quantity)

    same = next((
        o for o in recipient.items
        if o.container_id is None and o.item_type == "generic" == item.item_type
        and not is_container(o) and not is_container(item) and o.name == item.name
    ), None)

    if quantity is not None:  # split: the staying row keeps its equip state
        item.quantity -= quantity
        if same is not None:
            same.quantity += quantity
        else:
            db.add(Item(
                character_id=recipient.id, name=item.name, description=item.description,
                weight=item.weight, quantity=quantity, item_type=item.item_type,
                item_metadata=json.dumps({**item_meta(item), "attuned": False}) if item_meta(item).get("attuned") else item.item_metadata,
            ))
        await db.flush()
        return snapshot, []

    tree = [i for i in sender.items if i.id == item.id or i.id in descendant_ids(sender.items, item.id)]
    removed: list[tuple[Item, EquipmentSlot | None]] = []
    for row in tree:
        if row.is_equipped:
            removed.append((row, row.equipment_slot))
        row.is_equipped, row.equipment_slot = False, None
        md = item_meta(row)
        if md.get("attuned"):
            row.item_metadata = json.dumps({**md, "attuned": False})
    for row, _slot in removed:
        apply_equip_ac(sender, row)

    if same is not None:
        same.quantity += item.quantity
        await db.delete(item)
    else:
        for row in tree:
            row.character_id = recipient.id
        item.container_id = None
    await db.flush()
    return snapshot, removed


def _positive_coins(coins: dict[str, int]) -> dict[str, int]:
    given = {c: n for c, n in coins.items() if isinstance(n, int) and n > 0}
    if (not given or any(c not in COINS for c in coins)
            or any(not isinstance(n, int) or n < 0 for n in coins.values())):
        raise HTTPException(status_code=422, detail="nothing_to_give")
    return given


def _check_funds(owner, given: dict[str, int]) -> None:
    purse = {c: getattr(owner.currency, c) or 0 for c in COINS} if owner.currency else {}
    for coin, n in given.items():  # dry run: no mutation until every coin is covered
        try:
            allocate(purse, owner.items, coin, -n)
        except ValueError:
            raise HTTPException(status_code=409, detail="insufficient_funds")


def add_coins(owner, coins: dict[str, int]) -> dict[str, int]:
    """Create coins in the owner's purse."""
    given = _positive_coins(coins)
    if owner.currency is None:
        owner.currency = Currency(character_id=owner.id)
    for coin, n in given.items():
        setattr(owner.currency, coin, (getattr(owner.currency, coin) or 0) + n)
    return given


def remove_coins(owner, coins: dict[str, int]) -> dict[str, int]:
    """Destroy coins (purse first, then containers), all-or-nothing."""
    given = _positive_coins(coins)
    _check_funds(owner, given)
    for coin, n in given.items():
        withdraw(owner, coin, n)
    return given


def give_coins(sender, recipient, coins: dict[str, int]) -> dict[str, int]:
    """Move coins (purse first, then containers) to the recipient's purse, all-or-nothing."""
    given = remove_coins(sender, coins)
    add_coins(recipient, given)
    return given
