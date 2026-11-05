"""Guerriero 2014 (Task 23): Cavaliere Mistico, incantesimi da terzo di incantatore e limiti di scuola, Arma Vincolata,
Magia da Guerra, Colpo Mistico e Carica Arcana."""
from __future__ import annotations

import pytest

from tests.integration.rules.test_2014_bard import _ability, _full, _roll_keys, _use
from tests.integration.rules.test_2014_fighter import _attack, _fighter, _turn, AS

SLOTS = {3: (2,), 4: (3,), 5: (3,), 6: (3,), 7: (4, 2), 8: (4, 2), 9: (4, 2), 10: (4, 3), 11: (4, 3), 12: (4, 3),
         13: (4, 3, 2), 14: (4, 3, 2), 15: (4, 3, 2), 16: (4, 3, 3), 17: (4, 3, 3), 18: (4, 3, 3), 19: (4, 3, 3, 1),
         20: (4, 3, 3, 1)}
KNOWN = {3: 3, 4: 4, 5: 4, 6: 4, 7: 5, 8: 6, 9: 6, 10: 7, 11: 8, 12: 8, 13: 9, 14: 10, 15: 10, 16: 11, 17: 11, 18: 11,
         19: 12, 20: 13}
WAR_MAGIC, IMPROVED = "fighter.war_magic", "fighter.improved_war_magic"
STRIKE, STRIKE_CAST = "fighter.eldritch_strike", "fighter.eldritch_strike_cast"
BOND = "fighter.weapon_bond"


async def _knight(client, level=7, **scores) -> int:
    return await _fighter(client, level, "eldritch_knight", **scores)


async def _spell(client, cid, name, level=0, **extra) -> int:
    r = await client.post(f"/characters/{cid}/spells", json={"name": name, "level": level, "casting_time": "1 azione", **extra})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _cast(client, cid, spell, **body):
    return await client.post(f"/characters/{cid}/spells/{spell}/use", json=body)


async def _sword(client, cid, **meta) -> int:
    meta = {"damage_dice": "1d8", "weapon_type": "melee", "properties": [], **meta}
    r = await client.post(f"/characters/{cid}/items", json={"name": "Spada", "item_type": "weapon", "item_metadata": meta})
    assert r.status_code == 201, r.text
    return max(i["id"] for i in r.json()["items"])


# ---------------------------------------------------------------------------
# Incantesimi da terzo di incantatore
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level", list(SLOTS))
async def test_eldritch_knight_slots_cantrips_and_known_follow_the_table(client, level):
    full = await _full(client, await _knight(client, level))
    totals = tuple(s["total"] for s in sorted(full["spell_slots"], key=lambda s: s["level"]) if s["total"])
    assert totals == SLOTS[level]
    limits = full["spellcasting"]["limits"][0]
    assert (limits["cantrips_limit"], limits["known_limit"]) == (3 if level >= 10 else 2, KNOWN[level])


@pytest.mark.parametrize("subclass", [None, "champion", "battle_master"])
async def test_a_fighter_who_is_not_a_knight_does_not_cast(client, subclass):
    full = await _full(client, await _fighter(client, 10, subclass))
    assert not [s for s in full["spell_slots"] if s["total"]] and full["spellcasting"]["limits"] == []
    assert full["spellcasting"]["casters"] == []


async def test_the_knight_casts_with_intelligence_without_choosing_it(client):
    full = await _full(client, await _knight(client, 7, intelligence=16))
    caster = full["spellcasting"]["casters"][0]
    assert caster["ability"] == "intelligence" and caster["save_dc"] == 8 + 3 + 3 and caster["attack_bonus"] == 3 + 3


async def test_the_knight_slots_add_a_third_of_the_fighter_levels_to_other_casters(client):
    cid = await _knight(client, 9)  # 9 // 3 = 3
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "wizard", "level": 4, "hit_die": 6})
    assert r.status_code == 201, r.text
    totals = {s["level"]: s["total"] for s in (await _full(client, cid))["spell_slots"] if s["total"]}
    assert totals == {1: 4, 2: 3, 3: 3, 4: 1}  # livello di incantatore 3 + 4 = 7


