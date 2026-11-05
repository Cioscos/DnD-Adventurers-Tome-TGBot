"""Monaco 2014 (Task 24): progressione, Difesa Senza Armatura, Arti Marziali, Ki, Movimento Senza Armatura, Colpi Ki
Potenziati, Purezza del Corpo, scelta della Tradizione e righe di sola descrizione."""
from __future__ import annotations

import pytest

from core.rules.catalog import features_for
from core.rules.proficiencies import class_proficiencies
from tests.integration.rules.test_2014_bard import _ability, _full, _keys_of

SUBCLASSES = {"open_hand": "Via della Mano Aperta", "shadow": "Via dell'Ombra", "four_elements": "Via dei Quattro Elementi"}
KI = "monk.ki"
SHIELD = {"name": "Scudo", "item_type": "shield", "item_metadata": {"ac_bonus": 2}}
ARMOR = {"name": "Armatura leggera", "item_type": "armor", "item_metadata": {"ac_value": 11, "armor_type": "light"}}


async def _monk(client, level=5, subclass=None, **scores) -> int:
    body = {"name": "Monaco", "initial_class": {"class_name": "monk", "level": level, "subclass": SUBCLASSES.get(subclass)}}
    r = await client.post("/characters", json=body)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    for ability, value in scores.items():
        r = await client.patch(f"/characters/{cid}/ability_scores/{ability}", json={"value": value})
        assert r.status_code == 200, r.text
    return cid


async def _equip(client, cid, slot="body", **fields) -> dict:
    r = await client.post(f"/characters/{cid}/items", json=fields)
    assert r.status_code == 201, r.text
    item = max(r.json()["items"], key=lambda i: i["id"])
    r = await client.patch(f"/characters/{cid}/items/{item['id']}", json={"is_equipped": True, "equipment_slot": slot})
    assert r.status_code == 200, r.text
    return {**r.json(), "item_id": item["id"]}


async def _turn(client, cid) -> dict:
    return (await client.get(f"/characters/{cid}/turn-state")).json()["turn"]


async def _rest(client, cid, kind) -> None:
    r = await client.post(f"/characters/{cid}/rest", json={"rest_type": kind, "confirm_early": True})
    assert r.status_code == 200, r.text


# ---------------------------------------------------------------------------
# Punti Ferita, Competenze, Equipaggiamento
# ---------------------------------------------------------------------------

async def test_hit_points_use_the_d8_and_follow_constitution(client):
    full = await _full(client, await _monk(client, 3))
    assert full["classes"][0]["hit_die"] == 8
    assert full["hit_points"] == 8 + 5 + 5  # 8 + COS al 1°, poi la media 5 (COS 10)


async def test_hit_points_of_a_character_created_above_level_1_follow_the_effective_constitution(client):
    cid = await _monk(client, 5, constitution=14)
    assert (await _full(client, cid))["hit_points"] == (8 + 2) + 4 * (5 + 2)


def test_class_proficiencies_first_class_and_multiclass():
    first = class_proficiencies("2014", "monk", False)
    assert not first.armor and set(first.weapons) == {"simple", "shortsword"}
    assert set(first.saves) == {"strength", "dexterity"} and first.skills_count == 2
    assert set(first.skills_from) == {"acrobatics", "athletics", "history", "insight", "religion", "stealth"}
    multi = class_proficiencies("2014", "monk", True)
    assert not multi.armor and set(multi.weapons) == {"simple", "shortsword"} and not multi.saves and not multi.skills_count


# ---------------------------------------------------------------------------
# Difesa Senza Armatura
# ---------------------------------------------------------------------------

async def test_unarmored_defense_is_automatic_from_level_1_and_uses_dexterity_and_wisdom(client):
    cid = await _monk(client, 1, dexterity=16, wisdom=14)
    full = await _full(client, cid)
    assert full["ac_breakdown"]["base"] == 10 + 3 + 2 and full["unarmored_formula"] == ["dexterity", "wisdom"]
    assert "monk.unarmored_defense" in await _keys_of(client, cid)


async def test_unarmored_defense_follows_the_effective_scores(client):
    cid = await _monk(client, 1, dexterity=14, wisdom=14)
    await _equip(client, cid, slot="ring1", name="Anello", item_type="accessory", item_metadata={
        "ability_modifiers": [{"ability": "wisdom", "kind": "absolute", "value": 18}]})
    assert (await _full(client, cid))["ac_breakdown"]["base"] == 10 + 2 + 4


