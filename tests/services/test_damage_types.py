"""core.data.damage_types: normalizzazione tipi e moltiplicatore."""
import pytest

from core.data.damage_types import DAMAGE_TYPES, canonical_damage_type, damage_multiplier


def test_thirteen_slugs():
    assert len(DAMAGE_TYPES) == 13 and len(set(DAMAGE_TYPES)) == 13


@pytest.mark.parametrize("raw", ["Fuoco", "fire", "dmg_fire", " FIRE ", "Fire", "dmg_Fuoco"])
def test_canonical_accepts_all_forms(raw):
    assert canonical_damage_type(raw) == "fire"


@pytest.mark.parametrize("raw,slug", [
    ("Taglio", "slashing"), ("Tagliente", "slashing"), ("Perforazione", "piercing"),
    ("Radiante", "radiant"), ("Radioso", "radiant"), ("Tuono", "thunder"),
])
def test_canonical_italian_labels(raw, slug):
    assert canonical_damage_type(raw) == slug


@pytest.mark.parametrize("raw", [None, "", "Danni non magici", 5])
def test_canonical_unknown_is_none(raw):
    assert canonical_damage_type(raw) is None


def test_every_slug_round_trips():
    for s in DAMAGE_TYPES:
        assert canonical_damage_type(s) == s
        assert canonical_damage_type(f"dmg_{s}") == s


def test_multiplier_each_kind():
    mods = {"resistances": ["Fuoco"], "immunities": ["cold"], "vulnerabilities": ["dmg_acid"]}
    assert damage_multiplier(mods, "fire") == "half"
    assert damage_multiplier(mods, "cold") == "immune"
    assert damage_multiplier(mods, "acid") == "double"
    assert damage_multiplier(mods, "force") == "none"
    assert damage_multiplier(mods, None) == "none"
    assert damage_multiplier(None, "fire") == "none"


def test_resistance_plus_vulnerability_cancel():
    assert damage_multiplier({"resistances": ["fire"], "vulnerabilities": ["Fuoco"]}, "fire") == "none"


def test_immunity_wins():
    assert damage_multiplier({"resistances": ["fire"], "immunities": ["fire"]}, "fire") == "immune"
