"""Ladro 2024 (Task 39, parte B): Mistificatore Arcano, Assassino, Coltello dell'Anima e Furfante.
Valori da ``docs/superpowers/rules/2024/classes/rogue.md``."""
from __future__ import annotations

import pytest

from core.rules.catalog import features_for
from tests.integration.rules.test_2014_bard import _ability, _full, _keys_of, _roll_keys, _skills, _use
from tests.integration.rules.test_2014_fighter_battle_master import _fixed
from tests.integration.rules.test_2014_fighter_eldritch_knight import KNOWN, SLOTS, _cast, _spell
from tests.integration.rules.test_2014_paladin import _new_turn, _rest, _turn
from tests.integration.rules.test_2014_rogue_thief import _order, _reflexes_encounter
from tests.integration.rules.test_2014_rogue import _damage, _hit, _rapier, _rogue, _skill_roll
from tests.integration.rules.test_2014_rogue_trickster import _with_hand

SUBS = {"arcane_trickster": "Mistificatore Arcano", "assassin": "Assassino", "soulknife": "Coltello dell'Anima", "thief": "Furfante"}
SNEAK, PSI = "rogue.sneak_attack", "rogue.psionic_power"
ROWS = {
    "arcane_trickster": {3: {"mage_hand_legerdemain"}, 9: {"magical_ambush"}, 13: {"versatile_trickster"}, 17: {"spell_thief"}},
    "assassin": {3: {"assassinate", "assassins_tools"}, 9: {"infiltration_expertise"}, 13: {"envenom_weapons"}, 17: {"death_strike"}},
    "soulknife": {3: {"psionic_power", "psi_bolstered_knack", "psychic_whispers", "psychic_blades"},
                  9: {"soul_blades", "homing_strikes", "psychic_teleportation"}, 13: {"psychic_veil"}, 17: {"rend_mind"}},
    "thief": {3: {"fast_hands", "second_story_work"}, 9: {"supreme_sneak"}, 13: {"use_magic_device"}, 17: {"thiefs_reflexes"}},
}


def _k(name: str) -> str:
    return f"rogue.{name}"


async def _sub(client, sub, level=9, **scores) -> int:
    body = {"name": "Ladro", "initial_class": {"class_name": "rogue", "level": level, "subclass": SUBS[sub]}}
    r = await client.post("/characters", json=body)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    for ability, value in scores.items():
        assert (await client.patch(f"/characters/{cid}/ability_scores/{ability}", json={"value": value})).status_code == 200
    return cid


async def _blade(client, cid, *options, die=15, **body):
    r = await client.post(f"/characters/{cid}/attack/unarmed",
                          json={"die": die, "defer_damage": True, "confirm_extra_attack": True, "options": list(options), **body})
    assert r.status_code == 200, r.text
    return r.json()


async def _roll_keys_unarmed(client, cid) -> list[str]:
    return await _roll_keys(client, cid, "attack")


# ---------------------------------------------------------------------------
# Catalogo e livelli
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("sub", list(ROWS))
async def test_each_row_appears_at_its_level_and_only_for_its_subclass(client, sub):
    for level, names in ROWS[sub].items():
        before, after = await _keys_of(client, await _sub(client, sub, level - 1)), await _keys_of(client, await _sub(client, sub, level))
        wanted = {_k(n) for n in names}
        assert not before & wanted and wanted <= after, (sub, level)
    others = set().union(*({_k(n) for ns in rows.values() for n in ns} for s, rows in ROWS.items() if s != sub))
    assert not others & await _keys_of(client, await _sub(client, sub, 20))


def test_every_subclass_mapping_title_has_its_row_with_both_languages():
    titles = {f.source_title for f in features_for("2024", "rogue")}
    mapping = open("docs/superpowers/rules/mapping/2024/rogue.md", encoding="utf-8").read().splitlines()[4:]
    wanted = [line.split("|")[1].strip() for line in mapping if line.startswith("|")]
    subs = [t for t in wanted if any(s in t for s in ("Mistificatore Arcano", "Assassino ", "Coltello dell'Anima", "Furfante "))]
    assert len(subs) == 24 and [t for t in subs if t not in titles] == []
    assert all(f.summary["it"] and f.summary["en"] and len(f.summary["it"]) <= 200 for f in features_for("2024", "rogue"))


# ---------------------------------------------------------------------------
# Mistificatore Arcano
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level", [3, 7, 10, 13, 19])
async def test_arcane_trickster_slots_cantrips_and_prepared_follow_the_2024_table(client, level):
    full = await _full(client, await _sub(client, "arcane_trickster", level, intelligence=16))
    totals = tuple(s["total"] for s in sorted(full["spell_slots"], key=lambda s: s["level"]) if s["total"])
    limits = full["spellcasting"]["limits"][0]
    assert totals == SLOTS[level]
    assert (limits["cantrips_limit"], limits["prepared_limit"]) == (4 if level >= 10 else 3, KNOWN[level])
    assert full["spellcasting"]["casters"][0]["ability"] == "intelligence"


