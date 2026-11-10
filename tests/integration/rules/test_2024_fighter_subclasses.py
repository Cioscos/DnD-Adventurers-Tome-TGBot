"""Guerriero 2024 (Task 35, parte B): Maestro di Battaglia, Campione, Cavaliere Mistico e Guerriero Psionico.
Valori dalla scheda ``docs/superpowers/rules/2024/classes/fighter.md``."""
from __future__ import annotations

import pytest

from core.db.models import Character
from core.rules.catalog import features_for
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user
from tests.integration.rules.test_2014_bard import _ability, _full, _keys_of, _roll_keys, _use
from tests.integration.rules.test_2014_fighter import _attack as _swing
from tests.integration.rules.test_2014_fighter import (
    _champion_in_session, _hurt, _new_turn, _player_hp, _start, _turn,
)
from tests.integration.rules.test_2014_fighter_battle_master import (
    _damage, _dice_left, _fixed, _hit, _key, _pending, _sword,
)
from tests.integration.rules.test_2014_fighter_eldritch_knight import KNOWN, SLOTS, _cast, _spell
from tests.integration.rules.test_2024_fighter import _fighter24

SUBS = {"battle_master": "Maestro di Battaglia", "champion": "Campione", "eldritch_knight": "Cavaliere Mistico",
        "psi_warrior": "Guerriero Psionico"}
SD, PSI, AS = "fighter.superiority_dice", "fighter.psionic_power", "fighter.action_surge"
ALL = ["ambush", "bait_and_switch", "commanders_strike", "commanding_presence", "disarming", "distracting",
       "evasive_footwork", "feinting", "goading", "lunging", "maneuvering", "menacing", "parry", "precision", "pushing",
       "rally", "riposte", "sweeping", "tactical_assessment", "trip"]
RIDERS = ["goading", "maneuvering", "pushing", "disarming", "menacing", "trip", "distracting", "sweeping"]


async def _sub(client, sub, level=7, **scores) -> int:
    body = {"name": "Guerriero", "initial_class": {"class_name": "fighter", "level": level, "subclass": SUBS[sub]}}
    r = await client.post("/characters", json=body)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    for ability, value in scores.items():
        assert (await client.patch(f"/characters/{cid}/ability_scores/{ability}", json={"value": value})).status_code == 200
    return cid


async def _bm(client, level=7, *picks, **scores) -> int:
    cid = await _sub(client, "battle_master", level, **scores)
    choice = _pending(await _full(client, cid))
    chosen = list(picks) + [m for m in ALL if m not in picks and m not in ("riposte", "parry")]
    r = await client.post(f"/characters/{cid}/choices/{choice['id']}/resolve",
                          json={"kind": "class_option", "options": chosen[:choice["count"]]})
    assert r.status_code == 200, r.text
    return cid


def _k(name: str) -> str:
    return f"fighter.{name}"


# ---------------------------------------------------------------------------
# Catalogo e livelli
# ---------------------------------------------------------------------------

ROWS = {
    "battle_master": {3: {"superiority_dice", "student_of_war"}, 7: {"know_your_enemy"},
                      10: {"improved_combat_superiority"}, 15: {"relentless"}, 18: {"ultimate_combat_superiority"}},
    "champion": {3: {"improved_critical", "remarkable_athlete"}, 10: {"heroic_warrior"},
                 15: {"superior_critical"}, 18: {"survivor", "defy_death", "heroic_rally"}},
    "eldritch_knight": {3: {"weapon_bond"}, 7: {"war_magic"}, 10: {"eldritch_strike"}, 15: {"arcane_charge"},
                        18: {"improved_war_magic"}},
    "psi_warrior": {3: {"psionic_power", "protective_field", "psionic_strike", "telekinetic_movement"},
                    7: {"telekinetic_adept", "psi_powered_leap", "telekinetic_thrust"}, 10: {"guarded_mind"},
                    15: {"bulwark_of_force"}, 18: {"telekinetic_master"}},
}


@pytest.mark.parametrize("sub", list(SUBS))
async def test_each_subclass_brings_its_rows_at_its_level_and_only_to_its_own(client, sub):
    for level, present in ROWS[sub].items():
        keys = await _keys_of(client, await _sub(client, sub, level))
        assert {_k(k) for k in present} <= keys
        low = await _keys_of(client, await _sub(client, sub, level - 1 if level > 3 else 3))
        if level > 3:
            assert not {_k(k) for k in present} & low
    others = {_k(k) for s, rows in ROWS.items() if s != sub for ks in rows.values() for k in ks}
    assert not others & await _keys_of(client, await _sub(client, sub, 20))


