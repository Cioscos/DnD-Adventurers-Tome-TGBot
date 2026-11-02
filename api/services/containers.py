"""Moving items between containers and re-parenting contents when a container goes away."""
from __future__ import annotations

import json

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.services.equipment import apply_equip_ac
from core.db.models import Currency, Item
from core.game.containers import COINS, allocate, container_coins, is_container, would_cycle
from core.game.item_bonuses import item_meta


async def reparent_contents(session: AsyncSession, char, container: Item) -> None:
    """Children go to the container's parent; its coins go to that parent (or the purse).

    Always re-parenting keeps the invariant that no item points to a missing/non-container
    parent (SQLite-migrated DBs lack the ON DELETE SET NULL FK).
    """
    parent = next((i for i in char.items if i.id == container.container_id and is_container(i)), None)
    for it in char.items:
        if it.container_id == container.id:
            it.container_id = container.container_id
    coins = container_coins(container)
    if not any(coins.values()):
        return
    if parent is not None:
        md = item_meta(parent)
        md["container"]["coins"] = {c: container_coins(parent)[c] + coins[c] for c in COINS}
        parent.item_metadata = json.dumps(md)
        return
    if char.currency is None:
        char.currency = Currency(character_id=char.id)
    for c in COINS:
        setattr(char.currency, c, (getattr(char.currency, c) or 0) + coins[c])


async def move_items(
    session: AsyncSession, char, item_ids: list[int], container_id: int | None, quantity: int | None
) -> list[str]:
    """Move items into a container (None = loose). Returns names pulled off the paper-doll."""
    by_id = {i.id: i for i in char.items}
    if any(i not in by_id for i in item_ids):
        raise HTTPException(status_code=404, detail="Item not found")
    if container_id is not None:
        target = by_id.get(container_id)
        if target is None:
            raise HTTPException(status_code=404, detail="Container not found")
        if not is_container(target):
            raise HTTPException(status_code=422, detail="not_a_container")
        if would_cycle(char.items, set(item_ids), container_id):
            raise HTTPException(status_code=422, detail="container_cycle")
    if quantity is not None and not 1 <= quantity < by_id[item_ids[0]].quantity:
        raise HTTPException(status_code=422, detail="invalid_quantity")

    unequipped: list[str] = []
    for iid in item_ids:
        item = by_id[iid]
        if item.is_equipped and container_id is not None:
            item.is_equipped, item.equipment_slot = False, None
            apply_equip_ac(char, item)
            unequipped.append(item.name)
        same = next((
            o for o in char.items
            if o is not item and o.item_type == "generic" and item.item_type == "generic"
            and not is_container(o) and not is_container(item)
            and o.name == item.name and o.container_id == container_id
        ), None)
        if quantity is not None:
            item.quantity -= quantity
            if same is not None:
                same.quantity += quantity
            else:
                session.add(Item(
                    character_id=char.id, name=item.name, description=item.description,
                    weight=item.weight, quantity=quantity, item_type=item.item_type,
                    item_metadata=item.item_metadata, container_id=container_id,
                ))
        elif same is not None:
            same.quantity += item.quantity
            await session.delete(item)
        else:
            item.container_id = container_id
    await session.flush()
    return unequipped


def _coin_places(char) -> dict[int | None, dict]:
    """Coin dicts by location: purse (None) plus every container."""
    places: dict[int | None, dict] = {None: {c: getattr(char.currency, c) or 0 for c in COINS} if char.currency else dict.fromkeys(COINS, 0)}
    places.update({i.id: container_coins(i) for i in char.items if is_container(i)})
    return places


def apply_coin_placements(char, coin: str, placements: list[tuple[int | None, int]]) -> list[tuple[int | None, int]]:
    """Apply per-location coin changes all-or-nothing; returns the effective placements.

    A positive amount for a location that no longer exists goes to the purse; a withdrawal
    from one is insufficient_funds.
    """
    places = _coin_places(char)
    eff: dict[int | None, int] = {}
    for loc, amt in placements:
        if loc not in places:
            if amt < 0:
                raise HTTPException(status_code=409, detail="insufficient_funds")
            loc = None
        eff[loc] = eff.get(loc, 0) + amt
    if any(places[loc][coin] + amt < 0 for loc, amt in eff.items()):
        raise HTTPException(status_code=409, detail="insufficient_funds")
    by_id = {i.id: i for i in char.items}
    for loc, amt in eff.items():
        if loc is None:
            if char.currency is None:
                char.currency = Currency(character_id=char.id)
            setattr(char.currency, coin, places[None][coin] + amt)
        else:
            md = item_meta(by_id[loc])
            md["container"]["coins"] = {**places[loc], coin: places[loc][coin] + amt}
            by_id[loc].item_metadata = json.dumps(md)
    return [(loc, amt) for loc, amt in eff.items() if amt]


def withdraw(char, coin: str, amount: int) -> list[tuple[int | None, int]]:
    """Take coins from the purse then containers (409 insufficient_funds)."""
    purse = {c: getattr(char.currency, c) or 0 for c in COINS} if char.currency else {}
    try:
        placements = allocate(purse, char.items, coin, -amount)
    except ValueError:
        raise HTTPException(status_code=409, detail="insufficient_funds")
    return apply_coin_placements(char, coin, placements)
