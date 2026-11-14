"""Audit classi 2024 (paladino): il destriero di Trova Destriero 2024 (spell p.272) ha Volo 18 m dal 4° livello."""
from __future__ import annotations

from types import SimpleNamespace

from core.rules.catalog.y2024.paladin import make_steed


def _steed(level: int) -> dict:
    char = SimpleNamespace(id=1, companions=[])
    make_steed(char, "Fulmine", level)
    return char.companions[0].statblock


def test_find_steed_2024_p272_flies_at_18_m_from_slot_4():
    assert "fly_speed_ft" not in _steed(2) and _steed(4)["fly_speed_ft"] == 60