def test_every_subclass_row_names_its_subclass_with_a_known_key():
    specs = [s for s in features_for("2024", "fighter") if s.subclass]
    assert {s.subclass for s in specs} == set(SUBS) and len(specs) == 50


# ---------------------------------------------------------------------------
# Maestro di Battaglia
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,dice", [(3, 4), (6, 4), (7, 5), (14, 5), (15, 6), (20, 6)])
async def test_superiority_dice_follow_the_level(client, level, dice):
    row = await _ability(client, await _bm(client, level), SD)
    assert (row["max_uses"], row["restoration_type"], row["is_pool"]) == (dice, "short_rest", True)


@pytest.mark.parametrize("level,count", [(3, 3), (7, 5), (10, 7), (15, 9)])
async def test_maneuvers_known_follow_the_level_and_the_twenty_are_the_options(client, level, count):
    choice = _pending(await _full(client, await _sub(client, "battle_master", level)))
    assert choice["count"] == count and {o["key"] for o in choice["options"]} == set(ALL)
    assert all(o["name"]["it"] and o["name"]["en"] and 0 < len(o["summary"]["it"]) <= 200 for o in choice["options"])


@pytest.mark.parametrize("maneuver", RIDERS)
async def test_a_rider_maneuver_adds_the_die_to_the_damage_and_spends_one(client, maneuver, monkeypatch):
    cid = await _bm(client, 7, maneuver)
    wid = await _sword(client, cid)
    _fixed(monkeypatch, 5)
    hit = await _hit(client, cid, wid)
    plain = hit["damage_total"]
    body = (await _damage(client, cid, hit, _key(maneuver))).json()
    block = body["option_result"]
    if maneuver == "sweeping":
        assert block["separate_rolls"] == [5] and body["damage_total"] == plain
    else:
        assert block["extra_rolls"] == [5] and body["damage_total"] == plain + 5
    assert block["effects"] and await _dice_left(client, cid) == 4


async def test_the_die_is_a_d10_at_level_10_and_a_d12_at_level_18(client, monkeypatch):
    for level, sides in ((7, 8), (10, 10), (18, 12)):
        cid = await _bm(client, level, "trip")
        wid = await _sword(client, cid)
        _fixed(monkeypatch, 99)
        body = (await _damage(client, cid, await _hit(client, cid, wid), _key("trip"))).json()
        assert body["option_result"]["extra_rolls"] == [sides]


async def test_lunging_attack_is_a_bonus_action_dash_that_adds_the_die_to_the_next_melee_hit(client, monkeypatch):
    cid = await _bm(client, 7, "lunging")
    wid = await _sword(client, cid)
    bow = await _sword(client, cid, weapon_type="ranged", properties=["ammunition"])
    strike = _key("lunging_strike")
    assert strike not in await _roll_keys(client, cid, "attack", item_id=wid)
    r = await _use(client, cid, _key("lunging"))
    assert r.status_code == 200, r.text
    assert "Scatto" in r.json()["message"]["it"] and (await _turn(client, cid))["bonus_used"] is True
    assert await _dice_left(client, cid) == 4
    assert strike in await _roll_keys(client, cid, "attack", item_id=wid)
    assert strike not in await _roll_keys(client, cid, "attack", item_id=bow)  # solo in mischia
    _fixed(monkeypatch, 5)
    plain = (await _swing(client, cid, wid, confirm_extra_attack=True)).json()["damage_total"]
    body = (await _swing(client, cid, wid, confirm_extra_attack=True, options=[strike])).json()
    assert body["damage_total"] == plain + 5 and await _dice_left(client, cid) == 4
    assert strike not in await _roll_keys(client, cid, "attack", item_id=wid)  # una volta sola


async def test_evasive_footwork_is_a_bonus_action_disengage_with_the_die_as_ac_until_the_next_turn(client, monkeypatch):
    cid = await _bm(client, 7, "evasive_footwork")
    _fixed(monkeypatch, 5)
    r = await _use(client, cid, _key("evasive_footwork"))
    assert r.status_code == 200, r.text
    assert r.json()["rolls"] == [5] and "Disimpegno" in r.json()["message"]["it"]
    assert (await _turn(client, cid))["bonus_used"] is True and await _dice_left(client, cid) == 4
    state = next(s for s in (await _full(client, cid))["active_states"] if s["key"] == "evasive_footwork")
    assert state["data"]["ac"] == 5
    await client.post(f"/characters/{cid}/turn/new")
    assert not [s for s in (await _full(client, cid))["active_states"] if s["key"] == "evasive_footwork"]


