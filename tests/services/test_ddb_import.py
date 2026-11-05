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
    assert {"class_index": 0, "name": "Channel Divinity", "used": 1, "max": 3} in uses


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


# --- seconda scheda: Stregone 5 (regole 2024), nessuna armatura ---------------------------

_SORC = Path(__file__).parents[1] / "fixtures" / "ddb" / "sorcerer5_2024.json"


def sorc() -> dict:
    return json.loads(_SORC.read_text(encoding="utf-8"))["data"]


def test_sorcerer_core_values():
    exp, _, _ = convert(sorc())
    assert {a.name: a.value for a in exp.ability_scores} == {
        "strength": 10, "dexterity": 14, "constitution": 15, "intelligence": 10, "wisdom": 12, "charisma": 16}
    assert exp.character.hit_points == 32 and exp.classes[0].class_name == "Stregone"
    used = {(s.level, s.is_pact): s.used for s in exp.spell_slots}
    assert used == {(1, False): 1, (2, False): 1}


def test_unarmored_ac_adds_dex():  # come la scheda DDB: 10 + DES
    assert convert(sorc())[0].character.base_armor_class == 12


def _armor_on_cleric(type_id: int, base_ac: int, dex: int = 16) -> int:
    d = data()
    d["overrideStats"] = [{"id": i, "value": dex if i == 2 else None} for i in range(1, 7)]
    chain = next(i for i in d["inventory"] if i["definition"]["name"] == "Chain Mail")
    chain["definition"]["armorTypeId"], chain["definition"]["armorClass"] = type_id, base_ac
    return convert(d)[0].character.base_armor_class


def test_armor_dex_by_type():  # DES 16 = +3
    assert _armor_on_cleric(1, 11) == 14  # leggera: + DES piena
    assert _armor_on_cleric(2, 14) == 16  # media: + DES max 2
    assert _armor_on_cleric(3, 16) == 16  # pesante: niente DES


def test_unarmored_defense_modifier():
    d = sorc()
    d["modifiers"]["class"].append({"type": "set", "subType": "unarmored-armor-class", "statId": 3, "value": None})
    ch = convert(d)[0].character
    assert ch.unarmored_defense_ability == "constitution" and ch.base_armor_class == 14  # 10 + 2 + 2


def test_unarmored_flat_bonus():  # es. Resilienza draconica: 13 + DES
    d = sorc()
    d["modifiers"]["class"].append({"type": "set", "subType": "unarmored-armor-class", "statId": None, "value": 3})
    ch = convert(d)[0].character
    assert ch.base_armor_class == 15 and ch.unarmored_defense_ability is None


def test_2024_structural_features_dropped():
    names = {a.name for a in convert(sorc())[0].abilities}
    assert not names & {"Core Sorcerer Traits", "Sorcerer Subclass", "Metamagic Options"}
    assert {"Metamagic: Quickened Spell", "Font of Magic", "Innate Sorcery"} <= names


# --- terza scheda: Monaco 20 (regole 2024), Difesa e Movimento senza armatura --------------

_MONK = Path(__file__).parents[1] / "fixtures" / "ddb" / "monk20_2024.json"


def monk() -> dict:
    return json.loads(_MONK.read_text(encoding="utf-8"))["data"]


def test_monk_unarmored_defense_and_hp():
    ch = convert(monk())[0].character
    assert ch.unarmored_defense_ability == "wisdom" and ch.base_armor_class == 20  # 10 + DES 6 + SAG 4
    assert ch.hit_points == 143


def test_monk_speed_lineage_plus_unarmored_movement():
    assert convert(monk())[0].character.speed == 65  # lignaggio silvano 35 + movimento senza armatura 30


def test_unarmored_movement_lost_with_armor():
    d = monk()
    d["inventory"].append({"id": 1, "equipped": True, "quantity": 1,
                           "definition": {"name": "Leather Armor", "filterType": "Armor", "armorTypeId": 1, "armorClass": 11}})
    assert convert(d)[0].character.speed == 35