async def test_a_spell_slot_is_recovered_by_a_long_rest(client):
    cid = await _knight(client, 5)
    spell = await _spell(client, cid, "Dardo incantato", 1)
    assert (await _cast(client, cid, spell, slot_level=1)).status_code == 200
    await client.post(f"/characters/{cid}/rest", json={"rest_type": "long", "confirm_early": True})
    assert [s["available"] for s in (await _full(client, cid))["spell_slots"] if s["level"] == 1] == [3]


# ---------------------------------------------------------------------------
# Limiti di scuola
# ---------------------------------------------------------------------------

def _school(full: dict) -> dict:
    return full["spellcasting"]["limits"][0]


@pytest.mark.parametrize("level,free", [(3, 1), (7, 1), (8, 2), (13, 2), (14, 3), (19, 3), (20, 4)])
async def test_the_spells_outside_abjuration_and_evocation_are_limited_to_the_free_picks(client, level, free):
    limits = _school(await _full(client, await _knight(client, level)))
    assert limits["school_free_limit"] == free and limits["school_names"] == ["abjuration", "evocation"]
    assert limits["school_outside_count"] == 0


async def test_only_the_spells_outside_the_two_schools_count(client):
    cid = await _knight(client, 3)
    await _spell(client, cid, "Scudo", 1, school="abjuration")
    await _spell(client, cid, "Dardo", 1, school="evocation")
    await _spell(client, cid, "Charme", 1, school="enchantment")
    assert _school(await _full(client, cid))["school_outside_count"] == 1
    await _spell(client, cid, "Sonno", 1, school="enchantment")
    limits = _school(await _full(client, cid))
    assert limits["school_outside_count"] == 2 > limits["school_free_limit"]


async def test_cantrips_and_spells_without_a_school_do_not_count_as_outside(client):
    cid = await _knight(client, 3)
    await _spell(client, cid, "Luce", 0, school="evocation")
    await _spell(client, cid, "Mano magica", 0, school="conjuration")
    await _spell(client, cid, "Strano", 1)
    assert _school(await _full(client, cid))["school_outside_count"] == 0


async def test_the_italian_names_of_the_schools_are_recognised(client):
    cid = await _knight(client, 3)
    await _spell(client, cid, "Scudo", 1, school="Abiurazione")
    await _spell(client, cid, "Dardo", 1, school="Invocazione")
    assert _school(await _full(client, cid))["school_outside_count"] == 0


async def test_other_classes_have_no_school_limit(client):
    cid = await _knight(client, 3)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "wizard", "level": 2, "hit_die": 6})
    assert r.status_code == 201, r.text
    wizard = next(x for x in (await _full(client, cid))["spellcasting"]["limits"] if x["class_name"].lower() in ("wizard", "mago"))
    assert wizard["school_free_limit"] is None


# ---------------------------------------------------------------------------
# Magia da Guerra
# ---------------------------------------------------------------------------

async def test_war_magic_is_offered_after_a_cantrip_cast_with_the_action_and_costs_the_bonus_action(client):
    cid = await _knight(client, 7)
    sword = await _sword(client, cid)
    assert WAR_MAGIC not in await _roll_keys(client, cid, "attack", item_id=sword)
    cantrip = await _spell(client, cid, "Raggio di fuoco", 0)
    assert (await _cast(client, cid, cantrip)).status_code == 200
    assert WAR_MAGIC in await _roll_keys(client, cid, "attack", item_id=sword)
    r = await _attack(client, cid, sword, options=[WAR_MAGIC])
    assert r.status_code == 200, r.text
    turn = await _turn(client, cid)
    assert turn["bonus_used"] is True and turn["action_attacks"] == 0 and turn["attacks_made"] == 1
    assert WAR_MAGIC not in await _roll_keys(client, cid, "attack", item_id=sword)  # l'azione bonus è spesa