async def test_armor_or_shield_suspend_unarmored_defense_and_removing_them_brings_it_back(client):
    cid = await _monk(client, 3, dexterity=16, wisdom=16)
    shield = await _equip(client, cid, slot="off_hand", **SHIELD)
    assert shield["ac_breakdown"]["base"] == 13 and shield["unarmored_formula"] is None  # 10 + DES, senza SAG
    r = await client.patch(f"/characters/{cid}/items/{shield['item_id']}", json={"is_equipped": False})
    assert r.json()["ac_breakdown"]["base"] == 16
    armor = await _equip(client, cid, **ARMOR)
    assert armor["ac_breakdown"]["base"] == 14 and armor["unarmored_formula"] is None  # 11 + DES
    r = await client.patch(f"/characters/{cid}/items/{armor['item_id']}", json={"is_equipped": False})
    assert r.json()["ac_breakdown"]["base"] == 16


async def test_unarmored_defense_does_not_stack_with_the_barbarian_one(client):
    cid = await _monk(client, 3, dexterity=14, wisdom=14, constitution=18)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "barbarian", "level": 1, "hit_die": 12})
    assert r.status_code == 201, r.text
    # una sola formula, la migliore: 10 + DES 2 + COS 4 (non 10 + 2 + 4 + 2)
    assert (await _full(client, cid))["ac_breakdown"]["base"] == 10 + 2 + 4


# ---------------------------------------------------------------------------
# Arti Marziali
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,die", [(1, "1d4"), (4, "1d4"), (5, "1d6"), (10, "1d6"), (11, "1d8"), (16, "1d8"), (17, "1d10"), (20, "1d10")])
async def test_martial_arts_die_follows_the_level(client, level, die):
    cid = await _monk(client, level, dexterity=16)
    r = await client.post(f"/characters/{cid}/attack/unarmed", json={"die": 10})
    assert r.status_code == 200, r.text
    assert r.json()["damage_dice"] == die


async def test_martial_arts_is_a_passive_row_from_level_1(client):
    row = await _ability(client, await _monk(client, 1), "monk.martial_arts")
    assert row is not None and row["is_passive"] is True


async def test_unarmed_strike_uses_dexterity_and_armor_or_shield_cancel_the_die(client):
    cid = await _monk(client, 5, strength=8, dexterity=16)
    body = (await client.post(f"/characters/{cid}/attack/unarmed", json={"die": 10})).json()
    assert body["to_hit_bonus"] == 3 + 3 and body["damage_bonus"] == 3
    await _equip(client, cid, slot="off_hand", **SHIELD)
    body = (await client.post(f"/characters/{cid}/attack/unarmed", json={"die": 10})).json()
    assert body["damage_dice"] == "1" and body["damage_bonus"] == -1  # FOR 8, nessun dado di Arti Marziali


async def test_shortsword_is_a_monk_weapon_but_a_greatsword_is_not(client):
    cid = await _monk(client, 5, strength=8, dexterity=16)
    short = await _equip(client, cid, slot="main_hand", name="Spada corta", item_type="weapon", item_metadata={
        "damage_dice": "1d6", "weapon_type": "melee", "properties": ["finesse", "light"], "weapon_category": "martial"})
    r = await client.post(f"/characters/{cid}/items/{short['item_id']}/attack", json={"die": 10})
    assert r.json()["damage_dice"] == "1d6" and r.json()["damage_bonus"] == 3
    await client.patch(f"/characters/{cid}/items/{short['item_id']}", json={"is_equipped": False})
    great = await _equip(client, cid, slot="main_hand", name="Spadone", item_type="weapon", item_metadata={
        "damage_dice": "2d6", "weapon_type": "melee", "properties": ["heavy", "two_handed"], "weapon_category": "martial"})
    r = await client.post(f"/characters/{cid}/items/{great['item_id']}/attack", json={"die": 10})
    assert r.json()["damage_dice"] == "2d6" and r.json()["damage_bonus"] == -1  # FOR 8: nessun beneficio


# ---------------------------------------------------------------------------
# Ki
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level", [2, 3, 5, 11, 19, 20])
async def test_ki_points_equal_the_monk_level_and_come_back_with_a_short_rest(client, level):
    row = await _ability(client, await _monk(client, level), KI)
    assert (row["max_uses"], row["uses"], row["restoration_type"]) == (level, level, "short_rest")


async def test_there_is_no_ki_at_level_1(client):
    assert KI not in await _keys_of(client, await _monk(client, 1))


async def test_the_official_name_replaces_the_old_resource_name_and_the_row_has_no_use_button(client):
    row = await _ability(client, await _monk(client, 5), KI)
    assert row["name"] == "Ki" and row["is_pool"] is True and row["has_on_use"] is False
    assert "Difesa Attenta" not in (row["description"] or "") and "Difesa Paziente" in (row["description"] or "")