def test_monk_placeholder_features_dropped():
    names = {a.name for a in convert(monk())[0].abilities}
    assert not names & {"8: Ability Score Improvement", "Ability Score Increases", "Creature Type", "Epic Boon"}
    assert {"Martial Arts", "Boon of Combat Prowess", "Fey Ancestry"} <= names


# --- quarta scheda: Barbaro 20 Berserker (2024), Nano, Soldato, scelte lasciate aperte ----

_BARB = Path(__file__).parents[1] / "fixtures" / "ddb" / "barbarian20_2024.json"


def barb() -> dict:
    return json.loads(_BARB.read_text(encoding="utf-8"))["data"]


def test_barbarian_core_values():
    exp, _, _ = convert(barb())
    ch = exp.character
    assert ch.hit_points == 245  # d12 + CON 4 + Robustezza nanica, livello 20
    assert ch.unarmored_defense_ability == "constitution" and ch.base_armor_class == 16
    assert ch.speed == 40  # nano 30 + Movimento veloce
    assert {a.name: a.value for a in exp.ability_scores}["strength"] == 21


def test_unresolved_choices_not_imported_as_proficiencies():
    ch = convert(barb())[0].character
    every = [p for v in ch.general_proficiencies.values() for p in v] + list(ch.languages)
    assert not [p for p in every if p.lower().startswith(("choose ", "select "))]
    assert "Common" in ch.languages


def test_level_prefixed_duplicates_dropped():
    names = [a.name for a in convert(barb())[0].abilities]
    assert "Weapon Mastery" in names
    assert not {"4: Weapon Mastery", "10: Weapon Mastery", "Soldier Ability Score Improvements"} & set(names)


def test_feature_uses_carry_ddb_max():
    uses = convert(barb())[2]
    assert {"class_index": 0, "name": "Rage (Enter)", "used": 0, "max": 6} in uses


# --- quinta scheda: Bardo 20 Sapienza (2024), incantesimi "conosciuti" ----------------------

_BARD = Path(__file__).parents[1] / "fixtures" / "ddb" / "bard20_2024.json"


def bard() -> dict:
    return json.loads(_BARD.read_text(encoding="utf-8"))["data"]


def test_known_caster_spells_are_prepared():  # bardo: niente preparazione, tutto ciò che conosce è lanciabile
    sp = {s.name: s for s in convert(bard())[0].spells}
    assert sp["Counterspell"].is_prepared and sp["Power Word Kill"].is_prepared


def test_prepared_caster_keeps_ddb_flag():  # chierico: conta il flag "prepared" di DDB
    sp = {s.name: s for s in convert(load())[0].spells}
    assert sp["Heal"].is_prepared and sp["Guidance"].is_prepared  # trucchetto: sempre
    d = data()
    heal = next(s for cs in d["classSpells"] for s in cs["spells"] if s["definition"]["name"] == "Heal")
    heal["prepared"] = False
    assert not {s.name: s for s in convert(d)[0].spells}["Heal"].is_prepared


def test_empty_spell_placeholders_ignored_silently():
    _, rep, _ = convert(bard())
    assert not [e for e in rep.skipped if e.section == "spells"]


def test_always_prepared_from_game_data_imported():  # incantesimi di dominio 2024: fuori dal JSON del PG
    d = bard()
    d["_alwaysPrepared"] = [{"definition": {"name": "Bless", "level": 1}}, None, {"definition": None}]
    sp = {s.name: s for s in convert(d)[0].spells}
    assert sp["Bless"].is_prepared and sp["Bless"].level == 1


def test_condition_immunity_reported_as_condition():  # es. Nature's Ward del druido: immune a Poisoned
    d = bard()
    d["modifiers"]["class"].append({"type": "immunity", "subType": "poisoned", "friendlySubtypeName": "Poisoned"})
    _, rep, _ = convert(d)
    e = next(e for e in rep.skipped if e.name == "Poisoned")
    assert e.reason == "ddb.reason.condition_immunity"