async def test_war_magic_is_not_offered_after_a_leveled_spell_or_a_bonus_action_cantrip(client):
    cid = await _knight(client, 7)
    sword = await _sword(client, cid)
    leveled = await _spell(client, cid, "Dardo incantato", 1)
    await _cast(client, cid, leveled, slot_level=1)
    assert WAR_MAGIC not in await _roll_keys(client, cid, "attack", item_id=sword)
    await client.post(f"/characters/{cid}/turn/new")
    quick = await _spell(client, cid, "Colpo rapido", 0, casting_time="1 azione bonus")
    await _cast(client, cid, quick)
    assert WAR_MAGIC not in await _roll_keys(client, cid, "attack", item_id=sword)


async def test_war_magic_is_gone_at_the_next_turn(client):
    cid = await _knight(client, 7)
    sword = await _sword(client, cid)
    await _cast(client, cid, await _spell(client, cid, "Raggio", 0))
    await client.post(f"/characters/{cid}/turn/new")
    assert WAR_MAGIC not in await _roll_keys(client, cid, "attack", item_id=sword)


async def test_war_magic_is_for_the_knight_from_level_7_only(client):
    cid = await _knight(client, 6)
    sword = await _sword(client, cid)
    await _cast(client, cid, await _spell(client, cid, "Raggio", 0))
    assert WAR_MAGIC not in await _roll_keys(client, cid, "attack", item_id=sword)
    other = await _fighter(client, 7, "champion")
    assert WAR_MAGIC not in await _roll_keys(client, other, "attack", item_id=await _sword(client, other))


async def test_improved_war_magic_also_works_after_a_leveled_spell(client):
    cid = await _knight(client, 18)
    sword = await _sword(client, cid)
    leveled = await _spell(client, cid, "Dardo incantato", 1)
    await _cast(client, cid, leveled, slot_level=1)
    keys = await _roll_keys(client, cid, "attack", item_id=sword)
    assert IMPROVED in keys and WAR_MAGIC not in keys  # Magia da Guerra vale solo per i trucchetti
    assert (await _attack(client, cid, sword, options=[IMPROVED])).status_code == 200
    assert (await _turn(client, cid))["bonus_used"] is True


async def test_improved_war_magic_does_not_exist_before_level_18(client):
    cid = await _knight(client, 17)
    sword = await _sword(client, cid)
    await _cast(client, cid, await _spell(client, cid, "Dardo incantato", 1), slot_level=1)
    assert IMPROVED not in await _roll_keys(client, cid, "attack", item_id=sword)


# ---------------------------------------------------------------------------
# Colpo Mistico
# ---------------------------------------------------------------------------

async def _hit(client, cid, wid, **body) -> dict:
    r = await client.post(f"/characters/{cid}/items/{wid}/attack",
                          json={"die": 15, "defer_damage": True, "confirm_extra_attack": True, **body})
    assert r.status_code == 200, r.text
    return r.json()


async def test_eldritch_strike_marks_the_target_and_remembers_it_for_the_next_spell(client):
    cid = await _knight(client, 10)
    sword = await _sword(client, cid)
    assert STRIKE in await _roll_keys(client, cid, "attack", item_id=sword)
    hit = await _hit(client, cid, sword)
    r = await client.post(f"/characters/{cid}/attack/{hit['attack_id']}/damage", json={"options": [STRIKE]})
    assert r.status_code == 200, r.text
    block = r.json()["option_result"]
    assert block["targets"] == [STRIKE] and "svantaggio" in block["effects"][0]["it"]
    effect = (await client.get(f"/characters/{cid}/target-effects/{STRIKE}")).json()["result"]
    assert effect["condition"] == "custom:eldritch_strike" and effect["ends_at"] == {"anchor": "source", "edge": "end", "count": 1}
    assert any(s["key"] == "eldritch_strike" for s in (await _full(client, cid))["active_states"])


