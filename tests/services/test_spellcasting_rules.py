"""Unit test delle regole 5e di preparazione incantesimi e ritual casting.

Regole codificate (PHB 2014):
- Preparano: Chierico/Druido (SAG), Mago (INT) -> max(1, mod + livello);
  Paladino (CAR) -> max(1, mod + livello // 2), ma SOLO dal livello 2.
- Tetto aggregato multiclasse = somma dei contributi delle classi preparanti.
- spellcasting_ability NULL -> fallback al default di classe.
- Ritual Casting: Bardo, Chierico, Druido, Mago. has_wizard esposto a parte.
"""
from __future__ import annotations

from core.data.spellcasting import (
    compute_prepared_cap,
    has_preparing_class,
    has_ritual_caster,
    has_wizard,
)
from core.db.models import CharacterClass


def _cls(name: str, level: int, ability: str | None = None) -> CharacterClass:
    return CharacterClass(class_name=name, level=level, spellcasting_ability=ability)


# --- compute_prepared_cap ---------------------------------------------------

def test_cleric_cap_is_wis_mod_plus_level():
    cap = compute_prepared_cap([_cls("cleric", 5, "wisdom")], {"wisdom": 3})
    assert cap == 8


def test_wizard_negative_mod_floors_at_one():
    cap = compute_prepared_cap([_cls("wizard", 1, "intelligence")], {"intelligence": -1})
    assert cap == 1


def test_paladin_uses_half_level():
    cap = compute_prepared_cap([_cls("paladin", 5, "charisma")], {"charisma": 4})
    assert cap == 6  # 4 + 5 // 2


def test_paladin_level_1_does_not_prepare():
    assert compute_prepared_cap([_cls("paladin", 1, "charisma")], {"charisma": 4}) is None
    assert has_preparing_class([_cls("paladin", 1, "charisma")]) is False


def test_multiclass_cap_is_sum_of_contributions():
    classes = [_cls("cleric", 5, "wisdom"), _cls("wizard", 3, "intelligence")]
    cap = compute_prepared_cap(classes, {"wisdom": 3, "intelligence": 2})
    assert cap == 13  # (3+5) + (2+3)


def test_null_ability_falls_back_to_class_default():
    cap = compute_prepared_cap([_cls("cleric", 4, None)], {"wisdom": 2})
    assert cap == 6


def test_italian_class_names_are_recognized():
    cap = compute_prepared_cap([_cls("Chierico", 4, None)], {"wisdom": 0})
    assert cap == 4


def test_known_caster_only_has_no_cap():
    assert compute_prepared_cap([_cls("bard", 5, "charisma")], {"charisma": 3}) is None
    assert has_preparing_class([_cls("bard", 5, "charisma")]) is False


def test_missing_modifier_defaults_to_zero():
    assert compute_prepared_cap([_cls("wizard", 3, "intelligence")], {}) == 3


# --- ritual flags -----------------------------------------------------------

def test_ritual_casters():
    assert has_ritual_caster([_cls("bard", 1)]) is True
    assert has_ritual_caster([_cls("Chierico", 1)]) is True
    assert has_ritual_caster([_cls("sorcerer", 5)]) is False
    assert has_ritual_caster([_cls("paladin", 5)]) is False


def test_has_wizard():
    assert has_wizard([_cls("Mago", 2)]) is True
    assert has_wizard([_cls("cleric", 2)]) is False