@pytest.mark.parametrize("params,who", [({"self": True}, "self"), ({}, "other")])
async def test_bait_and_switch_costs_no_action_and_gives_the_die_as_ac_to_you_or_the_other(client, monkeypatch, params, who):
    cid = await _bm(client, 7, "bait_and_switch")
    _fixed(monkeypatch, 4)
    r = await _use(client, cid, _key("bait_and_switch"), params=params)
    assert r.status_code == 200, r.text
    turn = await _turn(client, cid)
    assert not (turn["bonus_used"] or turn["action_used"] or turn["reaction_used"]) and await _dice_left(client, cid) == 4
    data = next(s for s in (await _full(client, cid))["active_states"] if s["key"] == "bait_and_switch")["data"]
    assert (data.get("self") is True) == (who == "self") and data["ac"] == 4
    assert (data.get("others") == [_key("bait_and_switch")]) == (who == "other")


async def test_parry_uses_the_better_of_strength_and_dexterity(client, monkeypatch):
    cid = await _bm(client, 7, "parry", strength=18, dexterity=10)
    hp = (await _full(client, cid))["current_hit_points"]
    _fixed(monkeypatch, 5)
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 12, "damage_type": "slashing",
                                                           "options": [_key("parry")]})
    assert r.status_code == 200, r.text
    assert (await _full(client, cid))["current_hit_points"] == hp - (12 - 5 - 4)
    assert (await _turn(client, cid))["reaction_used"] is True and await _dice_left(client, cid) == 4


async def test_rally_gives_the_die_plus_half_the_fighter_level_as_temporary_hit_points(client, monkeypatch):
    cid = await _bm(client, 7, "rally", charisma=18)
    _fixed(monkeypatch, 5)
    r = await _use(client, cid, _key("rally"))
    assert r.status_code == 200, r.text
    assert r.json()["given"] == 5 + 3 and (await _turn(client, cid))["bonus_used"] is True


async def test_commanders_strike_replaces_an_attack_and_costs_no_bonus_action(client, monkeypatch):
    cid = await _bm(client, 7, "commanders_strike")
    _fixed(monkeypatch, 6)
    r = await _use(client, cid, _key("commanders_strike"))
    assert r.status_code == 200 and r.json()["given"] == 6, r.text
    turn = await _turn(client, cid)
    assert turn["bonus_used"] is False and turn["action_attacks"] == 1 and await _dice_left(client, cid) == 4


@pytest.mark.parametrize("name,roll,query,yes,no", [
    ("ambush", "initiative", {}, True, None), ("ambush", "skill", {"skill": "stealth"}, True, {"skill": "athletics"}),
    ("commanding_presence", "skill", {"skill": "persuasion"}, True, {"skill": "stealth"}),
    ("commanding_presence", "skill", {"skill": "intimidation"}, True, None),
    ("tactical_assessment", "skill", {"skill": "insight"}, True, {"skill": "persuasion"}),
    ("tactical_assessment", "skill", {"skill": "history"}, True, None),
])
async def test_check_maneuvers_are_offered_on_their_own_rolls_only(client, name, roll, query, yes, no):
    cid = await _bm(client, 7, name)
    assert _key(name) in await _roll_keys(client, cid, roll, **query)
    if no:
        assert _key(name) not in await _roll_keys(client, cid, roll, **no)
    assert _key(name) not in await _roll_keys(client, cid, "attack")


async def test_ambush_adds_the_die_to_the_initiative_and_is_refused_when_incapacitated(client, monkeypatch):
    cid = await _bm(client, 7, "ambush")
    _fixed(monkeypatch, 4)
    r = await client.post(f"/characters/{cid}/skills/stealth/roll", json={"die": 10, "options": [_key("ambush")]})
    assert r.status_code == 200, r.text
    assert r.json()["option_result"]["extra_rolls"] == [4] and await _dice_left(client, cid) == 4
    await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"incapacitated": True}})
    assert _key("ambush") not in await _roll_keys(client, cid, "initiative")