async def test_a_rogue_of_another_subclass_does_not_cast(client):
    full = await _full(client, await _sub(client, "thief", 10))
    assert not [s for s in full["spell_slots"] if s["total"]] and full["spellcasting"]["casters"] == []


async def test_legerdemain_is_a_bonus_action_that_needs_mage_hand(client):
    cid = await _sub(client, "arcane_trickster", 3)
    refused = await _use(client, cid, _k("mage_hand_legerdemain"))
    assert refused.status_code == 409 and refused.json()["detail"]["code"] == "feature_unavailable"
    await _with_hand(client, cid)
    assert (await _use(client, cid, _k("mage_hand_legerdemain"))).status_code == 200
    assert (await _turn(client, cid))["bonus_used"] is True


async def test_magical_ambush_needs_the_invisible_condition_and_a_save_spell(client):
    cid = await _sub(client, "arcane_trickster", 9)
    web = await _spell(client, cid, "Ragnatela", 2, attack_save="DEX")
    ray = await _spell(client, cid, "Raggio di fuoco", 0, attack_save="ATK")
    key = _k("magical_ambush_cast")
    assert key not in await _roll_keys(client, cid, "cast", spell_id=web)  # non sei invisibile
    assert (await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"invisible": True}})).status_code == 200
    assert key in await _roll_keys(client, cid, "cast", spell_id=web) and key not in await _roll_keys(client, cid, "cast", spell_id=ray)
    r = await _cast(client, cid, web, slot_level=2, options=[key])
    assert r.status_code == 200, r.text
    effect = (await client.get(f"/characters/{cid}/target-effects/{key}")).json()["result"]
    assert effect["condition"] == "custom:magical_ambush"
    low = await _sub(client, "arcane_trickster", 8)
    assert key not in await _roll_keys(client, low, "cast", spell_id=await _spell(client, low, "Ragnatela", 2, attack_save="DEX"))


async def _trip_text(client, cid) -> str:
    wid = await _rapier(client, cid)
    await _new_turn(client, cid)
    hit = await _hit(client, cid, wid, mode="advantage", dice=[10, 12])
    resp = await _damage(client, cid, hit, SNEAK, _k("trip"))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    return " ".join(e["it"] for e in body["option_result"]["effects"])


async def test_versatile_trickster_adds_the_second_creature_to_trip_with_mage_hand(client):
    cid = await _sub(client, "arcane_trickster", 13, dexterity=16)
    plain = await _trip_text(client, cid)
    assert "mano spettrale" not in plain
    await _with_hand(client, cid)
    assert "mano spettrale" in await _trip_text(client, cid)
    assert "mano spettrale" not in await _trip_text(client, await _sub(client, "arcane_trickster", 12, dexterity=16))


async def test_spell_thief_is_one_reaction_use_per_long_rest_with_the_spell_dc(client):
    cid = await _sub(client, "arcane_trickster", 17, intelligence=16)
    row = await _ability(client, cid, _k("spell_thief"))
    assert (row["max_uses"], row["action_type"], row["dc"]) == (1, "reaction", 8 + 3 + 6)
    r = await _use(client, cid, _k("spell_thief"), params={"stolen": True, "spell_level": "1", "spell": "Dardo Incantato"})
    assert r.status_code == 200, r.text
    assert (await _turn(client, cid))["reaction_used"] is True and (await _ability(client, cid, _k("spell_thief")))["uses"] == 0
    names = {s["name"] for s in (await client.get(f"/characters/{cid}/spells")).json()}
    assert "Dardo Incantato" in names


# ---------------------------------------------------------------------------
# Assassino
# ---------------------------------------------------------------------------

async def test_assassinate_gives_advantage_on_initiative_and_on_the_first_round_attack(client):
    cid, other = await _sub(client, "assassin", 3), await _sub(client, "thief", 3)
    assert (await client.post(f"/characters/{cid}/dice/initiative", json={"dice": [3, 9]})).json()["mode_applied"] == "advantage"
    assert (await client.post(f"/characters/{other}/dice/initiative", json={"die": 9})).json()["mode_applied"] == "normal"
    wid = await _rapier(client, cid)
    assert _k("assassinate_advantage") in await _roll_keys(client, cid, "attack", item_id=wid)
    r = await client.post(f"/characters/{cid}/items/{wid}/attack", json={"dice": [4, 15], "options": [_k("assassinate_advantage")]})
    assert r.json()["mode_applied"] == "advantage" and r.json()["to_hit_die"] == 15


async def test_assassinate_adds_the_rogue_level_to_a_sneak_attack_that_hits(client, monkeypatch):
    _fixed(monkeypatch, 3)
    cid = await _sub(client, "assassin", 9, dexterity=16)
    wid = await _rapier(client, cid)
    key = _k("assassinate_damage")
    hit = await _hit(client, cid, wid, mode="advantage", dice=[10, 12])
    plain = (await _damage(client, cid, hit, SNEAK)).json()
    await _new_turn(client, cid)
    hit = await _hit(client, cid, wid, mode="advantage", dice=[10, 12])
    extra = (await _damage(client, cid, hit, SNEAK, key)).json()
    assert extra["damage_total"] - extra["option_result"]["extra_total"] == plain["damage_total"] - plain["option_result"]["extra_total"] + 9
    refused = await _damage(client, cid, await _hit(client, cid, wid), key)  # senza l'Attacco Furtivo
    assert refused.status_code == 409


