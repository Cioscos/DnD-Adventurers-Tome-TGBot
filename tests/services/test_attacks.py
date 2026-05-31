"""Unit tests for core.game.attacks (pure unarmed-strike rules, no DB)."""
from __future__ import annotations

import pytest

from core.game.attacks import martial_arts_die, unarmed_strike_profile


@pytest.mark.parametrize("level,expected", [
    (1, "1d4"), (4, "1d4"),
    (5, "1d6"), (10, "1d6"),
    (11, "1d8"), (16, "1d8"),
    (17, "1d10"), (20, "1d10"),
])
def test_martial_arts_die_scaling(level, expected):
    assert martial_arts_die(level) == expected


def test_martial_arts_die_zero_for_non_monk_level():
    assert martial_arts_die(0) == ""


def test_non_monk_uses_strength_and_flat_one():
    ability_mod, dice = unarmed_strike_profile(str_mod=3, dex_mod=1, monk_level=0)
    assert ability_mod == 3
    assert dice == "1"


def test_monk_uses_best_of_str_dex_and_martial_die():
    ability_mod, dice = unarmed_strike_profile(str_mod=1, dex_mod=4, monk_level=5)
    assert ability_mod == 4
    assert dice == "1d6"


def test_monk_low_level_die():
    ability_mod, dice = unarmed_strike_profile(str_mod=2, dex_mod=0, monk_level=3)
    assert ability_mod == 2
    assert dice == "1d4"
