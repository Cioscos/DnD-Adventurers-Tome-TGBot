"""Ogni incantesimo concesso ha la sua scuola, e quella del 2024 dove cambia."""
from core.rules.catalog.granted_spells import GRANTED_SPELLS, granted_spell


def test_every_granted_spell_has_a_school():
    assert [k for k, s in GRANTED_SPELLS.items() if not s.school] == []


def test_school_follows_the_edition():
    assert granted_spell("cure-wounds", "2014").school == "evocation"
    assert granted_spell("cure-wounds", "2024").school == "abjuration"
    assert granted_spell("sleep", "2024").school == "enchantment"
