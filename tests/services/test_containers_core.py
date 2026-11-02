import json
from types import SimpleNamespace as NS

import pytest

from core.game.containers import (
    allocate, carried_weight, children_index, container_stats, would_cycle,
)


def it(id, weight=0, qty=1, parent=None, container=None):
    meta = {"container": container} if container is not None else {}
    return NS(id=id, container_id=parent, weight=weight, quantity=qty, item_metadata=json.dumps(meta))


def cont(id, weight=0, parent=None, counts=True, cap=None, **coins):
    return it(id, weight, 1, parent, {"capacity_lb": cap, "counts_weight": counts, "coins": coins})


def test_carried_weight_nested():
    items = [cont(1, 5), it(2, 10, parent=1), cont(3, 1, parent=1), it(4, 0.1, 3, parent=3), it(5, 3)]
    assert carried_weight(items, {}, False) == pytest.approx(19.3)


def test_carried_weight_weightless_bag():
    items = [cont(1, 15, counts=False), it(2, 100, parent=1), cont(3, 5, parent=1)]
    assert carried_weight(items, {}, False) == pytest.approx(15)


def test_coins_weight():
    items = [cont(1, 0, gold=50), cont(2, 0, counts=False, gold=500)]
    assert carried_weight(items, {"gold": 100}, True) == pytest.approx(3.0)
    assert carried_weight(items, {"gold": 100}, False) == 0


def test_stats_capacity_ignores_flag():
    items = [cont(1, 0, counts=False, cap=500, gold=500), it(2, 480, parent=1)]
    s = container_stats(items)[1]
    assert s.contents_weight == pytest.approx(490) and not s.over_capacity
    items[1].weight = 491
    assert container_stats(items)[1].over_capacity is True
    items[0].item_metadata = json.dumps({"container": {"capacity_lb": None, "coins": {"gold": 500}}})
    assert container_stats(items)[1].over_capacity is False
    assert container_stats(items)[1].items_count == 1


def test_would_cycle():
    items = [cont(1), cont(2, parent=1)]
    assert would_cycle(items, {1}, 2)
    assert would_cycle(items, {1, 2}, 1)
    assert not would_cycle(items, {2}, None)


def test_dangling_parent_is_root():
    assert [i.id for i in children_index([it(1, parent=999)])[None]] == [1]


def test_allocate_order():
    items = [cont(5, gold=3), cont(3, gold=10)]
    assert allocate({"gold": 2}, items, "gold", -6) == [(None, -2), (3, -4)]
    assert allocate({"gold": 2}, items, "gold", 4) == [(None, 4)]
    with pytest.raises(ValueError, match="insufficient_funds"):
        allocate({"gold": 2}, items, "gold", -20)