# --- sesta scheda: Guerriero 20 con armatura magica NON sintonizzata e spilla sintonizzata ---

_FIGHTER = Path(__file__).parents[1] / "fixtures" / "ddb" / "fighter20_2024.json"


def fighter() -> dict:
    return json.loads(_FIGHTER.read_text(encoding="utf-8"))["data"]


def test_unattuned_item_modifiers_ignored():  # DDB li elenca comunque in modifiers.item; la scheda no
    res = convert(fighter())[0].character.damage_modifiers["resistances"]
    assert "force" in res  # Brooch of Shielding sintonizzata
    assert "acid" not in res  # Armor of Acid Resistance equipaggiata ma non sintonizzata


def test_unequipped_item_modifiers_ignored():
    d = fighter()
    next(i for i in d["inventory"] if i["definition"]["name"] == "Brooch of Shielding")["equipped"] = False
    assert "force" not in convert(d)[0].character.damage_modifiers.get("resistances", [])


def test_fighter_armor_and_shield_ac():
    ch = convert(fighter())[0].character
    assert ch.base_armor_class == 16 and ch.shield_armor_class == 2


def test_unarmored_never_worse_than_plain_dex():  # Resilienza draconica 2024 con CAR negativo: DDB tiene 10 + DES
    d = sorc()
    d["overrideStats"] = [{"id": i, "value": 8 if i == 6 else None} for i in range(1, 7)]
    d["modifiers"]["class"].append({"type": "set", "subType": "unarmored-armor-class", "statId": 6, "value": None})
    assert convert(d)[0].character.base_armor_class == 12  # 10 + DES 2, non 10 + 2 - 1


# --- settima scheda: multiclasse Mago 17 (2024, sottoclasse PHB 2014) / Warlock 3 (2014) -----

_MULTI = Path(__file__).parents[1] / "fixtures" / "ddb" / "wizard17_warlock3_multi.json"


def multi() -> dict:
    return json.loads(_MULTI.read_text(encoding="utf-8"))["data"]


def test_multiclass_saves_only_from_starting_class():  # DDB: availableToMulticlass=false sulla classe aggiunta
    assert convert(multi(), edition="2024")[0].character.saving_throws == {"intelligence": True, "wisdom": True}


def test_multiclass_classes_and_slots():
    exp, _, _ = convert(multi(), edition="2024")
    assert [(c.class_name, c.level, c.subclass) for c in exp.classes] == [
        ("Mago", 17, "School of Necromancy (PHB)"), ("Warlock", 3, "The Fiend")]
    used = {(s.level, s.is_pact): s.used for s in exp.spell_slots}
    assert used == {(1, False): 1, (2, True): 1}
    assert exp.character.hit_points == 145


def test_conditions_mapped_by_ddb_id():  # id DDB: 4 esaurimento (con livello), 11 avvelenato, 12 prono
    raw = load()
    raw["data"]["conditions"] = [{"id": 4, "level": 2}, {"id": 11, "level": None},
                                 {"id": 12, "level": None}, {"id": 99, "level": None}]
    exp, rep, _ = convert(raw)
    assert exp.character.conditions == {"exhaustion": 2, "poisoned": True, "prone": True}
    assert [s.section for s in rep.skipped].count("conditions") == 1  # solo l'id sconosciuto


def _with_values(raw: dict, *values: tuple[int, int]) -> dict:
    raw["characterValues"] = [{"typeId": t, "value": v} for t, v in values]
    return raw


def test_ac_override_total_wins():  # DDB "Override AC" (typeId 1): la CA è quella, scudo e bonus esclusi
    ch = convert(_with_values(fighter(), (1, 18), (2, 1), (3, 2)))[0].character
    assert (ch.base_armor_class, ch.shield_armor_class, ch.magic_armor) == (18, 0, 0)
    assert ch.base_armor_class_override and ch.shield_armor_class_override
    assert ch.unarmored_defense_ability is None


