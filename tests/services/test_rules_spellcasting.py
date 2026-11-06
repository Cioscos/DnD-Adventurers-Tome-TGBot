"""Regole pure degli incantesimi per edizione. Valori dalle schede `docs/superpowers/rules/<anno>/classes/`."""
from __future__ import annotations

from types import SimpleNamespace as NS

import pytest

from core.rules.catalog.granted_spells import GRANTED_SPELLS, GrantedSpell
from core.rules.spellcasting import (
    KnownLimits,
    cast_warnings,
    concentration_dc,
    known_limits,
    prepared_limit,
    slots_for,
    spell_stats,
)


def _cls(name, level, ability=None, sub=None, id=1):
    return NS(id=id, class_name=name, level=level, spellcasting_ability=ability, subclass_key=sub)


def _score(name, value):
    return NS(name=name, value=value)


def _char(*classes, edition="2014", scores=(), items=(), abilities=(), profs=None, settings=None):
    return NS(rules_edition=edition, classes=list(classes), ability_scores=list(scores), items=list(items),
              proficiency_bonus=3, abilities=list(abilities), general_proficiencies=profs, active_states=[], turn_state=None,
              settings={"proficiencies_seeded": True} if settings is None else settings, spell_slots=[], conditions={})


def test_half_caster_rounding():
    classes = [_cls("paladin", 3), _cls("wizard", 1)]
    assert slots_for("2014", classes).regular == {1: 3}  # combinato 2
    assert slots_for("2024", classes).regular == {1: 4, 2: 2}  # combinato 3


def test_paladin_2024_has_slots_at_level_1():
    assert slots_for("2024", [_cls("Paladino", 1)]).regular == {1: 2}
    assert slots_for("2024", [_cls("ranger", 1)]).regular == {1: 2}
    assert slots_for("2014", [_cls("paladin", 1)]).regular == {}
    assert slots_for("2024", [_cls("paladin", 5)]).regular == slots_for("2014", [_cls("paladin", 5)]).regular == {1: 4, 2: 2}


def test_arcane_trickster_needs_subclass_key():
    assert slots_for("2024", [_cls("rogue", 3, sub="arcane_trickster")]).regular == {1: 2}
    assert slots_for("2014", [_cls("fighter", 3, sub="eldritch_knight")]).regular == {1: 2}
    assert slots_for("2024", [_cls("rogue", 3, ability="intelligence", sub="thief")]).regular == {}
    assert slots_for("2024", [_cls("rogue", 3)]).regular == {}


def test_existing_third_caster_without_catalog_subclass_keeps_slots():
    """Un PG già salvato con la caratteristica impostata non perde gli slot senza una sua scelta."""
    assert slots_for("2014", [_cls("rogue", 3, ability="intelligence")]).regular == {1: 2}
    assert slots_for("2024", [_cls("rogue", 3, ability="intelligence")]).regular == {1: 2}
    assert slots_for("2014", [_cls("rogue", 3, ability="intelligence", sub="thief")]).regular == {1: 2}


def test_third_caster_floor_in_both_editions():
    classes = [_cls("fighter", 5, sub="eldritch_knight"), _cls("wizard", 1)]
    assert slots_for("2014", classes).regular == slots_for("2024", classes).regular == {1: 3}  # 5//3 + 1


def test_pact_stays_apart():
    table = slots_for("2024", [_cls("warlock", 3), _cls("wizard", 1)])
    assert table.pact == {2: 2}
    assert table.regular == {1: 2}


@pytest.mark.parametrize("edition,key,level,expected", [
    ("2014", "bard", 1, KnownLimits(2, 4)),
    ("2014", "bard", 10, KnownLimits(4, 14)),
    ("2014", "sorcerer", 20, KnownLimits(6, 15)),
    ("2014", "warlock", 11, KnownLimits(4, 11)),
    ("2014", "ranger", 1, KnownLimits(0, 0)),
    ("2014", "ranger", 2, KnownLimits(0, 2)),
    ("2014", "cleric", 4, KnownLimits(4, None)),
    ("2014", "wizard", 10, KnownLimits(5, None)),
    ("2014", "druid", 1, KnownLimits(2, None)),
    ("2014", "paladin", 5, KnownLimits(0, None)),
    ("2014", "fighter", 3, KnownLimits(2, 3)),
    ("2014", "fighter", 19, KnownLimits(3, 12)),
    ("2014", "rogue", 3, KnownLimits(3, 3)),
    ("2014", "rogue", 10, KnownLimits(4, 7)),
    ("2024", "bard", 4, KnownLimits(3, None)),
    ("2024", "sorcerer", 10, KnownLimits(6, None)),
    ("2024", "paladin", 20, KnownLimits(0, None)),
    ("2024", "fighter", 10, KnownLimits(3, None)),
    ("2024", "barbarian", 5, KnownLimits(0, None)),
    ("2024", "unknown", 5, KnownLimits(0, None)),
])
def test_known_limits(edition, key, level, expected):
    assert known_limits(edition, key, level) == expected