async def test_assassins_tools_grant_the_proficiencies_and_the_poison_option_without_a_kit_in_the_bag(client):
    cid = await _sub(client, "assassin", 5)
    tools = (await _full(client, cid))["tool_proficiencies"]
    assert tools.get("disguise_kit") is True and tools.get("poisoners_kit") is True
    wid = await _rapier(client, cid)
    assert _k("poison") in await _roll_keys(client, cid, "attack", item_id=wid)
    other = await _sub(client, "thief", 5)
    assert _k("poison") not in await _roll_keys(client, other, "attack", item_id=await _rapier(client, other))


async def test_steady_aim_keeps_the_speed_for_the_assassin_from_level_9(client):
    for level, sub, zero in ((8, "assassin", True), (9, "assassin", False), (9, "thief", True)):
        cid = await _sub(client, sub, level)
        assert (await _use(client, cid, _k("steady_aim"))).status_code == 200
        speed = (await _full(client, cid))["computed"]["speed"]
        assert (speed == 0) is zero, (level, sub)


async def test_envenom_weapons_adds_2d6_poison_when_the_poison_save_fails(client):
    cid = await _sub(client, "assassin", 13, dexterity=16)
    wid = await _rapier(client, cid)
    key = _k("envenom_weapons")
    hit = await _hit(client, cid, wid, mode="advantage", dice=[10, 12])
    assert (await _damage(client, cid, hit, SNEAK, key)).status_code == 409  # senza Veleno
    plain = (await _damage(client, cid, await _hit(client, cid, wid, mode="advantage", dice=[10, 12]), SNEAK, _k("poison"))).json()
    await _new_turn(client, cid)
    both = (await _damage(client, cid, await _hit(client, cid, wid, mode="advantage", dice=[10, 12]), SNEAK, _k("poison"), key)).json()
    assert len(both["option_result"]["extra_rolls"]) == len(plain["option_result"]["extra_rolls"]) + 2
    low = await _sub(client, "assassin", 12)
    assert key not in await _roll_keys(client, low, "attack", item_id=await _rapier(client, low))


async def test_death_strike_doubles_a_sneak_attack_hit_and_shows_the_dc(client, monkeypatch):
    _fixed(monkeypatch, 3)
    cid = await _sub(client, "assassin", 17, dexterity=16)  # CD 8 + 6 + 3
    wid = await _rapier(client, cid)
    key = _k("death_strike")
    hit = await _hit(client, cid, wid, mode="advantage", dice=[10, 12])
    base = (await _damage(client, cid, hit, SNEAK)).json()
    await _new_turn(client, cid)
    hit = await _hit(client, cid, wid, mode="advantage", dice=[10, 12])
    done = (await _damage(client, cid, hit, SNEAK, key)).json()
    assert done["damage_total"] == 2 * base["damage_total"]
    assert "17" in " ".join(e["it"] for e in done["option_result"]["effects"])
    assert (await _damage(client, cid, await _hit(client, cid, wid), key)).status_code == 409


# ---------------------------------------------------------------------------
# Coltello dell'Anima
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,dice,sides", [(3, 4, 6), (5, 6, 8), (9, 8, 8), (11, 8, 10), (13, 10, 10), (17, 12, 12)])
async def test_psionic_energy_dice_follow_the_table(client, level, dice, sides, monkeypatch):
    cid = await _sub(client, "soulknife", level, dexterity=16)
    row = await _ability(client, cid, PSI)
    assert (row["max_uses"], row["is_pool"]) == (dice, True)
    _fixed(monkeypatch, 99)
    assert (await _use(client, cid, _k("psychic_whispers"))).json()["rolls"] == [sides]


async def test_a_short_rest_gives_back_one_die_and_a_long_rest_all(client):
    cid = await _sub(client, "soulknife", 5)
    row = await _ability(client, cid, PSI)
    await client.patch(f"/characters/{cid}/abilities/{row['id']}", json={"uses": 1})
    await _rest(client, cid, "short")
    assert (await _ability(client, cid, PSI))["uses"] == 2
    await _rest(client, cid, "long")
    assert (await _ability(client, cid, PSI))["uses"] == 6


async def test_psychic_whispers_is_free_once_then_costs_a_die(client):
    cid = await _sub(client, "soulknife", 3)
    key = _k("psychic_whispers")
    assert (await _use(client, cid, key)).status_code == 200
    assert (await _ability(client, cid, PSI))["uses"] == 4 and (await _turn(client, cid))["action_used"] is True
    await _new_turn(client, cid)
    assert (await _use(client, cid, key)).json()["detail"]["code"] == "no_uses"
    assert (await _use(client, cid, key, params={"restore": True})).status_code == 200
    assert (await _ability(client, cid, PSI))["uses"] == 3