def test_ac_override_base_keeps_shield_and_bonus():  # DDB "Override Base Armor + DEX" (typeId 4)
    ch = convert(_with_values(fighter(), (4, 14), (2, 1)))[0].character
    assert (ch.base_armor_class, ch.shield_armor_class, ch.magic_armor) == (14, 2, 1)
    assert ch.base_armor_class_override and not ch.shield_armor_class_override


def test_custom_speeds():  # DDB "Override speeds": movementId 1 a piedi, le altre in settings.speeds
    raw = load()
    raw["data"]["customSpeeds"] = [{"movementId": 1, "distance": 40}, {"movementId": 4, "distance": 60}]
    exp, rep, _ = convert(raw)
    assert exp.character.speed == 40
    assert exp.character.settings["speeds"] == [{"type": "fly", "range_ft": 60}]
    assert not [s for s in rep.skipped if s.section == "speed"]


def test_innate_other_speeds():  # es. nuoto da lignaggio
    raw = load()
    raw["data"]["modifiers"]["race"].append({"type": "set", "subType": "innate-speed-swimming", "value": 30})
    assert {"type": "swim", "range_ft": 30} in convert(raw)[0].character.settings["speeds"]


def test_fly_speed_equal_to_walking():  # Stormborn (Tempesta 17): innate-speed-flying senza valore
    assert convert(load())[0].character.settings["speeds"] == [{"type": "fly", "range_ft": 25}]


def test_senses_from_species_and_overrides():  # scurovisione della specie + override "Senses" della scheda
    raw = load()
    assert convert(raw)[0].character.settings["senses"] == [{"type": "darkvision", "range_ft": 60}]
    raw["data"]["customSenses"] = [{"senseId": 2, "distance": 90}, {"senseId": 4, "distance": 30}]
    assert convert(raw)[0].character.settings["senses"] == [
        {"type": "darkvision", "range_ft": 90}, {"type": "truesight", "range_ft": 30}]


def test_custom_actions_become_abilities():  # "Manage Custom" della scheda: l'app non ha attacchi liberi
    raw = load()
    raw["data"]["customActions"] = [{"name": "Flaming Claw", "description": "A burning claw strike.",
                                     "diceCount": 2, "diceType": 6, "damageTypeId": 7, "statId": 1},
                                    {"name": "Taunt", "description": None}]
    exp, rep, _ = convert(raw)
    claw = next(a for a in exp.abilities if a.name == "Flaming Claw")
    assert not claw.is_passive and "2d6" in claw.description and "fire" in claw.description.lower()
    assert "A burning claw strike." in claw.description
    assert any(a.name == "Taunt" for a in exp.abilities)
    assert {(e.name, e.reason) for e in rep.approximated} >= {("Flaming Claw", "ddb.reason.custom_action")}


def test_custom_item_already_in_inventory_not_duplicated():  # includeCustomItems: compare anche in inventory
    raw = load()
    raw["data"]["customItems"] = [{"id": 37363044, "name": "Lucky Coin", "quantity": 2},
                                  {"id": 5, "name": "Only Custom", "quantity": 1}]
    raw["data"]["inventory"].append({"id": 1, "quantity": 2, "equipped": False,
                                     "definition": {"id": 37363044, "name": "Lucky Coin"}})
    names = [i.name for i in convert(raw)[0].items]
    assert names.count("Lucky Coin") == 1 and names.count("Only Custom") == 1


def test_ac_override_total_not_raised_by_item_bonuses():  # l'app somma i bonus CA degli oggetti: vanno scalati
    from core.game.item_bonuses import item_bonus_total
    raw = _with_values(fighter(), (1, 18))
    brooch = next(i for i in raw["inventory"] if "Brooch" in i["definition"]["name"])
    brooch["definition"]["grantedModifiers"] = [{"type": "bonus", "subType": "armor-class", "value": 1}]
    exp = convert(raw)[0]
    ch = exp.character
    assert item_bonus_total(exp.items, "ac") == 1
    assert ch.base_armor_class + ch.shield_armor_class + ch.magic_armor + item_bonus_total(exp.items, "ac") == 18


