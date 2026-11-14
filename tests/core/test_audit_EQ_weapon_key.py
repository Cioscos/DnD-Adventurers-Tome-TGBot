"""Audit EQ: un'arma presa dal catalogo SRD va riconosciuta per le maestrie 2024 (PHB 2024 p.215, colonna Mastery)
anche se il suo nome SRD non e' quello della tabella (Ascia = Handaxe, Crossbow, light, Stella del mattino)."""
from types import SimpleNamespace

import pytest

from core.rules.weapons import weapon_key, weapon_mastery


def _item(name: str, **meta):
    return SimpleNamespace(name=name, item_metadata=meta)


@pytest.mark.parametrize("name,index,key,mastery", [
    ("Ascia", "handaxe", "handaxe", "vex"),
    ("Crossbow, light", "crossbow-light", "light_crossbow", "slow"),
    ("Crossbow, hand", "crossbow-hand", "hand_crossbow", "vex"),
    ("Crossbow, heavy", "crossbow-heavy", "heavy_crossbow", "push"),
    ("Light hammer", "light-hammer", "light_hammer", "nick"),
    ("Spada del Vento", "war-pick", "war_pick", "sap"),
])
def test_srd_index_resolves_the_weapon(name, index, key, mastery):
    item = _item(name, srd_index=index)
    assert weapon_key(item) == key
    assert weapon_mastery(item) == mastery


def test_morningstar_srd_italian_name():
    assert weapon_key(_item("Stella del mattino")) == "morningstar"
