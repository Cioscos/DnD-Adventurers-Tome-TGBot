"""Pure container-tree logic (duck-typed items: id, container_id, weight, quantity, item_metadata)."""
from collections import defaultdict
from dataclasses import dataclass

from core.game.item_bonuses import item_meta

COINS: tuple[str, ...] = ("copper", "silver", "electrum", "gold", "platinum")
COINS_PER_LB = 50


def container_meta(item) -> dict | None:
    c = item_meta(item).get("container")
    return c if isinstance(c, dict) else None


def is_container(item) -> bool:
    return container_meta(item) is not None


def children_index(items) -> dict:
    container_ids = {i.id for i in items if is_container(i)}
    idx: dict = defaultdict(list)
    for i in sorted(items, key=lambda i: i.id or 0):
        parent = i.container_id if i.container_id in container_ids else None
        idx[parent].append(i)
    # Corrupt data: members of an unreachable parent cycle are promoted to root so the index is a forest.
    seen: set[int] = set()
    stack = [None]

    def mark() -> None:
        while stack:
            for c in idx.get(stack.pop(), []):
                if id(c) not in seen:
                    seen.add(id(c))
                    stack.append(c.id)

    mark()
    for i in sorted(items, key=lambda i: i.id or 0):
        if id(i) not in seen:
            idx[i.container_id].remove(i)
            idx[None].append(i)
            seen.add(id(i))
            stack.append(i.id)
            mark()
    return idx


def descendant_ids(items, container_id: int) -> set[int]:
    idx = children_index(items)
    out: set[int] = set()
    stack = [container_id]
    while stack:
        for c in idx.get(stack.pop(), []):
            if c.id not in out:
                out.add(c.id)
                stack.append(c.id)
    return out


def would_cycle(items, moving_ids: set[int], target_id: int | None) -> bool:
    if target_id is None:
        return False
    return target_id in moving_ids or any(target_id in descendant_ids(items, m) for m in moving_ids)


def container_coins(item) -> dict[str, int]:
    raw = (container_meta(item) or {}).get("coins")
    raw = raw if isinstance(raw, dict) else {}
    return {c: int(raw.get(c) or 0) for c in COINS}


def _own(item) -> float:
    return (item.weight or 0) * (1 if item.quantity is None else item.quantity)


def carried_weight(items, purse_coins: dict, coin_weight: bool) -> float:
    idx = children_index(items)

    def walk(parent) -> float:
        total = 0.0
        for c in idx.get(parent, []):
            total += _own(c)
            m = container_meta(c)
            if m is not None and m.get("counts_weight", True):
                total += walk(c.id)
                if coin_weight:
                    total += sum(container_coins(c).values()) / COINS_PER_LB
        return total

    total = walk(None)
    if coin_weight:
        total += sum(int(purse_coins.get(c) or 0) for c in COINS) / COINS_PER_LB
    return total


@dataclass
class ContainerStats:
    contents_weight: float
    items_count: int
    containers_count: int
    over_capacity: bool


def container_stats(items) -> dict[int, ContainerStats]:
    idx = children_index(items)

    def contents(c) -> float:
        total = sum(container_coins(c).values()) / COINS_PER_LB
        for ch in idx.get(c.id, []):
            total += _own(ch) + (contents(ch) if is_container(ch) else 0)
        return total

    out = {}
    for c in items:
        if not is_container(c):
            continue
        kids = idx.get(c.id, [])
        w = contents(c)
        cap = container_meta(c).get("capacity_lb")
        out[c.id] = ContainerStats(
            w,
            sum(1 for k in kids if not is_container(k)),
            sum(1 for k in kids if is_container(k)),
            cap is not None and w > cap,
        )
    return out


def coin_locations(items) -> list[int]:
    idx = children_index(items)
    out: list[int] = []

    def walk(parent) -> None:
        for c in idx.get(parent, []):
            if is_container(c):
                out.append(c.id)
                walk(c.id)

    walk(None)
    return out


def allocate(purse: dict, items, coin: str, delta: int) -> list[tuple[int | None, int]]:
    if coin not in COINS:
        raise ValueError("invalid_coin")
    if delta >= 0:
        return [(None, delta)]
    by_id = {i.id: i for i in items}
    need = -delta
    out: list[tuple[int | None, int]] = []
    sources = [(None, int(purse.get(coin) or 0))] + [
        (cid, container_coins(by_id[cid])[coin]) for cid in coin_locations(items)
    ]
    for loc, have in sources:
        take = min(have, need)
        if take > 0:
            out.append((loc, -take))
            need -= take
    if need > 0:
        raise ValueError("insufficient_funds")
    return out


def trade_snapshot(items, root_id: int, quantity: int) -> dict:
    """Name/quantity/coins tree of `root_id` (children in inventory order), for trade records."""
    idx = children_index(items)
    by_id = {i.id: i for i in items}

    def node(item, qty) -> dict:
        coins = {c: n for c, n in container_coins(item).items() if n > 0} if is_container(item) else {}
        return {"name": item.name, "quantity": qty, "coins": coins or None,
                "children": [node(c, c.quantity) for c in idx.get(item.id, [])]}

    return node(by_id[root_id], quantity)