@pytest.mark.parametrize("key,level,expected", [
    ("bard", 5, 9), ("cleric", 18, 20), ("druid", 20, 22),
    ("paladin", 1, 2), ("paladin", 17, 14), ("ranger", 9, 9),
    ("sorcerer", 2, 4), ("warlock", 9, 10), ("wizard", 16, 21), ("wizard", 20, 25),
])
def test_prepared_limit_2024_from_tables(key, level, expected):
    assert prepared_limit("2024", key, level, _char(_cls(key, level), edition="2024")) == expected


def test_prepared_limit_2024_third_caster_only_with_subclass():
    knight = _char(_cls("fighter", 3, sub="eldritch_knight"), edition="2024")
    assert prepared_limit("2024", "fighter", 3, knight) == 3
    assert prepared_limit("2024", "fighter", 20, _char(_cls("fighter", 20, sub="eldritch_knight"), edition="2024")) == 13
    assert prepared_limit("2024", "fighter", 3, _char(_cls("fighter", 3, sub="champion"), edition="2024")) == 0
    assert prepared_limit("2024", "barbarian", 5, _char(_cls("barbarian", 5), edition="2024")) == 0


def test_prepared_limit_2014_uses_modifier():
    char = _char(_cls("cleric", 5, "wisdom"), scores=[_score("wisdom", 16)])
    assert prepared_limit("2014", "cleric", 5, char) == 8
    paladin = _char(_cls("paladin", 5, "charisma"), scores=[_score("charisma", 18)])
    assert prepared_limit("2014", "paladin", 5, paladin) == 6
    assert prepared_limit("2014", "paladin", 1, paladin) == 0
    assert prepared_limit("2014", "bard", 5, _char(_cls("bard", 5, "charisma"))) == 0
    weak = _char(_cls("wizard", 1, "intelligence"), scores=[_score("intelligence", 6)])
    assert prepared_limit("2014", "wizard", 1, weak) == 1


@pytest.mark.parametrize("edition,damage,dc", [
    ("2014", 5, 10), ("2014", 30, 15), ("2014", 100, 50),
    ("2024", 5, 10), ("2024", 60, 30), ("2024", 100, 30),
])
def test_concentration_dc(edition, damage, dc):
    assert concentration_dc(edition, damage) == dc


def test_spell_stats_uses_class_then_best():
    wizard = _cls("wizard", 5, "intelligence", id=1)
    cleric = _cls("cleric", 5, "wisdom", id=2)
    char = _char(wizard, cleric, scores=[_score("intelligence", 18), _score("wisdom", 12)])
    assert spell_stats(char, NS(class_id=2)).save_dc == 8 + 3 + 1
    assert spell_stats(char, NS(class_id=2)).class_name == "cleric"
    # Non assegnato: il calcolo di sempre, la classe migliore.
    assert spell_stats(char, NS(class_id=None)).save_dc == 8 + 3 + 4
    # La classe assegnata non c'è più o non lancia incantesimi: non è un errore.
    assert spell_stats(char, NS(class_id=99)).class_name == "wizard"
    assert spell_stats(_char(_cls("fighter", 5)), NS(class_id=None)) is None


def test_third_caster_without_stored_ability_casts_with_intelligence():
    char = _char(_cls("rogue", 3, sub="arcane_trickster"), scores=[_score("intelligence", 16)])
    assert spell_stats(char, NS(class_id=None)).attack_bonus == 3 + 3


def _spell(**kw):
    base = dict(level=1, casting_time="1 azione", is_prepared=True, always_prepared=False, class_id=None, is_ritual=False,
                in_spellbook=True)
    return NS(**{**base, **kw})


def _worn(kind):
    return NS(item_type="armor", is_equipped=True, item_metadata={"armor_type": kind})