async def test_eldritch_strike_gives_the_next_save_spell_a_note_and_is_used_up(client):
    cid = await _knight(client, 10)
    sword = await _sword(client, cid)
    hit = await _hit(client, cid, sword)
    await client.post(f"/characters/{cid}/attack/{hit['attack_id']}/damage", json={"options": [STRIKE]})
    saver = await _spell(client, cid, "Ragnatela", 2, attack_save="DEX")
    attacker = await _spell(client, cid, "Dardo di fuoco", 0, attack_save="ATK")
    assert STRIKE_CAST not in await _roll_keys(client, cid, "cast", spell_id=attacker)  # solo contro un TS
    assert STRIKE_CAST in await _roll_keys(client, cid, "cast", spell_id=saver)
    r = await _cast(client, cid, saver, slot_level=2, options=[STRIKE_CAST])
    assert r.status_code == 200, r.text
    assert "svantaggio" in r.json()["option_result"]["effects"][0]["it"]
    assert STRIKE_CAST not in await _roll_keys(client, cid, "cast", spell_id=saver)
    assert not [s for s in (await _full(client, cid))["active_states"] if s["key"] == "eldritch_strike"]


async def test_eldritch_strike_is_not_offered_to_other_subclasses_or_before_level_10(client):
    sword_of = {}
    for sub, level in (("eldritch_knight", 9), ("champion", 10)):
        cid = await _fighter(client, level, sub)
        sword_of[sub] = STRIKE in await _roll_keys(client, cid, "attack", item_id=await _sword(client, cid))
    assert sword_of == {"eldritch_knight": False, "champion": False}


# ---------------------------------------------------------------------------
# Carica Arcana
# ---------------------------------------------------------------------------

async def test_arcane_charge_is_a_choice_of_action_surge_for_the_knight_from_level_15(client):
    cid = await _knight(client, 15)
    row = await _ability(client, cid, AS)
    assert [t["key"] for t in row["use_toggles"]] == ["arcane_charge"]
    r = await _use(client, cid, AS, params={"arcane_charge": True})
    assert r.status_code == 200 and r.json()["notes"] == ["arcane_charge"]
    assert (await _turn(client, cid))["extra_actions"] == 1  # l'azione in più c'è comunque


async def test_action_surge_without_the_choice_has_no_note(client):
    cid = await _knight(client, 15)
    assert (await _use(client, cid, AS)).json()["notes"] == []


@pytest.mark.parametrize("subclass,level", [("eldritch_knight", 14), ("champion", 15), ("battle_master", 15)])
async def test_arcane_charge_is_not_offered_elsewhere(client, subclass, level):
    cid = await _fighter(client, level, subclass)
    assert (await _ability(client, cid, AS))["use_toggles"] in (None, [])
    r = await _use(client, cid, AS, params={"arcane_charge": True})
    assert r.json()["notes"] == []


# ---------------------------------------------------------------------------
# Arma Vincolata
# ---------------------------------------------------------------------------

async def _bond(client, cid, wid, **body):
    return await client.post(f"/characters/{cid}/items/{wid}/bond", json=body)


async def _item_meta(client, cid, wid) -> dict:
    item = next(i for i in (await _full(client, cid))["items"] if i["id"] == wid)
    meta = item["item_metadata"]
    import json
    return json.loads(meta) if isinstance(meta, str) else (meta or {})


async def test_weapon_bond_is_a_panel_feature_of_the_knight_from_level_3(client):
    cid = await _knight(client, 3)
    row = await _ability(client, cid, BOND)
    assert row["use_panel"] == "weapon_bond" and row["action_type"] == "bonus_action"
    r = await _use(client, cid, BOND)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "needs_panel"
    assert await _ability(client, await _fighter(client, 3, "champion"), BOND) is None


async def test_the_ritual_bonds_up_to_two_weapons_and_a_third_needs_one_to_be_broken(client):
    cid = await _knight(client, 3)
    a, b, c = [await _sword(client, cid) for _ in range(3)]
    assert (await _bond(client, cid, a)).status_code == 200 and (await _bond(client, cid, b)).status_code == 200
    assert (await _item_meta(client, cid, a)).get("bonded") is True
    r = await _bond(client, cid, c)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "bond_limit"
    assert not (await _item_meta(client, cid, c)).get("bonded")
    r = await _bond(client, cid, c, replace_item_id=a)
    assert r.status_code == 200, r.text
    assert not (await _item_meta(client, cid, a)).get("bonded") and (await _item_meta(client, cid, c)).get("bonded") is True


