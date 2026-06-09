"""Unit tests for core.game.stats — pure D&D 5e derived-attribute math.

No DB, no side effects. These functions are the foundation under HP recalc,
AC, ability modifiers and the multiclass HP formula, so the oracle here is the
PHB rule, asserted exactly (including Python floor-division on negative mods).
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.game.stats import (
    ability_modifier,
    effective_ability_score,
    hit_points_for_level,
    total_base_hp,
    unarmored_defense_ac,
)


# --- ability_modifier -------------------------------------------------------

@pytest.mark.parametrize("score,expected", [
    (10, 0), (11, 0),       # 10–11 → +0
    (12, 1), (13, 1),
    (8, -1), (9, -1),
    (1, -5),                # floor((1-10)/2) = floor(-4.5) = -5
    (3, -4),                # floor(-7/2) = -4
    (7, -2),                # floor(-3/2) = -2
    (20, 5),
    (30, 10),
])
def test_ability_modifier_floor_division(score, expected):
    assert ability_modifier(score) == expected


# --- hit_points_for_level ---------------------------------------------------

def test_hp_level1_uses_max_die_plus_con():
    # Level 1: hit_die + con_mod (PHB max value).
    assert hit_points_for_level(10, 2, 1) == 12
    assert hit_points_for_level(8, 0, 1) == 8


def test_hp_level2plus_uses_fixed_method():
    # Level 2+: hit_die // 2 + 1 + con_mod.
    assert hit_points_for_level(10, 2, 2) == 8     # 5 + 1 + 2
    assert hit_points_for_level(8, 0, 5) == 5      # 4 + 1 + 0
    assert hit_points_for_level(6, 1, 3) == 5      # 3 + 1 + 1


def test_hp_clamped_to_minimum_one():
    # Even with very negative CON a level grants at least 1 HP.
    assert hit_points_for_level(6, -20, 1) == 1
    assert hit_points_for_level(6, -5, 2) == 1     # (3+1) - 5 = -1 → clamp 1


def test_hp_rejects_bad_inputs():
    with pytest.raises(ValueError):
        hit_points_for_level(10, 0, 0)
    with pytest.raises(ValueError):
        hit_points_for_level(0, 0, 1)


# --- unarmored_defense_ac ---------------------------------------------------

@pytest.mark.parametrize("dex,second,expected", [
    (0, 0, 10),
    (3, 2, 15),     # Barbarian DEX+3 CON+2
    (4, 3, 17),     # Monk DEX+4 WIS+3
    (-1, 4, 13),
])
def test_unarmored_defense_ac(dex, second, expected):
    assert unarmored_defense_ac(dex, second) == expected


# --- total_base_hp ----------------------------------------------------------

def _cls(id_: int, level: int, hit_die: int):
    return SimpleNamespace(id=id_, level=level, hit_die=hit_die)


def test_total_base_hp_empty_is_zero():
    assert total_base_hp([], 0) == 0


def test_total_base_hp_single_class():
    # d10 L1 CON 0 → 10. d10 L2 → 10 + (5+1) = 16.
    assert total_base_hp([_cls(1, 1, 10)], 0) == 10
    assert total_base_hp([_cls(1, 2, 10)], 0) == 16


def test_total_base_hp_multiclass_first_class_owns_level1():
    # Fighter(id1,d10,L2) + Rogue(id2,d8,L1), CON 0:
    # id1 L1 = 10, id1 L2 = 6, id2 L1 (treated as 2+) = 5 → 21.
    classes = [_cls(1, 2, 10), _cls(2, 1, 8)]
    assert total_base_hp(classes, 0) == 21


def test_total_base_hp_lowest_id_owns_level1_regardless_of_order():
    # Passed out of order; lowest id (the d10 fighter) must own the L1 slot.
    rogue = _cls(2, 1, 8)
    fighter = _cls(1, 1, 10)
    # fighter L1 = 10 (max die), rogue L1 as 2+ = 8//2+1 = 5 → 15.
    assert total_base_hp([rogue, fighter], 0) == 15
    # If the rogue had wrongly owned L1 it would be 8 + 6 = 14.


def test_total_base_hp_applies_con_per_level():
    # d8 L2 CON +1: L1 = 8+1 = 9, L2 = (4+1)+1 = 6 → 15.
    assert total_base_hp([_cls(1, 2, 8)], 1) == 15


# --- effective_ability_score ------------------------------------------------

def _item(id_: int, name: str, metadata):
    return SimpleNamespace(id=id_, name=name, item_metadata=metadata)


def test_effective_no_items_returns_base():
    eff, applied = effective_ability_score("strength", 14, [])
    assert eff == 14
    assert applied == []


def test_effective_relative_modifiers_sum():
    items = [
        _item(1, "Cintura", {"ability_modifiers": [
            {"ability": "strength", "kind": "relative", "value": 2}]}),
        _item(2, "Anello", {"ability_modifiers": [
            {"ability": "strength", "kind": "relative", "value": 1}]}),
    ]
    eff, applied = effective_ability_score("strength", 14, items)
    assert eff == 17                  # 14 + 2 + 1
    assert len(applied) == 2


def test_effective_absolute_is_a_floor_not_a_bonus():
    # Absolute 18 with base 14 → 18; absolute 12 with base 14 → 14 (never lowers).
    high = _item(1, "Manuale", {"ability_modifiers": [
        {"ability": "strength", "kind": "absolute", "value": 18}]})
    low = _item(2, "Manuale", {"ability_modifiers": [
        {"ability": "strength", "kind": "absolute", "value": 12}]})
    assert effective_ability_score("strength", 14, [high])[0] == 18
    assert effective_ability_score("strength", 14, [low])[0] == 14


def test_effective_absolute_combines_with_relative():
    items = [
        _item(1, "Manuale", {"ability_modifiers": [
            {"ability": "strength", "kind": "absolute", "value": 18}]}),
        _item(2, "Cintura", {"ability_modifiers": [
            {"ability": "strength", "kind": "relative", "value": 2}]}),
    ]
    # base+rel = 16, max(16, 18) = 18.
    assert effective_ability_score("strength", 14, items)[0] == 18


def test_effective_ignores_other_abilities_and_bad_values():
    items = [
        _item(1, "Anello", {"ability_modifiers": [
            {"ability": "dexterity", "kind": "relative", "value": 4},      # other ability
            {"ability": "strength", "kind": "relative", "value": "x"},     # non-int
            {"ability": "strength", "kind": "relative", "value": 2}]}),
    ]
    eff, applied = effective_ability_score("strength", 10, items)
    assert eff == 12
    assert len(applied) == 1


def test_effective_parses_json_string_metadata():
    item = _item(1, "Cintura",
                 '{"ability_modifiers": [{"ability": "strength", "kind": "relative", "value": 4}]}')
    assert effective_ability_score("strength", 10, [item])[0] == 14


def test_effective_unknown_ability_raises():
    with pytest.raises(ValueError):
        effective_ability_score("luck", 10, [])