async def test_know_your_enemy_is_a_bonus_action_once_and_a_die_restores_the_use(client):
    cid = await _bm(client, 7)
    kye = _k("know_your_enemy")
    r = await _use(client, cid, kye)
    assert r.status_code == 200 and (await _turn(client, cid))["bonus_used"] is True and r.json()["message"], r.text
    await client.post(f"/characters/{cid}/turn/new")
    refused = await _use(client, cid, kye)
    assert refused.status_code == 409 and refused.json()["detail"]["code"] == "no_uses"
    assert (await _use(client, cid, kye, params={"restore": True})).status_code == 200
    assert await _dice_left(client, cid) == 4


async def test_relentless_makes_the_next_maneuver_a_free_d8_once_per_turn(client, monkeypatch):
    cid = await _bm(client, 15, "trip", "menacing")
    wid = await _sword(client, cid)
    _fixed(monkeypatch, 99)
    assert (await _use(client, cid, _k("relentless"))).status_code == 200
    assert (await _use(client, cid, _k("relentless"))).json()["detail"]["code"] == "once_per_turn"
    body = (await _damage(client, cid, await _hit(client, cid, wid), _key("trip"))).json()
    assert set(body["option_result"]["extra_rolls"]) == {8} and await _dice_left(client, cid) == 6  # d8, nessun dado speso
    body = (await _damage(client, cid, await _hit(client, cid, wid), _key("menacing"))).json()
    assert body["option_result"]["extra_rolls"] == [10] and await _dice_left(client, cid) == 5  # tornato il dado normale


async def test_student_of_war_adds_a_fighter_skill(client):
    cid = await _sub(client, "battle_master", 3)
    choice = next(c for c in (await _full(client, cid))["pending_choices"] if c.get("group") == "student_of_war")
    assert choice["count"] == 1 and {o["key"] for o in choice["options"]} == {
        "acrobatics", "animal_handling", "athletics", "history", "insight", "intimidation", "perception", "persuasion", "survival"}
    r = await client.post(f"/characters/{cid}/choices/{choice['id']}/resolve", json={"kind": "class_option", "options": ["history"]})
    assert r.status_code == 200, r.text
    assert (await _full(client, cid))["skills"]["history"] in ("proficient", True)


# ---------------------------------------------------------------------------
# Campione
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,die,critical", [(3, 18, False), (3, 19, True), (14, 18, False), (15, 18, True), (15, 17, False)])
async def test_the_champion_crits_on_19_and_from_level_15_on_18(client, level, die, critical):
    cid = await _sub(client, "champion", level)
    wid = await _sword(client, cid)
    body = (await _swing(client, cid, wid, die=die, confirm_extra_attack=True)).json()
    assert body["is_critical"] is critical


async def test_remarkable_athlete_gives_advantage_on_initiative_and_athletics_only(client):
    cid = await _sub(client, "champion", 3)
    athletics = (await client.post(f"/characters/{cid}/skills/athletics/roll", json={"dice": [5, 12]})).json()
    stealth = (await client.post(f"/characters/{cid}/skills/stealth/roll", json={"die": 5})).json()
    assert athletics["mode_applied"] == "advantage" and stealth["mode_applied"] == "normal"
    other = await _sub(client, "battle_master", 3)
    assert (await client.post(f"/characters/{other}/skills/athletics/roll", json={"die": 5})).json()["mode_applied"] == "normal"


async def test_remarkable_athlete_offers_the_free_move_after_a_critical_hit_only(client):
    cid = await _sub(client, "champion", 3)
    wid = await _sword(client, cid)
    move = _k("remarkable_athlete_move")
    normal = await _hit(client, cid, wid)
    assert move not in await _roll_keys(client, cid, "attack", item_id=wid) or (await _damage(client, cid, normal, move)).status_code == 409
    crit = await _hit(client, cid, wid, die=20)
    body = (await _damage(client, cid, crit, move)).json()
    assert "metà" in body["option_result"]["effects"][0]["it"] and body["option_result"]["effects"][0]["en"]


async def test_the_champion_chooses_a_second_style_at_level_7(client):
    cid = await _sub(client, "champion", 7)
    choice = next(c for c in (await _full(client, cid))["pending_choices"] if c.get("group") == "fighting_style")
    assert choice["count"] == 2 and len(choice["options"]) == 10


