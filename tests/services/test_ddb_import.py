"""Convertitore D&D Beyond -> CharacterExport: valori del PG reale (riscontrati sul PDF DDB) e robustezza."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from api.services.ddb_import import DdbImportError, convert

_FIXTURE = Path(__file__).parents[1] / "fixtures" / "ddb" / "cleric19.json"


def load() -> dict:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def data() -> dict:
    return load()["data"]


def test_fixture_core_values():
    exp, rep, uses = convert(load())
    scores = {a.name: a.value for a in exp.ability_scores}
    assert scores == {"strength": 29, "dexterity": 11, "constitution": 20,
                      "intelligence": 10, "wisdom": 21, "charisma": 12}
    assert exp.character.hit_points == 212
    assert exp.character.current_hit_points == 212 - 42
    assert [(c.class_name, c.level, c.subclass, c.hit_die) for c in exp.classes] == [
        ("Chierico", 19, "Tempest Domain", 8)]
    assert exp.classes[0].spellcasting_ability == "wisdom"
    assert exp.character.race == "Hill Dwarf" and exp.character.speed == 25
    assert exp.character.experience_points == 305000
    assert exp.currency.gold == 2733 and exp.currency.silver == 491 and exp.currency.copper == 24
    assert exp.character.saving_throws == {"wisdom": True, "charisma": True}
    assert exp.character.skills["medicine"] is True and exp.character.skills["persuasion"] is True
    assert "poison" in exp.character.damage_modifiers["resistances"]
    assert exp.character.spell_slots_mode == "automatic"
    assert {"Common", "Dwarvish"} <= set(exp.character.languages)
    assert "Heavy Armor" in exp.character.general_proficiencies["armor"]


def test_class_name_follows_language():  # come il wizard: nome localizzato
    assert convert(load(), lang="en")[0].classes[0].class_name == "Cleric"
    assert convert(load(), lang="it")[0].classes[0].class_name == "Chierico"


def test_fixture_items_and_ac():
    exp, rep, _ = convert(load())
    by_name = {i.name: i for i in exp.items}
    chain = by_name["Chain Mail"]
    assert chain.item_type == "armor" and chain.is_equipped and chain.equipment_slot.value == "body"
    assert chain.item_metadata["ac_value"] == 16 and chain.item_metadata["armor_type"] == "heavy"
    shield = by_name["Shield"]
    assert shield.item_type == "shield" and shield.equipment_slot.value == "off_hand"
    assert exp.character.base_armor_class == 16 and exp.character.shield_armor_class == 2
    assert exp.character.magic_armor == 3  # characterValues typeId 2
    cloak = by_name["Cloak of Protection"]
    assert cloak.item_metadata["attuned"] is True and cloak.equipment_slot.value == "cloak"
    assert {"target": "ac", "value": 1} in cloak.item_metadata["bonuses"]
    assert {"target": "saves", "value": 1} in cloak.item_metadata["bonuses"]
    halberd = by_name["Halberd, +2"]
    assert halberd.item_type == "weapon" and halberd.item_metadata["magic_bonus"] == 2
    assert halberd.item_metadata["damage_dice"] == "1d10" and halberd.item_metadata["weapon_category"] == "martial"
    assert "Balestra infima" in by_name  # nome personalizzato (characterValues typeId 8)
    assert by_name["Arrows"].item_type == "ammunition"
    assert by_name["Potion of Healing"].item_type == "consumable"
    assert by_name["legume seed"].quantity == 25  # custom item


def test_fixture_spells():
    exp, _, _ = convert(load())
    names = [s.name for s in exp.spells]
    assert len(names) == len(set(names)) and len(names) >= 28
    g = next(s for s in exp.spells if s.name == "Guidance")
    assert g.level == 0 and g.is_prepared and g.is_concentration and g.srd_index == "guidance"
    flame = next(s for s in exp.spells if s.name == "Sacred Flame")
    assert flame.range_area == "60 ft." and flame.components == "V, S"
    assert len({s.export_key for s in exp.spells}) == len(exp.spells)
    used = {(s.level, s.is_pact): s.used for s in exp.spell_slots}
    assert used[(1, False)] == 1 and used[(3, False)] == 3


def test_fixture_limited_use():
    exp, _, uses = convert(load())
    ab = {a.name: a for a in exp.abilities}
    cd = ab["Channel Divinity"]
    assert cd.max_uses == 3 and cd.uses == 2 and cd.restoration_type == "short_rest"
    assert ab["Divine Intervention"].max_uses == 1 and ab["Divine Intervention"].restoration_type == "long_rest"
    assert ab["Wrath of the Storm"].max_uses == 5  # modificatore SAG
    assert {"class_index": 0, "name": "Channel Divinity", "used": 1} in uses


def test_alert_feat_and_racial_traits_passive():
    exp, _, _ = convert(load())
    ab = {a.name: a for a in exp.abilities}
    assert ab["Alert"].is_passive and ab["Dwarven Resilience"].is_passive
    assert "Hit Points" not in ab and "Ability Score Improvement" not in ab
    assert len(ab) == len(exp.abilities)  # nessun duplicato per nome


def test_unknown_class_is_approximated():
    d = data()
    d["classes"][0]["definition"]["name"] = "Blood Hunter"
    exp, rep, _ = convert(d)
    assert exp.classes[0].class_name == "Blood Hunter" and exp.classes[0].hit_die == 8
    assert any(e.section == "classes" and e.reason == "ddb.reason.unknown_class" for e in rep.approximated)


@pytest.mark.parametrize("section", ["inventory", "classSpells", "modifiers", "actions", "race",
                                     "currencies", "stats", "spells", "characterValues", "feats", "notes"])
def test_section_null_never_raises(section):
    d = data()
    d[section] = None
    exp, rep, _ = convert(d)
    assert exp.character.name == "Додрия"


def test_garbage_types_never_raise():
    d = data()
    d["stats"] = [{"id": "x", "value": "y"}, 3]
    d["inventory"] = [1, "a", None, {"definition": None}]
    d["classSpells"] = [{"spells": [None, {"definition": {"name": 5}}]}]
    d["modifiers"] = {"race": "boh", "class": [None, {"type": 1}]}
    d["baseHitPoints"] = "tanti"
    exp, rep, _ = convert(d)
    assert exp.classes and rep.skipped


def test_attunement_capped_at_three():
    d = data()
    base = next(i for i in d["inventory"] if i["definition"]["name"] == "Cloak of Protection")
    for n in range(4):
        extra = copy.deepcopy(base)
        extra["id"] = 900 + n
        extra["definition"]["name"] = f"Ring {n}"
        d["inventory"].append(extra)
    exp, rep, _ = convert(d)
    assert sum(1 for i in exp.items if i.item_metadata.get("attuned")) == 3
    assert sum(1 for e in rep.approximated if e.reason == "ddb.reason.attunement_limit") == 2


@pytest.mark.parametrize("mutate", [
    lambda d: d.pop("name"), lambda d: d.update(name="  "), lambda d: d.update(classes=[]),
    lambda d: d.update(classes=None),
])
def test_missing_name_or_classes_raises(mutate):
    d = data()
    mutate(d)
    with pytest.raises(DdbImportError) as e:
        convert(d)
    assert e.value.code == "ddb_invalid"


def test_not_a_dict_raises():
    with pytest.raises(DdbImportError):
        convert([1, 2])


def test_accepts_bare_data():
    a, _, _ = convert(load())
    b, _, _ = convert(data())
    def norm(e):  # timestamp generati a ogni conversione
        d = e.model_dump(exclude={"exported_at"})
        d["character"]["notes"] = sorted(d["character"]["notes"])
        return d
    assert norm(a) == norm(b)


def test_shield_keeps_off_hand_when_weapons_listed_first():
    d = data()
    inv = d["inventory"]
    shield = next(i for i in inv if i["definition"]["name"] == "Shield")
    inv.remove(shield)
    for i in inv:
        if i["definition"]["name"] in ("Handaxe", "Warhammer"):
            i["equipped"] = True
    inv.append(shield)
    exp, rep, _ = convert(d)
    assert exp.character.shield_armor_class == 2
    assert next(i for i in exp.items if i.name == "Shield").equipment_slot.value == "off_hand"
    # le armi equipaggiate rimaste senza slot finiscono nel report
    assert any(e.reason == "ddb.reason.no_free_slot" for e in rep.approximated)