def test_cast_warnings_armor_without_training():
    wizard = _char(_cls("wizard", 5, "intelligence"), items=[_worn("heavy")], profs={"armor": ["light"]})
    assert "armor" in cast_warnings(wizard, _spell(), ritual=False)
    assert "armor" in cast_warnings(wizard, _spell(level=0), ritual=False)
    trained = _char(_cls("wizard", 5), items=[_worn("light")], profs={"armor": ["light"]})
    assert cast_warnings(trained, _spell(), ritual=False) == []
    pending_seed = _char(_cls("wizard", 5), items=[_worn("heavy")], profs={"armor": []}, settings={})
    assert cast_warnings(pending_seed, _spell(), ritual=False) == []  # competenze vuote non seminate


def test_cast_warnings_shield_blocks_only_in_2014():
    shield = NS(item_type="shield", is_equipped=True, item_metadata={})
    profs = {"armor": ["light"]}
    assert "armor" in cast_warnings(_char(_cls("wizard", 5), items=[shield], profs=profs), _spell(), ritual=False)
    assert cast_warnings(_char(_cls("wizard", 5), edition="2024", items=[shield], profs=profs),
                         _spell(), ritual=False) == []


def test_cast_warnings_slot_per_turn_by_edition():
    c2024 = _char(_cls("wizard", 5), edition="2024")
    c2024.turn_state = {"spell_slot_cast": True}
    assert cast_warnings(c2024, _spell(), ritual=False) == ["one_slot_per_turn"]
    assert cast_warnings(c2024, _spell(level=0), ritual=False) == []
    assert cast_warnings(c2024, _spell(), ritual=True) == []
    assert cast_warnings(c2024, _spell(casting_time="1 reazione"), ritual=False) == []

    c2014 = _char(_cls("wizard", 5))
    c2014.turn_state = {"spell_slot_cast": True}
    assert cast_warnings(c2014, _spell(), ritual=False) == []  # Azione Impetuosa: due incantesimi d'azione
    assert cast_warnings(c2014, _spell(casting_time="1 bonus action"), ritual=False) == ["bonus_spell"]
    c2014.turn_state = {"bonus_spell_cast": True}
    assert cast_warnings(c2014, _spell(), ritual=False) == ["bonus_spell"]
    assert cast_warnings(c2014, _spell(level=0), ritual=False) == []
    assert cast_warnings(c2014, _spell(level=0, casting_time="1 azione bonus"), ritual=False) == ["bonus_spell"]


def test_cast_warnings_ritual_preparation():
    unprepared = _spell(is_prepared=False, is_ritual=True)
    assert cast_warnings(_char(_cls("cleric", 5)), unprepared, ritual=True) == ["ritual_unprepared"]
    assert cast_warnings(_char(_cls("wizard", 5)), unprepared, ritual=True) == []  # dal libro
    outside = _spell(is_prepared=False, is_ritual=True, in_spellbook=False)  # 2014: un rituale fuori dal libro si conferma
    assert cast_warnings(_char(_cls("wizard", 5)), outside, ritual=True) == ["ritual_unprepared"]
    assert cast_warnings(_char(_cls("bard", 5)), unprepared, ritual=True) == []  # 2014: li conosce
    assert cast_warnings(_char(_cls("bard", 5), edition="2024"), unprepared, ritual=True) == ["ritual_unprepared"]
    assert cast_warnings(_char(_cls("wizard", 5), edition="2024"), unprepared, ritual=True) == []
    assert cast_warnings(_char(_cls("cleric", 5)), _spell(is_ritual=True), ritual=True) == []


def test_granted_spells_are_a_mechanical_minimum():
    """D4: dati nostri, solo per gli incantesimi concessi dai privilegi, i Task 19-42 riempiono il dizionario."""
    assert isinstance(GRANTED_SPELLS, dict)
    spell = GrantedSpell(key="prova", name={"it": "Prova", "en": "Test"}, level=1)
    assert (spell.is_concentration, spell.is_ritual, spell.damage_dice) == (False, False, None)


def test_caster_stats_skips_a_class_that_does_not_cast_in_its_edition():
    from core.rules.spellcasting import caster_stats
    scores = (_score("intelligence", 16),)
    champion = _cls("fighter", 5, ability="intelligence", sub="champion")
    knight = _cls("fighter", 5, ability="intelligence", sub="eldritch_knight", id=2)
    custom = _cls("Artificiere Homebrew", 5, ability="intelligence", id=3)
    stats = caster_stats(_char(champion, knight, custom, edition="2024", scores=scores))
    assert [s.class_id for s in stats] == [2, 3]
    # 2014: la caratteristica salvata tiene gli slot dei personaggi esistenti, e con loro CD e select (stessa regola)
    assert [s.class_id for s in caster_stats(_char(champion, edition="2014", scores=scores))] == [1]