async def test_the_replaced_weapon_must_be_one_of_the_bonded_ones(client):
    cid = await _knight(client, 3)
    a, b, c = [await _sword(client, cid) for _ in range(3)]
    await _bond(client, cid, a)
    await _bond(client, cid, b)
    r = await _bond(client, cid, c, replace_item_id=c)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_replacement"


async def test_bonding_the_same_weapon_twice_changes_nothing(client):
    cid = await _knight(client, 3)
    a, b = await _sword(client, cid), await _sword(client, cid)
    await _bond(client, cid, a)
    await _bond(client, cid, b)
    assert (await _bond(client, cid, a)).status_code == 200
    assert (await _item_meta(client, cid, b)).get("bonded") is True


async def test_only_the_knight_bonds_and_only_weapons(client):
    champion = await _fighter(client, 5, "champion")
    assert (await _bond(client, champion, await _sword(client, champion))).status_code == 409
    cid = await _knight(client, 3)
    shield = (await client.post(f"/characters/{cid}/items", json={"name": "Scudo", "item_type": "shield"})).json()["items"][0]["id"]
    assert (await _bond(client, cid, shield)).status_code == 422


async def test_breaking_the_bond_frees_the_slot(client):
    cid = await _knight(client, 3)
    a = await _sword(client, cid)
    await _bond(client, cid, a)
    assert (await client.delete(f"/characters/{cid}/items/{a}/bond")).status_code == 200
    assert not (await _item_meta(client, cid, a)).get("bonded")


async def test_summoning_puts_the_bonded_weapon_in_a_free_hand_with_the_bonus_action(client):
    cid = await _knight(client, 3)
    a = await _sword(client, cid)
    await _bond(client, cid, a)
    r = await client.post(f"/characters/{cid}/items/{a}/summon")
    assert r.status_code == 200, r.text
    item = next(i for i in r.json()["items"] if i["id"] == a)
    assert item["is_equipped"] is True and item["equipment_slot"] == "main_hand"
    assert (await _turn(client, cid))["bonus_used"] is True


async def test_summoning_needs_a_bonded_weapon_a_free_bonus_action_and_a_free_hand_and_costs_nothing_if_refused(client):
    cid = await _knight(client, 3)
    a, b = await _sword(client, cid), await _sword(client, cid)
    r = await client.post(f"/characters/{cid}/items/{a}/summon")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "not_bonded"
    await _bond(client, cid, a)
    await client.post(f"/characters/{cid}/turn/use", json={"slot": "bonus"})
    r = await client.post(f"/characters/{cid}/items/{a}/summon")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "turn_slot_used"
    await client.post(f"/characters/{cid}/turn/new")
    for iid, slot in ((b, "main_hand"),):
        await client.patch(f"/characters/{cid}/items/{iid}", json={"is_equipped": True, "equipment_slot": slot})
    shield = (await client.post(f"/characters/{cid}/items", json={"name": "Scudo", "item_type": "shield", "is_equipped": True,
                                                                 "equipment_slot": "off_hand"})).json()["items"][-1]["id"]
    assert shield
    r = await client.post(f"/characters/{cid}/items/{a}/summon")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_free_hand"
    assert (await _turn(client, cid))["bonus_used"] is False


async def test_a_weapon_already_in_hand_is_not_summoned_again(client):
    cid = await _knight(client, 3)
    a = await _sword(client, cid)
    await _bond(client, cid, a)
    await client.patch(f"/characters/{cid}/items/{a}", json={"is_equipped": True, "equipment_slot": "main_hand"})
    r = await client.post(f"/characters/{cid}/items/{a}/summon")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "already_in_hand"