async def test_heroic_warrior_gives_inspiration_at_the_start_of_each_combat_turn_only(client, test_session_factory):
    sid, cid = await _champion_in_session(client, test_session_factory, 10)
    as_user(PLAYER_ID)
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    as_user(GM_ID)
    await _start(client, sid)
    as_user(PLAYER_ID)
    assert (await _full(client, cid))["heroic_inspiration"] is True
    async with test_session_factory() as session:  # la scheda non permette di toglierla da API: la spende un altro privilegio
        (await session.get(Character, cid)).heroic_inspiration = False
        await session.commit()
    as_user(GM_ID)
    assert (await client.post(f"/sessions/{sid}/encounter/next-turn")).status_code == 200  # il goblin
    assert (await client.post(f"/sessions/{sid}/encounter/next-turn")).status_code == 200  # di nuovo il PG
    as_user(PLAYER_ID)
    assert (await _full(client, cid))["heroic_inspiration"] is True
    notice = (await _turn(client, cid)).get("start_heal") or []
    assert notice and notice[0]["feature_key"] == _k("heroic_warrior") and notice[0]["message"]["it"]
    as_user(GM_ID)
    assert (await client.post(f"/sessions/{sid}/encounter/prev-turn")).status_code == 200  # l'annullamento la toglie
    as_user(PLAYER_ID)
    assert (await _full(client, cid))["heroic_inspiration"] is False


async def test_heroic_warrior_does_nothing_with_the_new_turn_button_outside_combat(client):
    cid = await _sub(client, "champion", 10)
    await _new_turn(client, cid)
    assert (await _full(client, cid))["heroic_inspiration"] is False