async def test_psi_bolstered_knack_adds_the_die_to_a_proficient_skill_and_pays_only_on_success(client, monkeypatch):
    cid = await _sub(client, "soulknife", 3)
    key = _k("psi_bolstered_knack")
    await _skills(client, cid, stealth=1)
    assert key in await _roll_keys(client, cid, "skill", skill="stealth") and key not in await _roll_keys(client, cid, "skill", skill="arcana")
    _fixed(monkeypatch, 4)
    first = (await client.post(f"/characters/{cid}/skills/stealth/roll", json={"die": 5})).json()
    r = await client.post(f"/characters/{cid}/last-roll/options", json={"options": [key]})
    assert r.status_code == 200, r.text
    assert r.json()["total"] == first["total"] + 4 and (await _ability(client, cid, PSI))["uses"] == 3
    assert (await client.post(f"/characters/{cid}/last-roll/refund")).status_code == 200
    assert (await _ability(client, cid, PSI))["uses"] == 4


async def test_psychic_blades_attack_with_the_best_of_strength_and_dexterity_for_psychic_damage(client, monkeypatch):
    cid = await _sub(client, "soulknife", 3, dexterity=16, strength=8)
    blade = _k("psychic_blade")
    assert blade in await _roll_keys_unarmed(client, cid)
    _fixed(monkeypatch, 4)
    hit = await _blade(client, cid, blade)
    assert hit["damage_type"] == "psychic" and hit["to_hit_bonus"] == 3 + 2 and hit["damage_dice"] == "1d6"
    assert hit["damage_total"] == 4 + 3
    strong = await _sub(client, "soulknife", 3, dexterity=10, strength=18)
    assert (await _blade(client, strong, blade))["to_hit_bonus"] == 4 + 2
    plain = await _sub(client, "thief", 3)
    assert blade not in await _roll_keys_unarmed(client, plain)


async def test_the_second_blade_is_a_d4_bonus_action_after_the_first_attack(client, monkeypatch):
    cid = await _sub(client, "soulknife", 3, dexterity=16)
    first, second = _k("psychic_blade"), _k("psychic_blade_bonus")
    assert second not in await _roll_keys_unarmed(client, cid)
    _fixed(monkeypatch, 3)
    await _blade(client, cid, first)
    assert second in await _roll_keys_unarmed(client, cid)
    hit = await _blade(client, cid, second)
    assert hit["damage_dice"] == "1d4" and (await _turn(client, cid))["bonus_used"] is True
    await _new_turn(client, cid)
    assert second not in await _roll_keys_unarmed(client, cid)


async def test_sneak_attack_works_with_a_psychic_blade(client):
    cid = await _sub(client, "soulknife", 5, dexterity=16)
    hit = await _blade(client, cid, _k("psychic_blade"), mode="advantage", dice=[10, 12])
    done = await _damage(client, cid, hit, SNEAK)
    assert done.status_code == 200, done.text
    assert len(done.json()["option_result"]["extra_rolls"]) == 3


async def test_homing_strikes_add_the_die_to_a_blade_attack_from_level_9(client):
    cid = await _sub(client, "soulknife", 9, dexterity=16)
    key = _k("homing_strikes")
    await _blade(client, cid, _k("psychic_blade"), die=5)
    assert key in await _roll_keys(client, cid, "attack")
    assert key not in await _roll_keys(client, await _sub(client, "soulknife", 8), "attack")
    r = await client.post(f"/characters/{cid}/last-roll/options", json={"options": [key]})
    assert r.status_code == 200, r.text
    assert (await _ability(client, cid, PSI))["uses"] == 7


async def test_psychic_teleportation_spends_and_rolls_a_die_as_a_bonus_action(client, monkeypatch):
    cid = await _sub(client, "soulknife", 9)
    _fixed(monkeypatch, 5)
    r = await _use(client, cid, _k("psychic_teleportation"))
    assert r.status_code == 200, r.text
    assert r.json()["rolls"] == [5] and (await _ability(client, cid, PSI))["uses"] == 7
    assert (await _turn(client, cid))["bonus_used"] is True


async def test_psychic_veil_makes_you_invisible_for_an_hour_and_can_be_restored_by_a_die(client):
    cid = await _sub(client, "soulknife", 13)
    key = _k("psychic_veil")
    assert (await _use(client, cid, key)).status_code == 200
    full = await _full(client, cid)
    assert full["conditions"].get("invisible") and next(s for s in full["active_states"] if s["key"] == "psychic_veil")["rounds_left"] == 600
    await _new_turn(client, cid)
    assert (await _use(client, cid, key)).json()["detail"]["code"] == "no_uses"
    assert (await _use(client, cid, key, params={"restore": True})).status_code == 200
    assert (await _ability(client, cid, PSI))["uses"] == 9