def test_proficiency_level_overrides():  # "Skill/Saving Throw Proficiency Level" dalla scheda
    raw = load()["data"]
    raw["characterValues"] = [
        {"typeId": 26, "value": 4, "valueId": "5"},   # Furtività -> maestria
        {"typeId": 26, "value": 1, "valueId": "13"},  # Medicina -> non competente
        {"typeId": 26, "value": 2, "valueId": "6"},   # Arcano -> mezza competenza (non gestita)
        {"typeId": 41, "value": 3, "valueId": "2"},   # TS Destrezza -> competente
        {"typeId": 41, "value": 1, "valueId": "5"},   # TS Saggezza -> non competente
    ]
    exp, rep, _ = convert(raw)
    ch = exp.character
    assert ch.skills.get("stealth") == "expert" and not ch.skills.get("medicine") and not ch.skills.get("arcana")
    assert ch.saving_throws.get("dexterity") and not ch.saving_throws.get("wisdom")
    assert ("proficiencies", "arcana", "ddb.reason.half_proficiency") in [(e.section, e.name, e.reason) for e in rep.approximated]


def test_unsupported_sheet_overrides_reported():  # bonus/valori fissi per abilità e TS: l'app non li ha
    raw = load()["data"]
    raw["characterValues"] = [{"typeId": 24, "value": 2, "valueId": "5"},   # bonus vario Furtività
                              {"typeId": 40, "value": 1, "valueId": "2"},   # bonus magico TS Destrezza
                              {"typeId": 5, "value": 18, "valueId": None},  # Percezione passiva fissa
                              {"typeId": 9, "value": "x", "valueId": "1"}]  # note di un oggetto: non è del PG
    rep = convert(raw)[1]
    assert [(e.section, e.name) for e in rep.skipped if e.section == "other"] == [
        ("other", "Skill Misc Bonus: stealth +2"), ("other", "Saving Throw Magic Bonus: dexterity +1"),
        ("other", "Override Passive Perception: 18")]


_CREATURES = Path(__file__).parents[1] / "fixtures" / "ddb" / "creatures.json"


def with_creatures() -> dict:
    raw = load()
    raw["data"]["creatures"] = json.loads(_CREATURES.read_text(encoding="utf-8"))
    return raw


def test_creatures_become_companions():  # famigli (gruppo 2) e forme selvatiche 2024 (gruppo 13)
    exp, rep, _ = convert(with_creatures())
    assert [(c.kind, c.name) for c in exp.companions] == [
        ("familiar", "Cat"), ("familiar", "Cat"), ("wild_shape", "Giant Wolf Spider"), ("wild_shape", "Dire Wolf")]
    assert not [e for e in rep.skipped if e.section == "creatures"]
    assert not [e for e in rep.approximated if e.section == "creatures"]  # la forma 2024 ha i suoi PF temporanei


def test_creature_statblock_2024():
    wolf = convert(with_creatures())[0].companions[3]
    assert (wolf.armor_class, wolf.max_hp, wolf.current_hp) == (14, 22, 22)
    sb = wolf.statblock
    assert sb["size"] == "large" and sb["type"] == "beast" and sb["challenge_rating"] == 1
    assert sb["speed"] == {"walk_ft": 50}
    assert set(sb["abilities"]) == {"str", "dex", "con", "int", "wis", "cha"}
    bite = sb["actions"][0]
    assert (bite["name"], bite["attack_bonus"], bite["damage_dice"], bite["damage_type"]) == ("Bite", 5, "1d10+3", "piercing")
    assert "Prone" in bite["desc"]
    assert sb["traits"][0]["name"] == "Pack Tactics"