async def test_heroic_rally_heals_five_plus_constitution_when_bloodied_and_never_at_zero(client, test_session_factory):
    cid = await _sub(client, "champion", 18, constitution=14)
    maximum = (await _full(client, cid))["hit_points"]
    await _hurt(test_session_factory, cid, maximum // 2)
    await _new_turn(client, cid)
    assert (await _full(client, cid))["current_hit_points"] == maximum // 2 + 5 + 2
    await _hurt(test_session_factory, cid, 0)
    await _new_turn(client, cid)
    assert (await _full(client, cid))["current_hit_points"] == 0


async def test_defy_death_gives_advantage_and_treats_18_to_20_as_a_20(client):
    cid = await _sub(client, "champion", 18)
    r = await client.post(f"/characters/{cid}/death_saves/roll", json={"dice": [2, 18]})
    assert r.status_code == 200, r.text
    assert r.json()["mode_applied"] == "advantage" and r.json()["revived"] is True and r.json()["current_hp"] == 1
    low = await _sub(client, "champion", 17)
    r = await client.post(f"/characters/{low}/death_saves/roll", json={"die": 18})
    assert r.json()["mode_applied"] == "normal" and r.json()["revived"] is False


# ---------------------------------------------------------------------------
# Cavaliere Mistico
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level", [3, 7, 10, 13, 19])
async def test_eldritch_knight_slots_cantrips_and_prepared_spells_follow_the_2024_table(client, level):
    full = await _full(client, await _sub(client, "eldritch_knight", level))
    totals = tuple(s["total"] for s in sorted(full["spell_slots"], key=lambda s: s["level"]) if s["total"])
    limits = full["spellcasting"]["limits"][0]
    assert totals == SLOTS[level]
    assert (limits["cantrips_limit"], limits["prepared_limit"]) == (3 if level >= 10 else 2, KNOWN[level])
    assert full["spellcasting"]["casters"][0]["ability"] == "intelligence"


async def test_war_magic_lets_a_cantrip_replace_one_attack(client):
    cid = await _sub(client, "eldritch_knight", 7)
    cantrip, leveled = await _spell(client, cid, "Raggio di fuoco", 0), await _spell(client, cid, "Dardo", 1)
    key = _k("war_magic")
    assert key in await _roll_keys(client, cid, "cast", spell_id=cantrip) and key not in await _roll_keys(client, cid, "cast", spell_id=leveled)
    assert (await _cast(client, cid, cantrip, options=[key])).status_code == 200
    turn = await _turn(client, cid)
    assert turn["action_attacks"] == 1 and turn["bonus_used"] is False
    wid = await _sword(client, cid)
    assert (await _swing(client, cid, wid)).status_code == 200  # il secondo attacco dell'azione
    assert (await _swing(client, cid, wid)).json()["detail"]["code"] == "attack_limit"


async def test_improved_war_magic_lets_a_level_1_or_2_spell_replace_two_attacks(client):
    cid = await _sub(client, "eldritch_knight", 18)
    spell, big = await _spell(client, cid, "Dardo", 1), await _spell(client, cid, "Palla", 3)
    key = _k("improved_war_magic")
    assert key in await _roll_keys(client, cid, "cast", spell_id=spell) and key not in await _roll_keys(client, cid, "cast", spell_id=big)
    assert (await _cast(client, cid, spell, slot_level=1, options=[key])).status_code == 200
    assert (await _turn(client, cid))["action_attacks"] == 2


async def test_arcane_charge_is_a_choice_of_action_surge_for_the_knight_from_level_15(client):
    cid = await _sub(client, "eldritch_knight", 15)
    row = await _ability(client, cid, AS)
    assert [t["key"] for t in row["use_toggles"]] == ["arcane_charge"]
    r = await _use(client, cid, AS, params={"arcane_charge": True})
    assert r.status_code == 200 and r.json()["notes"] == ["arcane_charge"]
    assert not (await _ability(client, await _sub(client, "champion", 15), AS))["use_toggles"]


async def test_eldritch_strike_and_the_weapon_bond_come_from_the_2014_knight(client):
    cid = await _sub(client, "eldritch_knight", 10)
    sword = await _sword(client, cid)
    assert _k("eldritch_strike") in await _roll_keys(client, cid, "attack", item_id=sword)
    assert (await _use(client, cid, _k("weapon_bond"))).json()["detail"]["code"] == "needs_panel"


# ---------------------------------------------------------------------------
# Guerriero Psionico
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,dice,sides", [(3, 4, 6), (5, 6, 8), (9, 8, 8), (11, 8, 10), (13, 10, 10), (17, 12, 12)])
async def test_psionic_energy_dice_follow_the_table(client, level, dice, sides, monkeypatch):
    cid = await _sub(client, "psi_warrior", level, intelligence=14)
    row = await _ability(client, cid, PSI)
    assert (row["max_uses"], row["is_pool"]) == (dice, True)
    _fixed(monkeypatch, 99)
    assert (await _use(client, cid, _k("protective_field"))).json()["rolls"] == [sides]


async def test_a_short_rest_gives_back_one_die_and_a_long_rest_all(client):
    cid = await _sub(client, "psi_warrior", 5)
    row = await _ability(client, cid, PSI)
    await client.patch(f"/characters/{cid}/abilities/{row['id']}", json={"uses": 1})
    await client.post(f"/characters/{cid}/rest", json={"rest_type": "short", "confirm_early": True})
    assert (await _ability(client, cid, PSI))["uses"] == 2
    await client.post(f"/characters/{cid}/rest", json={"rest_type": "long", "confirm_early": True})
    assert (await _ability(client, cid, PSI))["uses"] == 6


async def test_protective_field_reduces_damage_to_you_or_shows_the_value_for_another(client, monkeypatch):
    cid = await _sub(client, "psi_warrior", 5, intelligence=16)
    hp = (await _full(client, cid))["current_hit_points"]
    _fixed(monkeypatch, 5)
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 12, "damage_type": "slashing",
                                                           "options": [_k("protective_field")]})
    assert r.status_code == 200, r.text
    assert (await _full(client, cid))["current_hit_points"] == hp - (12 - 5 - 3)
    assert (await _turn(client, cid))["reaction_used"] is True and (await _ability(client, cid, PSI))["uses"] == 5
    await client.post(f"/characters/{cid}/turn/new")
    other = await _use(client, cid, _k("protective_field"))  # un'altra creatura
    assert other.json()["given"] == 5 + 3 and (await _ability(client, cid, PSI))["uses"] == 4


async def test_psionic_strike_adds_force_damage_once_per_turn_for_a_die(client, monkeypatch):
    cid = await _sub(client, "psi_warrior", 5, intelligence=16)
    wid = await _sword(client, cid)
    key = _k("psionic_strike")
    _fixed(monkeypatch, 4)
    hit = await _hit(client, cid, wid)
    plain = hit["damage_total"]
    body = (await _damage(client, cid, hit, key)).json()
    assert body["damage_total"] == plain + 4 + 3 and "Forza" in body["option_result"]["effects"][0]["it"]
    assert (await _ability(client, cid, PSI))["uses"] == 5
    assert key not in await _roll_keys(client, cid, "attack", item_id=wid) or (
        await _damage(client, cid, await _hit(client, cid, wid), key)).status_code == 409