async def test_rend_mind_stuns_after_a_blade_sneak_attack_for_a_use_or_three_dice(client):
    cid = await _sub(client, "soulknife", 17, dexterity=16)  # CD 8 + 6 + 3
    own, dice = _k("rend_mind"), _k("rend_mind_dice")
    hit = await _blade(client, cid, _k("psychic_blade"), mode="advantage", dice=[10, 12])
    assert (await _damage(client, cid, hit, own)).status_code == 409  # senza Attacco Furtivo
    done = await _damage(client, cid, await _blade(client, cid, _k("psychic_blade"), mode="advantage", dice=[10, 12]), SNEAK, own)
    assert done.status_code == 200, done.text
    effect = (await client.get(f"/characters/{cid}/target-effects/{own}")).json()["result"]
    assert (effect["condition"], effect["save_ability"], effect["save_dc"]) == ("stunned", "wisdom", 17)
    assert (await _ability(client, cid, own))["uses"] == 0
    await _new_turn(client, cid)
    again = await _damage(client, cid, await _blade(client, cid, _k("psychic_blade"), mode="advantage", dice=[10, 12]), SNEAK, own)
    assert again.status_code == 409
    paid = await _damage(client, cid, await _blade(client, cid, _k("psychic_blade"), mode="advantage", dice=[10, 12]), SNEAK, dice)
    assert paid.status_code == 200, paid.text
    assert (await _ability(client, cid, PSI))["uses"] == 12 - 3


# ---------------------------------------------------------------------------
# Furfante
# ---------------------------------------------------------------------------

async def test_fast_hands_is_a_bonus_action_with_two_options(client):
    cid = await _sub(client, "thief", 3)
    row = await _ability(client, cid, _k("fast_hands"))
    assert row["action_type"] == "bonus_action"
    assert (await _use(client, cid, _k("fast_hands"), params={"action": "dash"})).status_code == 422
    r = await _use(client, cid, _k("fast_hands"), params={"action": "sleight_of_hand"})
    assert r.status_code == 200, r.text
    assert "cunning_sleight_of_hand" in r.json()["notes"] and (await _turn(client, cid))["bonus_used"] is True


async def test_second_story_work_gives_a_climb_speed_and_a_dexterity_jump(client):
    thief, other = await _sub(client, "thief", 3, dexterity=18, strength=10), await _sub(client, "assassin", 3, dexterity=18, strength=10)
    full, plain = (await _full(client, thief))["computed"], (await _full(client, other))["computed"]
    assert full["climb_speed"] == full["speed"] and not plain.get("climb_speed")
    assert full["long_jump_bonus_ft"] == 8 and not plain.get("long_jump_bonus_ft")


async def test_supreme_sneak_is_a_one_die_cunning_strike_option_for_the_thief_from_level_9(client):
    cid = await _sub(client, "thief", 9, dexterity=16)
    wid = await _rapier(client, cid)
    key = _k("supreme_sneak")
    assert key in await _roll_keys(client, cid, "attack", item_id=wid)
    hit = await _hit(client, cid, wid, mode="advantage", dice=[10, 12])
    done = await _damage(client, cid, hit, SNEAK, key)
    assert done.status_code == 200, done.text
    assert len(done.json()["option_result"]["extra_rolls"]) == 4  # 5d6 meno 1
    for cid2 in (await _sub(client, "thief", 8), await _sub(client, "assassin", 9)):
        assert key not in await _roll_keys(client, cid2, "attack", item_id=await _rapier(client, cid2))


async def test_use_magic_device_raises_the_attunement_limit_to_four(client):
    async def attune(cid, n):
        r = await client.post(f"/characters/{cid}/items", json={
            "name": f"Anello {n}", "item_type": "magic_item", "item_metadata": {"requires_attunement": True, "attuned": True}})
        return r.status_code
    thief, other = await _sub(client, "thief", 13), await _sub(client, "thief", 12)
    assert [await attune(thief, n) for n in range(5)] == [201, 201, 201, 201, 409]
    assert [await attune(other, n) for n in range(4)] == [201, 201, 201, 409]


async def test_use_magic_device_roll_of_six_spends_no_charge(client, monkeypatch):
    cid = await _sub(client, "thief", 13)
    r = await client.post(f"/characters/{cid}/items", json={
        "name": "Bacchetta", "item_type": "magic_item", "item_metadata": {"charges": {"current": 5, "max": 7}}})
    iid = max(i["id"] for i in r.json()["items"])

    async def charges() -> int:
        item = next(i for i in (await _full(client, cid))["items"] if i["id"] == iid)
        return item["item_metadata"]["charges"]["current"]
    _fixed(monkeypatch, 6)
    await client.post(f"/characters/{cid}/items/{iid}/charges", json={"delta": -1, "spend": True})
    assert await charges() == 5
    _fixed(monkeypatch, 3)
    await client.post(f"/characters/{cid}/items/{iid}/charges", json={"delta": -1, "spend": True})
    assert await charges() == 4
    plain = await _sub(client, "thief", 12)
    r = await client.post(f"/characters/{plain}/items", json={
        "name": "Bacchetta", "item_type": "magic_item", "item_metadata": {"charges": {"current": 5, "max": 7}}})
    pid = max(i["id"] for i in r.json()["items"])
    _fixed(monkeypatch, 6)
    await client.post(f"/characters/{plain}/items/{pid}/charges", json={"delta": -1, "spend": True})
    item = next(i for i in (await _full(client, plain))["items"] if i["id"] == pid)
    assert item["item_metadata"]["charges"]["current"] == 4