def test_creature_statblock_2014_and_flat_damage():
    comps = convert(with_creatures())[0].companions
    spider = comps[2].statblock
    assert spider["speed"] == {"walk_ft": 40, "climb_ft": 40}
    bite = spider["actions"][0]
    assert (bite["attack_bonus"], bite["damage_dice"], bite["damage_type"]) == (3, "1d6+1", "piercing")
    scratch = comps[0].statblock["actions"][0]  # danno fisso "1 Slashing": l'app vuole NdX
    assert (scratch["attack_bonus"], scratch["damage_dice"], scratch["damage_type"]) == (4, "1d1", "slashing")


def test_creature_custom_name_hp_and_active_form():
    raw = with_creatures()
    raw["data"]["creatures"][3] |= {"name": "Zanna", "removedHitPoints": 5, "temporaryHitPoints": 3, "isActive": True}
    wolf = convert(raw)[0].companions[3]
    assert (wolf.name, wolf.current_hp, wolf.temp_hp, wolf.is_active) == ("Zanna", 17, 3, True)


def test_creature_other_groups_and_garbage():
    raw = with_creatures()
    cr = raw["data"]["creatures"]
    cr[0]["groupId"], cr[1]["groupId"], cr[2]["groupId"] = 4, 6, 11  # cavalcatura, evocato, sidekick
    cr.append({"groupId": 2, "definition": None})  # spazzatura: niente crash
    exp, rep, _ = convert(raw)
    assert [c.kind for c in exp.companions] == ["mount", "summon", "companion", "wild_shape"]
    assert ("creatures", "Giant Wolf Spider", "ddb.reason.creature_group") in [
        (e.section, e.name, e.reason) for e in rep.approximated]


def test_containers_map_to_refs():
    exp, _, _ = convert(load())
    by_name = {i.name: i for i in exp.items}
    pack = by_name["Backpack"]
    assert pack.item_metadata["container"] == {"capacity_lb": 30.0, "counts_weight": True, "quick_access": False,
                                               "coins": {"copper": 0, "silver": 0, "electrum": 0, "gold": 0, "platinum": 0}}
    assert pack.ref is not None and pack.container_ref is None
    assert by_name["Torch"].container_ref == pack.ref
    assert by_name["Shield"].container_ref is None  # sciolto: containerEntityId = id del personaggio


def test_container_with_quantity_stays_plain_item():
    d = load()
    for it in d["data"]["inventory"]:
        if it["definition"]["name"] == "Backpack":
            it["quantity"] = 2
    exp, rep, _ = convert(d)
    by_name = {i.name: i for i in exp.items}
    assert "container" not in by_name["Backpack"].item_metadata and by_name["Backpack"].ref is None
    assert by_name["Torch"].container_ref is None
    assert any(a.name == "Backpack" and a.reason == "ddb.reason.container_quantity" for a in rep.approximated)


def test_equipped_item_inside_container_is_unequipped_and_ignored_by_ac():
    d = load()
    base = convert(load())[0].character.base_armor_class
    for it in d["data"]["inventory"]:
        if it["definition"]["name"] == "Chain Mail":  # indossata nel fixture: la mettiamo nello zaino
            it["containerEntityId"] = 446369977
        if it["definition"]["name"] == "Backpack":
            it["definition"]["capacityWeight"] = 10**9
    exp, _, _ = convert(d)
    by_name = {i.name: i for i in exp.items}
    chain = by_name["Chain Mail"]
    assert chain.container_ref == by_name["Backpack"].ref
    assert not chain.is_equipped and chain.equipment_slot is None
    assert exp.character.base_armor_class != base  # niente armatura: CA senza maglia
    assert by_name["Backpack"].item_metadata["container"]["capacity_lb"] == 100_000


def test_container_capacity_junk_and_id_zero():
    d = load()
    for it in d["data"]["inventory"]:
        if it["definition"]["name"] == "Backpack":
            it["definition"]["capacityWeight"] = float("inf")
            it["id"] = 0
    exp, _, _ = convert(d)
    pack = next(i for i in exp.items if i.name == "Backpack")
    assert "container" not in pack.item_metadata and pack.ref is None