async def test_telekinetic_thrust_rides_on_the_strike_with_a_dc_and_a_prone_effect(client):
    cid = await _sub(client, "psi_warrior", 7, intelligence=16)
    wid = await _sword(client, cid)
    thrust = _k("telekinetic_thrust")
    hit = await _hit(client, cid, wid)
    assert (await _damage(client, cid, hit, thrust)).status_code == 409  # senza il Colpo Psionico
    body = (await _damage(client, cid, await _hit(client, cid, wid), _k("psionic_strike"), thrust)).json()
    assert f"CD {8 + 3 + 3}" in body["option_result"]["effects"][-1]["it"]
    effect = (await client.get(f"/characters/{cid}/target-effects/{thrust}")).json()["result"]
    assert (effect["condition"], effect["save_ability"], effect["save_dc"]) == ("prone", "strength", 14)


@pytest.mark.parametrize("name,level,slot", [("telekinetic_movement", 3, "action"), ("psi_powered_leap", 7, "bonus"),
                                             ("bulwark_of_force", 15, "bonus")])
async def test_psionic_powers_with_a_free_use_can_be_restored_by_a_die(client, name, level, slot):
    cid = await _sub(client, "psi_warrior", level, intelligence=16)
    key = _k(name)
    r = await _use(client, cid, key)
    assert r.status_code == 200, r.text
    assert (await _turn(client, cid))[f"{slot}_used"] is True and (await _ability(client, cid, PSI))["uses"] == (await _ability(client, cid, PSI))["max_uses"]
    await client.post(f"/characters/{cid}/turn/new")
    refused = await _use(client, cid, key)
    assert refused.status_code == 409 and refused.json()["detail"]["code"] == "no_uses"
    again = await _use(client, cid, key, params={"restore": True})
    assert again.status_code == 200, again.text
    row = await _ability(client, cid, PSI)
    assert row["uses"] == row["max_uses"] - 1


async def test_the_leap_doubles_the_speed_as_a_fly_speed_until_the_end_of_the_turn(client):
    cid = await _sub(client, "psi_warrior", 7)
    speed = (await _full(client, cid))["computed"]["speed"]
    assert (await _use(client, cid, _k("psi_powered_leap"))).status_code == 200
    assert (await _full(client, cid))["computed"]["fly_speed"] == speed * 2
    await client.post(f"/characters/{cid}/turn/new")
    assert not (await _full(client, cid))["computed"]["fly_speed"]


async def test_bulwark_of_force_is_a_one_minute_state_shown_to_the_group(client):
    cid = await _sub(client, "psi_warrior", 15, intelligence=16)
    assert (await _use(client, cid, _k("bulwark_of_force"))).status_code == 200
    state = next(s for s in (await _full(client, cid))["active_states"] if s["key"] == "bulwark_of_force")
    assert state["rounds_left"] == 10 and state["data"]["others"] == [_k("bulwark_of_force")]


async def test_guarded_mind_gives_psychic_resistance_and_ends_charm_and_fear_for_a_die(client):
    cid = await _sub(client, "psi_warrior", 10)
    assert "psychic" in (await _full(client, cid))["computed"]["resistances"]
    assert (await _use(client, cid, _k("guarded_mind"))).json()["detail"]["code"] == "feature_unavailable"
    await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"charmed": True, "frightened": True}})
    assert (await _use(client, cid, _k("guarded_mind"))).status_code == 200
    conditions = (await _full(client, cid))["conditions"]
    assert not conditions.get("charmed") and not conditions.get("frightened")
    assert (await _ability(client, cid, PSI))["uses"] == (await _ability(client, cid, PSI))["max_uses"] - 1
    assert (await _turn(client, cid))["action_used"] is False


async def test_telekinetic_master_casts_telekinesis_free_once_and_a_die_restores_the_cast(client):
    cid = await _sub(client, "psi_warrior", 18, intelligence=16)
    spell = next(s for s in (await _full(client, cid))["spells"] if s["name"] == "Telecinesi")
    assert spell["is_prepared"] is True
    row = await _ability(client, cid, _k("telekinetic_master"))
    assert (row["uses"], row["max_uses"]) == (1, 1)
    assert (await _cast(client, cid, spell["id"], free_cast=True)).status_code == 200
    assert (await _ability(client, cid, _k("telekinetic_master")))["uses"] == 0
    assert (await _use(client, cid, _k("telekinetic_master"))).status_code == 200  # il dado ripristina il lancio
    assert (await _ability(client, cid, _k("telekinetic_master")))["uses"] == 1
    assert (await _ability(client, cid, PSI))["uses"] == (await _ability(client, cid, PSI))["max_uses"] - 1