async def test_thiefs_reflexes_is_a_row_of_the_2024_thief_at_17(client, test_session_factory):
    row = await _ability(client, await _sub(client, "thief", 17), _k("thiefs_reflexes"))
    assert row is not None and row["name"]
    # M9: il secondo turno dell'incontro vale anche per il Furfante 2024
    _sid, _cid, live = await _reflexes_encounter(client, test_session_factory, edition="2024")
    assert [i for _n, i in _order(live)] == [23, 13, 1] and "Riflessi" in _order(live)[1][0]


# ---------------------------------------------------------------------------
# Giro di correzione 1 (I1-I12)
# ---------------------------------------------------------------------------

async def _attune(client, cid, n) -> int:
    r = await client.post(f"/characters/{cid}/items", json={
        "name": f"Anello {n}", "item_type": "magic_item", "item_metadata": {"requires_attunement": True, "attuned": True}})
    return r.status_code


async def _wand(client, cid, current=5, spells=()) -> int:
    meta = {"charges": {"current": current, "max": 7}, "granted_spells": list(spells)}
    r = await client.post(f"/characters/{cid}/items", json={"name": "Bacchetta", "item_type": "magic_item", "item_metadata": meta})
    assert r.status_code == 201, r.text
    return max(i["id"] for i in r.json()["items"])


async def _charges(client, cid, iid) -> int:
    return next(i for i in (await _full(client, cid))["items"] if i["id"] == iid)["item_metadata"]["charges"]["current"]


async def test_i1_a_2014_thief_keeps_three_attunements_and_spends_charges_without_the_d6(client, monkeypatch):
    cid = await _rogue(client, 13, "thief")
    assert [await _attune(client, cid, n) for n in range(4)] == [201, 201, 201, 409]
    assert (await _full(client, cid))["computed"].get("attunement_limit", 3) == 3
    iid = await _wand(client, cid)
    _fixed(monkeypatch, 6)
    r = await client.post(f"/characters/{cid}/items/{iid}/charges", json={"delta": -1, "spend": True})
    assert r.status_code == 200 and await _charges(client, cid, iid) == 4
    assert not r.json().get("homebrew_notifications")


async def test_i2_the_server_says_the_attunement_limit(client):
    assert (await _full(client, await _sub(client, "thief", 13)))["computed"]["attunement_limit"] == 4
    assert (await _full(client, await _sub(client, "thief", 12)))["computed"]["attunement_limit"] == 3


async def test_i3_export_import_and_duplicate_accept_four_attunements_for_who_has_the_right(client):
    cid = await _sub(client, "thief", 13)
    for n in range(4):
        assert await _attune(client, cid, n) == 201
    assert (await client.post(f"/characters/{cid}/duplicate")).status_code == 201
    data = (await client.get(f"/characters/{cid}/export")).json()
    assert (await client.post("/characters/import", json=data)).status_code == 201
    data["character"]["rules_edition"] = "2014"  # senza il privilegio il limite resta 3
    refused = await client.post("/characters/import", json=data)
    assert refused.status_code == 422 and "attunement_limit" in refused.text


async def test_i7_a_six_spends_no_charge_whatever_the_delta_and_the_outcome_is_shown(client, monkeypatch):
    cid = await _sub(client, "thief", 13)
    iid = await _wand(client, cid, 5, spells=[{"name": "Dardo", "level": 1, "charges_cost": 2}])
    _fixed(monkeypatch, 6)
    r = await client.post(f"/characters/{cid}/items/{iid}/charges", json={"delta": -3, "spend": True})
    assert await _charges(client, cid, iid) == 5
    assert "6" in " ".join(n["message"] for n in r.json()["homebrew_notifications"])
    r = await client.post(f"/characters/{cid}/items/{iid}/cast", json={"spell_index": 0})
    assert r.status_code == 200 and await _charges(client, cid, iid) == 5 and r.json()["homebrew_notifications"]
    _fixed(monkeypatch, 3)
    r = await client.post(f"/characters/{cid}/items/{iid}/charges", json={"delta": -3, "spend": True})
    assert await _charges(client, cid, iid) == 2 and r.json()["homebrew_notifications"]
    _fixed(monkeypatch, 6)  # correzione a mano: nessun tiro
    r = await client.post(f"/characters/{cid}/items/{iid}/charges", json={"delta": -1})
    assert await _charges(client, cid, iid) == 1 and not r.json().get("homebrew_notifications")


async def _scroll(client, cid) -> int:
    r = await client.post(f"/characters/{cid}/items", json={
        "name": "Pergamena di Dardo", "item_type": "consumable", "quantity": 2, "item_metadata": {"subtype": "scroll"}})
    assert r.status_code == 201, r.text
    return max(i["id"] for i in r.json()["items"])


async def _qty(client, cid, iid) -> int:
    return next(i for i in (await _full(client, cid))["items"] if i["id"] == iid)["quantity"]