@pytest.mark.parametrize("rest", ["short", "long"])
async def test_ki_comes_back_with_a_short_or_a_long_rest(client, rest):
    cid = await _monk(client, 5)
    ability = await _ability(client, cid, KI)
    await client.patch(f"/characters/{cid}/abilities/{ability['id']}", json={"uses": 1})
    await _rest(client, cid, rest)
    assert (await _ability(client, cid, KI))["uses"] == 5


async def test_the_ki_save_dc_is_8_plus_proficiency_plus_wisdom(client):
    cid = await _monk(client, 5, wisdom=16)  # competenza +3, Saggezza +3
    assert (await _ability(client, cid, KI))["dc"] == 8 + 3 + 3
    await client.patch(f"/characters/{cid}/ability_scores/wisdom", json={"value": 20})
    assert (await _ability(client, cid, KI))["dc"] == 8 + 3 + 5
    other = await _ability(client, cid, "monk.martial_arts")
    assert other["dc"] is None


async def test_a_ki_spent_before_the_catalog_keeps_its_count_when_the_level_rises(client):
    cid = await _monk(client, 5)
    ability = await _ability(client, cid, KI)
    await client.patch(f"/characters/{cid}/abilities/{ability['id']}", json={"uses": 2})  # 3 spesi
    klass = (await _full(client, cid))["classes"][0]
    await client.patch(f"/characters/{cid}/classes/{klass['id']}", json={"level": 6})
    row = await _ability(client, cid, KI)
    assert (row["max_uses"], row["uses"]) == (6, 3)


# ---------------------------------------------------------------------------
# Movimento Senza Armatura
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,bonus", [(1, 0), (2, 10), (5, 10), (6, 15), (9, 15), (10, 20), (13, 20), (14, 25), (17, 25), (18, 30), (20, 30)])
async def test_unarmored_movement_grows_with_the_level(client, level, bonus):
    cid = await _monk(client, level)
    assert (await _full(client, cid))["computed"]["speed"] == 30 + bonus


async def test_armor_or_shield_cancel_the_speed_bonus(client):
    cid = await _monk(client, 10)
    shield = await _equip(client, cid, slot="off_hand", **SHIELD)
    assert shield["computed"]["speed"] == 30
    r = await client.patch(f"/characters/{cid}/items/{shield['item_id']}", json={"is_equipped": False})
    assert r.json()["computed"]["speed"] == 50
    armor = await _equip(client, cid, **ARMOR)
    assert armor["computed"]["speed"] == 30


async def test_the_surface_movement_line_appears_at_level_9(client):
    low = await _keys_of(client, await _monk(client, 8))
    high = await _keys_of(client, await _monk(client, 9))
    assert "monk.unarmored_movement" in low and "monk.unarmored_movement_9" not in low
    assert "monk.unarmored_movement_9" in high


# ---------------------------------------------------------------------------
# Colpi Ki Potenziati
# ---------------------------------------------------------------------------

async def test_unarmed_strikes_are_magical_bludgeoning_from_level_6(client):
    low = (await client.post(f"/characters/{await _monk(client, 5)}/attack/unarmed", json={"die": 10})).json()
    assert low["damage_type"] == "bludgeoning" and not low.get("is_magic")
    high = (await client.post(f"/characters/{await _monk(client, 6)}/attack/unarmed", json={"die": 10})).json()
    assert high["damage_type"] == "bludgeoning" and high["is_magic"] is True


async def test_a_weapon_attack_is_not_flagged_magical_by_ki_strikes(client):
    cid = await _monk(client, 6, dexterity=16)
    club = await _equip(client, cid, slot="main_hand", name="Randello", item_type="weapon", item_metadata={
        "damage_dice": "1d4", "weapon_type": "melee", "properties": ["light"], "weapon_category": "simple"})
    body = (await client.post(f"/characters/{cid}/items/{club['item_id']}/attack", json={"die": 10})).json()
    assert not body.get("is_magic")


# ---------------------------------------------------------------------------
# Purezza del Corpo
# ---------------------------------------------------------------------------

async def _hp(client, cid, current, maximum):
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": maximum})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": current})


async def test_purity_of_body_makes_the_monk_immune_to_poison_damage_and_the_poisoned_condition(client):
    cid = await _monk(client, 10)
    await _hp(client, cid, 40, 40)
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 10, "damage_type": "poison"})
    assert r.json()["current_hit_points"] == 40
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 10, "damage_type": "fire"})
    assert r.json()["current_hit_points"] == 30
    r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"poisoned": True, "prone": True}})
    assert not r.json()["conditions"].get("poisoned") and r.json()["conditions"]["prone"] is True
    assert "poison" in (await _full(client, cid))["computed"]["immunities"]


