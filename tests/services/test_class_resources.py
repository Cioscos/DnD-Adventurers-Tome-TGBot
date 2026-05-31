"""Unit tests for core.data.classes.update_resources_for_level.

The function mutates ClassResource-like objects in place; it only touches
.name / .current / .total, so plain SimpleNamespace stubs are enough — no DB.
"""
from __future__ import annotations

from types import SimpleNamespace

from core.data.classes import update_resources_for_level


def _ki(current: int, total: int) -> SimpleNamespace:
    """A stub resource matching a Monk's 'Punti Ki' entry."""
    return SimpleNamespace(name="Punti Ki", current=current, total=total)


def test_levelup_raises_current_by_gained_amount():
    res = _ki(current=3, total=4)
    update_resources_for_level("Monaco", 5, [res])
    assert res.total == 5
    assert res.current == 4  # spent stays spent, gained capacity is available


def test_levelup_from_full_stays_full():
    res = _ki(current=4, total=4)
    update_resources_for_level("Monaco", 5, [res])
    assert res.total == 5
    assert res.current == 5


def test_levelup_caps_current_at_new_total():
    res = _ki(current=9, total=4)
    update_resources_for_level("Monaco", 5, [res])
    assert res.total == 5
    assert res.current == 5


def test_level_decrease_caps_current_down():
    res = _ki(current=5, total=5)
    update_resources_for_level("Monaco", 3, [res])
    assert res.total == 3
    assert res.current == 3


def test_level_decrease_leaves_lower_current_untouched():
    res = _ki(current=1, total=5)
    update_resources_for_level("Monaco", 3, [res])
    assert res.total == 3
    assert res.current == 1


def test_no_negative_total_below_availability():
    res = _ki(current=2, total=2)
    update_resources_for_level("Monaco", 1, [res])
    assert res.total == 0
    assert res.current == 0


def test_barbarian_unlimited_rage_sentinel_does_not_inflate_current():
    # _BARBARO_FURIE[19] == 99 (unlimited). Leveling 19 -> 20 must NOT raise
    # current by the (absurd) delta; total becomes the sentinel, current stays.
    res = SimpleNamespace(name="Furia", current=3, total=6)
    update_resources_for_level("Barbaro", 20, [res])
    assert res.total == 99
    assert res.current == 3


def test_cha_based_resource_is_left_untouched():
    # Bardo's Ispirazione Bardica is cha_based=True -> the function must skip it
    # entirely (no total/current recalculation from the level formula).
    res = SimpleNamespace(name="Ispirazione Bardica", current=2, total=3)
    update_resources_for_level("Bardo", 10, [res])
    assert res.total == 3
    assert res.current == 2