async def test_i6_scroll_cast_levels_0_and_1_always_work_higher_ones_need_an_arcana_check(client, monkeypatch):
    cid = await _sub(client, "thief", 13)  # Intelligenza 10, nessuna competenza in Arcano
    iid = await _scroll(client, cid)
    _fixed(monkeypatch, 1)
    r = await client.post(f"/characters/{cid}/items/{iid}/scroll", json={"spell_level": 1})
    assert r.status_code == 200, r.text
    assert await _qty(client, cid, iid) == 1 and r.json()["homebrew_notifications"][0]["severity"] == "success"
    r = await client.post(f"/characters/{cid}/items/{iid}/scroll", json={"spell_level": 3})  # CD 13, tiro 1
    note = r.json()["homebrew_notifications"][0]
    assert note["severity"] == "error" and "disintegra" in note["message"] and await _qty(client, cid, iid) == 0
    iid = await _scroll(client, cid)
    _fixed(monkeypatch, 20)
    r = await client.post(f"/characters/{cid}/items/{iid}/scroll", json={"spell_level": 3})
    assert r.json()["homebrew_notifications"][0]["severity"] == "success" and await _qty(client, cid, iid) == 1


async def test_i6_scroll_cast_is_for_use_magic_device_only_and_for_scrolls_only(client):
    other = await _sub(client, "thief", 12)
    assert (await client.post(f"/characters/{other}/items/{await _scroll(client, other)}/scroll", json={"spell_level": 1})).status_code == 409
    cid = await _sub(client, "thief", 13)
    assert (await client.post(f"/characters/{cid}/items/{await _wand(client, cid)}/scroll", json={"spell_level": 1})).status_code == 409


async def _hidden_thief(client) -> tuple[int, int]:
    cid = await _sub(client, "thief", 9, dexterity=16)
    wid = await _rapier(client, cid)
    await _skill_roll(client, cid, "stealth", die=20)
    assert (await client.post(f"/characters/{cid}/hide")).status_code == 200
    return cid, wid


async def test_i4_supreme_sneak_keeps_the_hiding_invisibility_after_the_attack(client):
    cid, wid = await _hidden_thief(client)
    hit = await _hit(client, cid, wid, mode="advantage", dice=[10, 12])
    assert (await _damage(client, cid, hit, SNEAK, _k("supreme_sneak"))).status_code == 200
    full = await _full(client, cid)
    assert full["conditions"]["invisible"] is True and "hiding" in full["settings"]
    plain, wid2 = await _hidden_thief(client)  # senza l'opzione l'attacco rompe il nascondiglio
    hit = await _hit(client, plain, wid2, mode="advantage", dice=[10, 12])
    assert (await _damage(client, plain, hit, SNEAK)).status_code == 200
    assert not (await _full(client, plain))["conditions"].get("invisible")


async def test_i5_the_psychic_veil_ends_when_the_soulknife_attacks(client):
    cid = await _sub(client, "soulknife", 13, dexterity=16)
    assert (await _use(client, cid, _k("psychic_veil"))).status_code == 200
    assert (await _full(client, cid))["conditions"]["invisible"] is True
    await _blade(client, cid, _k("psychic_blade"))
    full = await _full(client, cid)
    assert not full["conditions"].get("invisible") and not [s for s in full["active_states"] if s["key"] == "psychic_veil"]


async def _veiled(client) -> int:
    cid = await _sub(client, "soulknife", 13, dexterity=16)
    assert (await _use(client, cid, _k("psychic_veil"))).status_code == 200
    await _new_turn(client, cid)  # l'azione Magia del Velo è spesa: il lancio di prova ha bisogno di un turno nuovo
    return cid


async def _veil(client, cid) -> dict | None:
    return next((s for s in (await _full(client, cid))["active_states"] if s["key"] == "psychic_veil"), None)


async def test_n1_a_blade_hit_ends_the_veil_and_a_declared_miss_gives_it_back(client):
    cid = await _veiled(client)
    hit = await _blade(client, cid, _k("psychic_blade"))
    assert await _veil(client, cid) is None and not (await _full(client, cid))["conditions"].get("invisible")
    assert (await _damage(client, cid, hit)).status_code == 200  # il danno dice che il colpo è andato a segno
    assert await _veil(client, cid) is None
    assert (await client.post(f"/characters/{cid}/last-roll/refund", json={"succeeded": False})).status_code == 409

    cid = await _veiled(client)
    assert (await _blade(client, cid, _k("psychic_blade")))["refundable"]  # minori 46: il client sa che la domanda c'è già
    assert (await _turn(client, cid))["last_roll"]["refundable"]  # esce «Il tiro è riuscito?»
    assert (await client.post(f"/characters/{cid}/last-roll/refund", json={"succeeded": False})).status_code == 200
    veil = await _veil(client, cid)
    assert veil and veil["rounds_left"] == 600 and (await _full(client, cid))["conditions"]["invisible"] is True


async def test_n1_answering_that_the_attack_hit_keeps_the_veil_ended(client):
    cid = await _veiled(client)
    await _blade(client, cid, _k("psychic_blade"))
    assert (await client.post(f"/characters/{cid}/last-roll/refund", json={"succeeded": True})).status_code == 200
    assert await _veil(client, cid) is None