async def test_before_level_10_poison_still_works(client):
    cid = await _monk(client, 9)
    await _hp(client, cid, 40, 40)
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 10, "damage_type": "poison"})
    assert r.json()["current_hit_points"] == 30
    r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"poisoned": True}})
    assert r.json()["conditions"]["poisoned"] is True


# ---------------------------------------------------------------------------
# Aumento dei Punteggi, Attacco Extra, Tradizione, righe di sola descrizione
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level", [4, 8, 12, 16, 19])
async def test_asi_choice_is_pending_at_each_asi_level(client, level):
    cid = await _monk(client, level)
    levels = sorted(c["level"] for c in (await _full(client, cid))["pending_choices"] if c["kind"] == "asi")
    assert levels == [lv for lv in (4, 8, 12, 16, 19) if lv <= level]


@pytest.mark.parametrize("level,attacks", [(1, 1), (4, 1), (5, 2), (11, 2), (20, 2)])
async def test_extra_attack_is_two_attacks_and_never_more(client, level, attacks):
    cid = await _monk(client, level)
    assert (await client.get(f"/characters/{cid}/turn-state")).json()["attacks_allowed"] == attacks


async def test_extra_attack_does_not_stack_with_another_class(client):
    cid = await _monk(client, 5)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "fighter", "level": 5, "hit_die": 10})
    assert r.status_code == 201, r.text
    assert (await client.get(f"/characters/{cid}/turn-state")).json()["attacks_allowed"] == 2


def test_the_three_traditions_of_the_sheet_are_the_whole_catalog():
    assert {f.subclass for f in features_for("2014", "monk") if f.subclass} == set(SUBCLASSES)


async def test_the_tradition_is_chosen_once_and_unlocks_its_features_at_3_6_11_and_17(client):
    for sub, expected in (("open_hand", {3: {"monk.open_hand_technique"}, 6: {"monk.wholeness_of_body"},
                                         11: {"monk.tranquility"}, 17: {"monk.quivering_palm"}}),
                          ("shadow", {3: {"monk.shadow_arts"}, 6: {"monk.shadow_step"}, 11: {"monk.cloak_of_shadows"},
                                      17: {"monk.opportunist"}})):
        prev: set[str] = set()
        for level, keys in expected.items():
            have = await _keys_of(client, await _monk(client, level, sub))
            assert keys <= have, (sub, level)
            assert not prev - have
            assert not (set().union(*[k for lv, k in expected.items() if lv > level]) & have)
            prev = keys
    other = await _keys_of(client, await _monk(client, 17, "shadow"))
    assert not other & {"monk.open_hand_technique", "monk.wholeness_of_body"}
    none = await _keys_of(client, await _monk(client, 17))
    assert not none & {"monk.open_hand_technique", "monk.shadow_arts", "monk.elemental_attunement"}


async def test_descriptive_rows_are_passive_text(client):
    keys = await _keys_of(client, await _monk(client, 15))
    for key in ("monk.tongue_of_the_sun_and_moon", "monk.timeless_body"):
        assert key in keys
        row = await _ability(client, await _monk(client, 15), key)
        assert row["is_passive"] is True and row["has_on_use"] is False and row["description"]
    assert "monk.tongue_of_the_sun_and_moon" not in await _keys_of(client, await _monk(client, 12))
    assert "monk.timeless_body" not in await _keys_of(client, await _monk(client, 14))


async def test_rules_only_rows_do_not_clutter_the_sheet(client):
    keys = await _keys_of(client, await _monk(client, 20, "open_hand"))
    assert not keys & {f"monk.{k}" for k in ("hit_points", "proficiencies", "equipment", "monastic_tradition",
                                            "ability_score_improvement", "multiclassing")}


async def test_hit_points_after_adding_the_monk_as_a_second_class_follow_the_effective_constitution(client):
    r = await client.post("/characters", json={"name": "Guerriero", "initial_class": {"class_name": "fighter", "level": 1}})
    cid = r.json()["id"]
    await client.patch(f"/characters/{cid}/ability_scores/constitution", json={"value": 14})
    before = (await _full(client, cid))["hit_points"]
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "monk", "level": 2, "hit_die": 8})
    assert r.status_code == 201, r.text
    assert (await _full(client, cid))["hit_points"] == before + 2 * (5 + 2)  # d8 medio 5 + COS 2 per livello, nessun 1° livello