async def test_telekinetic_master_gives_a_bonus_action_attack_while_concentrating_on_telekinesis(client):
    cid = await _sub(client, "psi_warrior", 18, intelligence=16)
    wid = await _sword(client, cid)
    key = _k("telekinetic_master_attack")
    assert key not in await _roll_keys(client, cid, "attack", item_id=wid)
    spell = next(s for s in (await _full(client, cid))["spells"] if s["name"] == "Telecinesi")
    assert (await _cast(client, cid, spell["id"], free_cast=True)).status_code == 200
    assert key in await _roll_keys(client, cid, "attack", item_id=wid)
    assert (await _swing(client, cid, wid, options=[key])).status_code == 200
    assert (await _turn(client, cid))["bonus_used"] is True


async def test_psionic_strike_die_does_not_double_on_a_critical(client, monkeypatch):
    cid = await _sub(client, "psi_warrior", 5, intelligence=16)
    wid = await _sword(client, cid)
    _fixed(monkeypatch, 4)
    hit = await _hit(client, cid, wid, die=20)
    plain = hit["damage_total"]
    body = (await _damage(client, cid, hit, _k("psionic_strike"))).json()
    assert body["damage_total"] == plain + 4 + 3  # un solo dado: il critico raddoppia l'arma, non il Colpo Psionico
    assert body["option_result"]["extra_rolls"] == [4]


async def test_minori_9_relentless_gives_the_d8_to_the_feint_and_lunging_strikes_and_lunging_rolls_nothing(client, monkeypatch):
    cid = await _bm(client, 15, "feinting", "lunging")
    wid = await _sword(client, cid)
    _fixed(monkeypatch, 99)
    plain = (await _swing(client, cid, wid, confirm_extra_attack=True)).json()["damage_total"]
    assert (await _use(client, cid, _k("relentless"))).status_code == 200
    r = await _use(client, cid, _key("feinting"))
    assert r.status_code == 200 and await _dice_left(client, cid) == 6  # Implacabile: nessun dado speso
    body = (await _swing(client, cid, wid, confirm_extra_attack=True, options=[_key("feinting_strike")])).json()
    assert set(body["option_result"]["extra_rolls"]) == {8}  # d8 di Implacabile, non il d10 del livello
    await client.post(f"/characters/{cid}/turn/new")
    assert (await _use(client, cid, _k("relentless"))).status_code == 200
    r = await _use(client, cid, _key("lunging"))
    assert r.status_code == 200 and r.json()["rolls"] == [] and await _dice_left(client, cid) == 6  # niente dado inutile all'Usa
    body = (await _swing(client, cid, wid, confirm_extra_attack=True, options=[_key("lunging_strike")])).json()
    assert set(body["option_result"]["extra_rolls"]) == {8}


async def test_minori_10_bulwark_half_cover_raises_the_users_ac_by_2(client):
    cid = await _sub(client, "psi_warrior", 15, intelligence=16)
    before = (await _full(client, cid))["ac"]
    assert (await _use(client, cid, _k("bulwark_of_force"))).status_code == 200
    assert (await _full(client, cid))["ac"] == before + 2


async def test_minori_10_bulwark_half_cover_adds_2_to_dexterity_saves_only(client):
    cid = await _sub(client, "psi_warrior", 15, intelligence=16)
    async def save(ability):
        return (await client.post(f"/characters/{cid}/saving_throws/{ability}/roll", json={})).json()["bonus"]
    dex, con = await save("dexterity"), await save("constitution")
    assert (await _use(client, cid, _k("bulwark_of_force"))).status_code == 200
    assert await save("dexterity") == dex + 2 and await save("constitution") == con


async def test_minori_10_telekinesis_of_the_master_shows_the_intelligence_dc(client):
    cid = await _sub(client, "psi_warrior", 18, intelligence=16)
    full = await _full(client, cid)
    spell = next(s for s in full["spells"] if s["name"] == "Telecinesi")
    assert spell["save_dc"] == 8 + full["proficiency_bonus"] + 3