async def test_n1_a_natural_one_gives_the_veil_back_without_asking(client):
    cid = await _veiled(client)
    await _blade(client, cid, _k("psychic_blade"), mode="advantage", dice=[1, 1])
    assert await _veil(client, cid) is not None and not (await _turn(client, cid))["last_roll"]["refundable"]


@pytest.mark.parametrize("extra,ends", [
    ({"damage_dice": "1d10"}, True),
    ({"attack_save": "DEX"}, True),
    ({}, False),  # né danni né TS: il Velo resta
    ({"damage_dice": "1d10", "attack_save": "ATK"}, False),  # a decidere è il tiro per colpire
])
async def test_n1_a_spell_ends_the_veil_only_with_damage_or_a_save(client, extra, ends):
    cid = await _veiled(client)
    spell = await _spell(client, cid, "Prova", **extra)
    assert (await _cast(client, cid, spell)).status_code == 200
    assert (await _veil(client, cid) is None) is ends


async def test_i8_the_psychic_blades_defer_the_damage_by_themselves(client):
    cid = await _sub(client, "soulknife", 3, dexterity=16)
    listed = {o["key"]: o for o in (await client.get(f"/characters/{cid}/roll-options", params={"roll": "attack"})).json()}
    assert listed[_k("psychic_blade")].get("defers_damage") is True
    await _blade(client, cid, _k("psychic_blade"))
    listed = {o["key"]: o for o in (await client.get(f"/characters/{cid}/roll-options", params={"roll": "attack"})).json()}
    assert listed[_k("psychic_blade_bonus")].get("defers_damage") is True


async def test_i9_the_blade_arms_vex_for_the_next_attack(client):
    cid = await _sub(client, "soulknife", 3, dexterity=16)
    vex = _k("psychic_blade_vex")
    hit = await _blade(client, cid, _k("psychic_blade"))
    assert "mastery_vex_advantage" not in await _roll_keys_unarmed(client, cid)
    assert (await _damage(client, cid, hit, vex)).status_code == 200
    assert "mastery_vex_advantage" in await _roll_keys_unarmed(client, cid)


async def test_i11_envenom_weapons_poison_dice_do_not_double_on_a_critical(client):
    cid = await _sub(client, "assassin", 13, dexterity=16)
    wid = await _rapier(client, cid)
    plain = (await _damage(client, cid, await _hit(client, cid, wid, die=20, mode="advantage", dice=[20, 12]), SNEAK, _k("poison"))).json()
    await _new_turn(client, cid)
    both = (await _damage(client, cid, await _hit(client, cid, wid, die=20, mode="advantage", dice=[20, 12]), SNEAK, _k("poison"), _k("envenom_weapons"))).json()
    assert both["is_critical"] and len(both["option_result"]["extra_rolls"]) == len(plain["option_result"]["extra_rolls"]) + 2


async def test_i12_homing_strikes_need_the_psychic_blade(client):
    cid = await _sub(client, "soulknife", 9, dexterity=16)
    r = await client.post(f"/characters/{cid}/attack/unarmed", json={"die": 5, "defer_damage": True, "confirm_extra_attack": True})
    assert r.status_code == 200, r.text
    refused = await client.post(f"/characters/{cid}/last-roll/options", json={"options": [_k("homing_strikes")]})
    assert refused.status_code == 409


def test_minori_46_a_feature_attack_saves_the_roll_so_a_declared_miss_gives_the_veil_back():
    from types import SimpleNamespace

    from api.services.rules_states import end_on_feature_attack
    from core.rules.states import begin_state
    from core.rules.catalog import features_for

    spec = next(f.on_use.state for f in features_for("2024", "rogue") if f.key.endswith("psychic_veil"))
    for die, back in ((12, False), (1, True)):
        char = SimpleNamespace(conditions={}, active_states=[], settings={}, turn_state={}, spells=[], abilities=[])
        begin_state(char, spec, "psychic_veil", "rogue.psychic_veil")
        end_on_feature_attack(char, {"die": die, "dice": [die], "mode": "normal", "bonus": 5, "total": die + 5, "notes": [],
                                     "is_fumble": die == 1, "is_critical": False})
        last = char.turn_state["last_roll"]
        assert last["roll"] == "attack" and last["die"] == die and "miss_refund" not in char.turn_state
        assert bool(char.conditions.get("invisible")) is back and bool(last["refundable"]) is not back  # su un 12 il giocatore dichiara il mancato


async def test_minori_32_scroll_outcome_follows_the_request_language(client, monkeypatch):
    from api.auth import get_current_lang
    from api.main import app
    cid = await _sub(client, "thief", 13)
    iid = await _scroll(client, cid)
    _fixed(monkeypatch, 1)
    app.dependency_overrides[get_current_lang] = lambda: "en"
    try:
        r = await client.post(f"/characters/{cid}/items/{iid}/scroll", json={"spell_level": 3})
        assert "disintegrates" in r.json()["homebrew_notifications"][0]["message"]
        iid = await _scroll(client, cid)
        r = await client.post(f"/characters/{cid}/items/{iid}/scroll", json={"spell_level": 1})
        assert "cast" in r.json()["homebrew_notifications"][0]["message"]
    finally:
        app.dependency_overrides[get_current_lang] = lambda: "it"