async def test_hit_points_after_the_xp_that_raises_the_monk_level_follow_the_effective_constitution(client):
    cid = await _monk(client, 1, constitution=14)
    first = (await _full(client, cid))["hit_points"]
    assert first == 8 + 2
    r = await client.patch(f"/characters/{cid}/xp", json={"set": 900})  # 3° livello
    assert r.status_code == 200, r.text
    full = await _full(client, cid)
    assert full["classes"][0]["level"] == 3 and full["hit_points"] == first + 2 * (5 + 2)


# ---------------------------------------------------------------------------
# Import da Beyond e passaggio al catalogo dei personaggi esistenti (R33, R17)
# ---------------------------------------------------------------------------

async def test_beyond_option_names_find_the_elemental_disciplines(test_session_factory):
    from api.routers.transfer import _apply_class_options
    from api.services.ddb_import import ImportReport
    from core.rules.sample_characters import build_rules_character

    async with test_session_factory() as s:
        char = await build_rules_character(s, {"name": "x", "edition": "2014",
                                               "classes": [("Monaco", 6, "Via dei Quattro Elementi", 8)]}, 1)
        report = ImportReport()
        names = ("Fist of Four Thunders", "Gong of the Summit", "Water Whip", "Ride the Wind", "Dragon Slayer")
        _apply_class_options(char, [{"class_index": 0, "name": n} for n in names], report, "it")
        # al 6° livello sono due: la terza è fuori limite e la quarta (11°) non è ancora disponibile; il resto resta nel report
        assert char.classes[0].options["elemental_disciplines"] == ["fist_of_four_thunders", "gong_of_the_summit"]
        assert [e.name for e in report.approximated] == ["Water Whip", "Ride the Wind", "Dragon Slayer"]


async def test_migration_keeps_the_spent_ki_and_replaces_the_old_name_and_description(client, test_session_factory):
    from sqlalchemy import select
    from api.services.catalog_migration import migrate_catalog
    from core.data.classes import CLASS_RESOURCES
    from core.db.models import Ability

    cid = await _monk(client, 5)
    legacy = CLASS_RESOURCES["Monaco"][0].description["it"]
    async with test_session_factory() as s:  # lo stato di prima del catalogo: nome vecchio, testo vecchio, due ki spesi
        row = (await s.execute(select(Ability).where(Ability.character_id == cid, Ability.feature_key == KI))).scalar_one()
        row.name, row.description, row.uses = "Punti Ki", legacy, 3
        await s.commit()
    assert await migrate_catalog(test_session_factory) >= 1
    rows = [a for a in (await _full(client, cid))["abilities"] if a["feature_key"] == KI]
    assert len(rows) == 1 and rows[0]["name"] == "Ki" and rows[0]["uses"] == 3 and rows[0]["max_uses"] == 5
    assert "Difesa Attenta" not in rows[0]["description"]


async def test_migration_keeps_a_description_the_player_wrote(client, test_session_factory):
    from sqlalchemy import select
    from api.services.catalog_migration import migrate_catalog
    from core.db.models import Ability

    cid = await _monk(client, 5)
    async with test_session_factory() as s:
        row = (await s.execute(select(Ability).where(Ability.character_id == cid, Ability.feature_key == KI))).scalar_one()
        row.description = "La mia nota sul ki"
        await s.commit()
    await migrate_catalog(test_session_factory)
    assert (await _ability(client, cid, KI))["description"] == "La mia nota sul ki"


async def test_lowering_the_level_drops_the_pending_asi_beyond_it_and_a_resolved_one_does_not_come_back(client):
    cid = await _monk(client, 8)
    klass = (await _full(client, cid))["classes"][0]

    async def pending() -> list[int]:
        return sorted(c["level"] for c in (await _full(client, cid))["pending_choices"] if c["kind"] == "asi")

    assert await pending() == [4, 8]
    first = next(c for c in (await _full(client, cid))["pending_choices"] if c["kind"] == "asi" and c["level"] == 4)
    r = await client.post(f"/characters/{cid}/choices/{first['id']}/resolve", json={"kind": "asi", "increases": {"dexterity": 2}})
    assert r.status_code == 200, r.text
    await client.patch(f"/characters/{cid}/classes/{klass['id']}", json={"level": 4})
    assert await pending() == []  # il livello 8 sparisce, il 4 è già risolto
    await client.patch(f"/characters/{cid}/classes/{klass['id']}", json={"level": 8})
    assert await pending() == [8]  # ripassare il livello 4 non ne crea una nuova
