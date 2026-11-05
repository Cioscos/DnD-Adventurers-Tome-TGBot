"""Guerriero 2014 (Task 23): Maestro di Battaglia, dadi di superiorità, manovre scelte e conferme al tiro."""
from __future__ import annotations

import pytest

from core.rules.catalog.y2014.fighter import MANEUVERS, _die_sides
from tests.integration.rules.test_2014_bard import _ability, _full, _keys_of, _roll_keys, _use
from tests.integration.rules.test_2014_fighter import _attack, _fighter, _rest, _turn

SD = "fighter.superiority_dice"
ALL = [k for k, _it, _en in MANEUVERS]
RIDERS = ["goading", "maneuvering", "pushing", "disarming", "menacing", "trip", "distracting", "sweeping"]


def _key(maneuver: str) -> str:
    return f"fighter.maneuver_{maneuver}"


def _pending(full: dict) -> dict | None:
    return next((c for c in full["pending_choices"] if c.get("group") == "maneuvers"), None)


async def _master(client, level=7, *picks: str, **scores) -> int:
    """Un Maestro di Battaglia con le manovre indicate; il resto delle scelte è riempito con altre qualsiasi."""
    cid = await _fighter(client, level, "battle_master", **scores)
    choice = _pending(await _full(client, cid))
    if choice and picks is not None:
        chosen = list(picks) + [m for m in ALL if m not in picks and m not in ("riposte", "parry")]
        r = await client.post(f"/characters/{cid}/choices/{choice['id']}/resolve",
                              json={"kind": "class_option", "options": chosen[:choice["count"]]})
        assert r.status_code == 200, r.text
    return cid


async def _dice_left(client, cid) -> int:
    return (await _ability(client, cid, SD))["uses"]


async def _sword(client, cid, **meta) -> int:
    meta = {"damage_dice": "1d8", "weapon_type": "melee", "properties": [], "damage_type": "slashing", **meta}
    r = await client.post(f"/characters/{cid}/items", json={"name": "Spada", "item_type": "weapon", "item_metadata": meta})
    assert r.status_code == 201, r.text
    return max(i["id"] for i in r.json()["items"])


def _fixed(monkeypatch, value: int) -> None:
    monkeypatch.setattr("random.randint", lambda a, b: min(value, b))


async def _hit(client, cid, wid, die=15, **body) -> dict:
    r = await client.post(f"/characters/{cid}/items/{wid}/attack",
                          json={"die": die, "defer_damage": True, "confirm_extra_attack": True, **body})
    assert r.status_code == 200, r.text
    return r.json()


async def _damage(client, cid, hit, *options, **body):
    return await client.post(f"/characters/{cid}/attack/{hit['attack_id']}/damage", json={"options": list(options), **body})


# ---------------------------------------------------------------------------
# Dadi, manovre scelte e CD
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,dice", [(3, 4), (6, 4), (7, 5), (14, 5), (15, 6), (20, 6)])
async def test_superiority_dice_follow_the_level_and_come_back_with_any_rest(client, level, dice):
    cid = await _master(client, level)
    row = await _ability(client, cid, SD)
    assert (row["max_uses"], row["uses"], row["restoration_type"], row["is_pool"], row["has_on_use"]) == (
        dice, dice, "short_rest", True, False)


@pytest.mark.parametrize("rest", ["short", "long"])
async def test_superiority_dice_return_with_a_short_or_a_long_rest(client, rest):
    cid = await _master(client, 3)
    row = await _ability(client, cid, SD)
    await client.patch(f"/characters/{cid}/abilities/{row['id']}", json={"uses": 0})
    await _rest(client, cid, rest)
    assert await _dice_left(client, cid) == 4


@pytest.mark.parametrize("level,sides", [(3, 8), (9, 8), (10, 10), (17, 10), (18, 12), (20, 12)])
def test_the_die_grows_at_10_and_18(level, sides):
    assert _die_sides(level) == sides


@pytest.mark.parametrize("level,count", [(3, 3), (6, 3), (7, 5), (9, 5), (10, 7), (14, 7), (15, 9), (20, 9)])
async def test_maneuvers_known_follow_the_level(client, level, count):
    cid = await _fighter(client, level, "battle_master")
    assert _pending(await _full(client, cid))["count"] == count


async def test_the_sixteen_maneuvers_are_the_options_and_each_has_a_name_and_a_summary(client):
    choice = _pending(await _full(client, await _fighter(client, 3, "battle_master")))
    assert {o["key"] for o in choice["options"]} == set(ALL) and len(ALL) == 16
    assert all(o["name"]["it"] and o["name"]["en"] and 0 < len(o["summary"]["it"]) <= 200 for o in choice["options"])


async def test_each_chosen_maneuver_becomes_a_row_and_the_others_do_not(client):
    cid = await _master(client, 3, "trip", "rally", "parry")
    keys = await _keys_of(client, cid)
    assert {_key("trip"), _key("rally"), _key("parry")} <= keys and _key("goading") not in keys


async def test_the_new_picks_at_level_7_add_to_the_old_ones_and_can_replace_one(client):
    cid = await _master(client, 3, "trip", "rally", "parry")
    klass = (await _full(client, cid))["classes"][0]
    await client.patch(f"/characters/{cid}/classes/{klass['id']}", json={"level": 7})
    choice = _pending(await _full(client, cid))
    assert choice["count"] == 2 and not {"trip", "rally", "parry"} & {o["key"] for o in choice["options"]}
    state = (await client.get(f"/characters/{cid}/classes/{klass['id']}/options/maneuvers")).json()
    assert state["replaceable"] is True and {o["key"] for o in state["chosen"]} == {"trip", "rally", "parry"}
    r = await client.post(f"/characters/{cid}/classes/{klass['id']}/options/replace",
                          json={"group": "maneuvers", "old_key": "trip", "new_key": "goading"})
    assert r.status_code == 200, r.text
    keys = await _keys_of(client, cid)
    assert _key("goading") in keys and _key("trip") not in keys


async def test_only_the_battle_master_has_maneuvers(client):
    for sub in (None, "champion", "eldritch_knight"):
        cid = await _fighter(client, 10, sub)
        assert _pending(await _full(client, cid)) is None
        assert not {k for k in await _keys_of(client, cid) if k.startswith("fighter.maneuver_")}


@pytest.mark.parametrize("strength,dexterity,dc", [(16, 10, 8 + 3 + 3), (10, 18, 8 + 3 + 4), (14, 14, 8 + 3 + 2)])
async def test_the_maneuver_dc_uses_the_better_of_strength_and_dexterity(client, strength, dexterity, dc):
    cid = await _master(client, 7, "trip", strength=strength, dexterity=dexterity)
    wid = await _sword(client, cid)
    hit = await _hit(client, cid, wid)
    body = (await _damage(client, cid, hit, _key("trip"))).json()
    assert f"CD {dc}" in body["option_result"]["effects"][0]["it"] and f"DC {dc}" in body["option_result"]["effects"][0]["en"]


# ---------------------------------------------------------------------------
# Manovre dopo un colpo
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("maneuver", RIDERS)
async def test_a_rider_maneuver_is_offered_spends_a_die_and_adds_it_to_the_damage(client, maneuver, monkeypatch):
    cid = await _master(client, 7, maneuver)
    wid = await _sword(client, cid)
    assert _key(maneuver) in await _roll_keys(client, cid, "attack", item_id=wid)
    _fixed(monkeypatch, 5)
    hit = await _hit(client, cid, wid)
    plain = hit["damage_total"]
    r = await _damage(client, cid, hit, _key(maneuver))
    assert r.status_code == 200, r.text
    body = r.json()
    block = body["option_result"]
    if maneuver == "sweeping":  # il dado va a un'altra creatura, non al bersaglio
        assert block["separate_rolls"] == [5] and body["damage_total"] == plain
    else:
        assert block["extra_rolls"] == [5] and body["damage_total"] == plain + 5
    assert block["effects"] and block["effects"][0]["it"] and block["effects"][0]["en"]
    assert await _dice_left(client, cid) == 4


@pytest.mark.parametrize("maneuver", RIDERS)
async def test_a_rider_maneuver_is_refused_before_the_hit_without_dice_and_on_a_miss(client, maneuver):
    cid = await _master(client, 7, maneuver)
    wid = await _sword(client, cid)
    row = await _ability(client, cid, SD)
    hit = await _hit(client, cid, wid)
    await client.patch(f"/characters/{cid}/abilities/{row['id']}", json={"uses": 0})
    r = await _damage(client, cid, hit, _key(maneuver))
    assert r.status_code == 409 and r.json()["detail"]["code"] == "option_unavailable"
    await client.patch(f"/characters/{cid}/abilities/{row['id']}", json={"uses": 5})
    miss = await _hit(client, cid, wid, die=1)
    assert miss.get("attack_id") is None or (await _damage(client, cid, miss, _key(maneuver))).status_code == 409
    assert await _dice_left(client, cid) == 5


async def test_a_rider_maneuver_is_not_offered_for_a_spell_or_without_the_choice(client):
    cid = await _master(client, 7, "trip")
    wid = await _sword(client, cid)
    assert _key("pushing") not in await _roll_keys(client, cid, "attack", item_id=wid)
    spell = (await client.post(f"/characters/{cid}/spells", json={"name": "Raggio", "level": 0, "attack_save": "ATK"})).json()["id"]
    assert _key("trip") not in await _roll_keys(client, cid, "attack", spell_id=spell)


async def test_a_critical_doubles_the_superiority_die(client, monkeypatch):
    cid = await _master(client, 7, "menacing")
    wid = await _sword(client, cid)
    _fixed(monkeypatch, 4)
    hit = await _hit(client, cid, wid, die=20)
    body = (await _damage(client, cid, hit, _key("menacing"))).json()
    assert body["option_result"]["extra_rolls"] == [4, 4]


async def test_only_one_maneuver_per_attack(client):
    cid = await _master(client, 7, "trip", "menacing", "precision")
    wid = await _sword(client, cid)
    hit = await _hit(client, cid, wid)
    r = await _damage(client, cid, hit, _key("trip"), _key("menacing"))
    assert r.status_code == 409 and r.json()["detail"]["code"] == "option_unavailable"
    assert await _dice_left(client, cid) == 5  # niente è stato pagato a metà


async def test_one_maneuver_chosen_before_blocks_the_one_after_the_hit(client):
    cid = await _master(client, 7, "lunging", "trip")
    wid = await _sword(client, cid)
    hit = await _hit(client, cid, wid, options=[_key("lunging")])
    assert _key("trip") not in await _roll_keys(client, cid, "attack", item_id=wid)  # l'attacco in sospeso ne ha già una
    r = await _damage(client, cid, hit, _key("trip"))
    assert r.status_code == 409 and await _dice_left(client, cid) == 4


async def test_the_next_attack_can_use_a_maneuver_again(client):
    cid = await _master(client, 7, "trip")
    wid = await _sword(client, cid)
    assert (await _damage(client, cid, await _hit(client, cid, wid), _key("trip"))).status_code == 200
    assert (await _damage(client, cid, await _hit(client, cid, wid), _key("trip"))).status_code == 200
    assert await _dice_left(client, cid) == 3


async def test_trip_menacing_and_goading_give_the_target_a_save_effect(client):
    cid = await _master(client, 7, "trip", "menacing", "goading", strength=16)
    wid = await _sword(client, cid)
    expected = {"trip": ("prone", "strength"), "menacing": ("frightened", "wisdom"), "goading": ("custom:goaded", "wisdom")}
    for maneuver, (condition, save) in expected.items():
        body = (await _damage(client, cid, await _hit(client, cid, wid), _key(maneuver))).json()
        assert body["option_result"]["targets"] == [_key(maneuver)]
        effect = (await client.get(f"/characters/{cid}/target-effects/{_key(maneuver)}")).json()["result"]
        assert (effect["condition"], effect["save_ability"], effect["save_dc"]) == (condition, save, 14)
        assert effect["ends_at"] == ({"anchor": "source", "edge": "end", "count": 1} if maneuver != "trip" else None)


@pytest.mark.parametrize("maneuver", ["maneuvering", "distracting"])
async def test_effects_without_a_condition_are_shown_to_the_gm_with_the_state(client, maneuver):
    cid = await _master(client, 7, maneuver)
    wid = await _sword(client, cid)
    await _damage(client, cid, await _hit(client, cid, wid), _key(maneuver))
    state = next(s for s in (await _full(client, cid))["active_states"] if s["key"] == f"maneuver_{maneuver}")
    assert state["data"]["others"] == [_key(maneuver)] and state["rounds_left"] == 1
    await client.post(f"/characters/{cid}/turn/new")
    assert not [s for s in (await _full(client, cid))["active_states"] if s["key"] == f"maneuver_{maneuver}"]


async def test_pushing_and_disarming_are_a_result_with_the_dc_and_no_condition(client):
    cid = await _master(client, 7, "pushing", "disarming", strength=16)
    wid = await _sword(client, cid)
    for maneuver in ("pushing", "disarming"):
        body = (await _damage(client, cid, await _hit(client, cid, wid), _key(maneuver))).json()
        assert "CD 14" in body["option_result"]["effects"][0]["it"] and body["option_result"]["targets"] == []


async def test_sweeping_attack_is_for_melee_and_names_the_damage_type(client):
    cid = await _master(client, 7, "sweeping")
    sword = await _sword(client, cid)
    bow = await _sword(client, cid, weapon_type="ranged", properties=["ammunition"])
    assert _key("sweeping") in await _roll_keys(client, cid, "attack", item_id=sword)
    assert _key("sweeping") not in await _roll_keys(client, cid, "attack", item_id=bow)
    body = (await _damage(client, cid, await _hit(client, cid, sword), _key("sweeping"))).json()
    assert "Taglio" in body["option_result"]["effects"][0]["it"] and "slashing" in body["option_result"]["effects"][0]["en"]


# ---------------------------------------------------------------------------
# Prima e dopo il tiro
# ---------------------------------------------------------------------------

async def test_lunging_attack_adds_the_die_to_the_damage_says_the_reach_and_is_for_melee(client, monkeypatch):
    cid = await _master(client, 7, "lunging")
    sword = await _sword(client, cid)
    bow = await _sword(client, cid, weapon_type="ranged", properties=["ammunition"])
    assert _key("lunging") in await _roll_keys(client, cid, "attack", item_id=sword)
    assert _key("lunging") not in await _roll_keys(client, cid, "attack", item_id=bow)
    _fixed(monkeypatch, 5)
    plain = (await _attack(client, cid, sword, confirm_extra_attack=True)).json()["damage_total"]
    body = (await _attack(client, cid, sword, confirm_extra_attack=True, options=[_key("lunging")])).json()
    assert body["damage_total"] == plain + 5 and "1,5 m" in body["option_result"]["effects"][0]["it"]
    assert await _dice_left(client, cid) == 4


async def test_lunging_attack_costs_the_die_even_on_a_miss(client):
    cid = await _master(client, 7, "lunging")
    sword = await _sword(client, cid)
    body = (await _attack(client, cid, sword, die=1, confirm_extra_attack=True, options=[_key("lunging")])).json()
    assert body["is_fumble"] is True and await _dice_left(client, cid) == 4


async def test_precision_attack_adds_the_die_to_the_roll_after_seeing_it(client, monkeypatch):
    cid = await _master(client, 7, "precision")
    sword = await _sword(client, cid)
    _fixed(monkeypatch, 6)
    hit = await _hit(client, cid, sword, die=8)
    r = await client.post(f"/characters/{cid}/last-roll/options", json={"options": [_key("precision")]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == hit["to_hit_total"] + 6 and body["option_result"]["extra_rolls"] == [6]
    assert await _dice_left(client, cid) == 4
    again = await client.post(f"/characters/{cid}/last-roll/options", json={"options": [_key("precision")]})
    assert again.status_code == 409  # un solo dado


async def test_precision_attack_blocks_a_second_maneuver_on_the_same_attack(client):
    cid = await _master(client, 7, "precision", "trip")
    sword = await _sword(client, cid)
    hit = await _hit(client, cid, sword, die=8)
    assert (await client.post(f"/characters/{cid}/last-roll/options", json={"options": [_key("precision")]})).status_code == 200
    r = await _damage(client, cid, hit, _key("trip"))
    assert r.status_code == 409 and await _dice_left(client, cid) == 4


async def test_precision_attack_is_not_offered_for_a_skill_roll(client):
    cid = await _master(client, 7, "precision")
    assert _key("precision") not in await _roll_keys(client, cid, "skill", skill="athletics")


async def test_feinting_attack_is_a_bonus_action_then_gives_advantage_and_the_die_to_the_next_attack(client, monkeypatch):
    cid = await _master(client, 7, "feinting")
    sword = await _sword(client, cid)
    assert _key("feinting_strike") not in await _roll_keys(client, cid, "attack", item_id=sword)  # prima la finta
    _fixed(monkeypatch, 5)
    r = await _use(client, cid, _key("feinting"))
    assert r.status_code == 200, r.text
    assert (await _turn(client, cid))["bonus_used"] is True and await _dice_left(client, cid) == 4
    assert _key("feinting_strike") in await _roll_keys(client, cid, "attack", item_id=sword)
    body = (await _attack(client, cid, sword, confirm_extra_attack=True, options=[_key("feinting_strike")])).json()
    plain = (await _attack(client, cid, sword, confirm_extra_attack=True)).json()
    assert body["mode_applied"] == "advantage" and body["damage_total"] == plain["damage_total"] + 5
    assert await _dice_left(client, cid) == 4  # il dado si è speso alla finta, non all'attacco
    assert _key("feinting_strike") not in await _roll_keys(client, cid, "attack", item_id=sword)  # vale per un attacco


async def test_feinting_attack_survives_an_attack_on_another_creature_and_ends_with_the_turn(client):
    cid = await _master(client, 7, "feinting")
    sword = await _sword(client, cid)
    await _use(client, cid, _key("feinting"))
    await _attack(client, cid, sword, confirm_extra_attack=True)  # contro un'altra creatura: non dichiara la finta
    assert _key("feinting_strike") in await _roll_keys(client, cid, "attack", item_id=sword)  # vale ancora per l'attacco giusto
    await client.post(f"/characters/{cid}/turn/new")
    assert _key("feinting_strike") not in await _roll_keys(client, cid, "attack", item_id=sword)


async def test_feinting_attack_is_used_up_by_the_attack_that_declares_it(client):
    cid = await _master(client, 7, "feinting")
    sword = await _sword(client, cid)
    await _use(client, cid, _key("feinting"))
    await _attack(client, cid, sword, confirm_extra_attack=True)  # un altro bersaglio
    body = (await _attack(client, cid, sword, confirm_extra_attack=True, options=[_key("feinting_strike")])).json()
    assert body["mode_applied"] == "advantage"
    assert _key("feinting_strike") not in await _roll_keys(client, cid, "attack", item_id=sword)


async def test_feinting_attack_refused_with_the_bonus_action_spent_or_no_dice_and_costs_nothing(client):
    cid = await _master(client, 7, "feinting")
    await client.post(f"/characters/{cid}/turn/use", json={"slot": "bonus"})
    r = await _use(client, cid, _key("feinting"))
    assert r.status_code == 409 and r.json()["detail"]["code"] == "turn_slot_used" and await _dice_left(client, cid) == 5
    row = await _ability(client, cid, SD)
    await client.patch(f"/characters/{cid}/abilities/{row['id']}", json={"uses": 0})
    await client.post(f"/characters/{cid}/turn/new")
    r = await _use(client, cid, _key("feinting"))
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_uses"


async def test_commanders_strike_gives_up_an_attack_and_shows_the_die_for_the_ally(client, monkeypatch):
    cid = await _master(client, 7, "commanders_strike")
    _fixed(monkeypatch, 6)
    r = await _use(client, cid, _key("commanders_strike"))
    assert r.status_code == 200, r.text
    assert r.json()["rolls"] == [6] and r.json()["given"] == 6
    turn = await _turn(client, cid)
    assert turn["bonus_used"] is True and turn["action_attacks"] == 1 and turn["attacks_made"] == 0
    assert await _dice_left(client, cid) == 4


async def test_commanders_strike_needs_an_attack_left_in_the_attack_action(client):
    cid = await _master(client, 3, "commanders_strike")  # un solo attacco per azione
    assert (await _use(client, cid, _key("commanders_strike"))).status_code == 200
    await client.post(f"/characters/{cid}/turn/use", json={"slot": "bonus", "used": False})
    r = await _use(client, cid, _key("commanders_strike"))
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_attack_left" and await _dice_left(client, cid) == 3


async def test_the_attack_given_up_is_one_less_attack_for_the_fighter(client):
    cid = await _master(client, 7, "commanders_strike")
    sword = await _sword(client, cid)
    await _use(client, cid, _key("commanders_strike"))
    assert (await _attack(client, cid, sword)).status_code == 200
    assert (await _attack(client, cid, sword)).json()["detail"]["code"] == "attack_limit"


async def test_rally_shows_the_die_plus_charisma_as_temporary_hit_points_for_an_ally(client, monkeypatch):
    cid = await _master(client, 7, "rally", charisma=14)
    _fixed(monkeypatch, 5)
    r = await _use(client, cid, _key("rally"))
    assert r.status_code == 200, r.text
    assert r.json()["given"] == 5 + 2 and (await _turn(client, cid))["bonus_used"] is True
    assert (await _full(client, cid))["temp_hp"] == 0  # i PF temporanei sono dell'alleato, non scritti sulla scheda


async def test_rally_with_a_negative_charisma_never_gives_less_than_zero(client, monkeypatch):
    cid = await _master(client, 7, "rally", charisma=1)
    _fixed(monkeypatch, 2)
    assert (await _use(client, cid, _key("rally"))).json()["given"] == 0


async def test_parry_reduces_the_melee_damage_by_the_die_plus_dexterity_and_spends_the_reaction(client, monkeypatch):
    cid = await _master(client, 7, "parry", dexterity=14)
    hp = (await _full(client, cid))["current_hit_points"]
    assert _key("parry") in await _roll_keys(client, cid, "damage_taken", damage_type="slashing")
    _fixed(monkeypatch, 5)
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 12, "damage_type": "slashing",
                                                           "options": [_key("parry")]})
    assert r.status_code == 200, r.text
    assert (await _full(client, cid))["current_hit_points"] == hp - (12 - 5 - 2)
    assert (await _turn(client, cid))["reaction_used"] is True and await _dice_left(client, cid) == 4
    assert _key("parry") not in await _roll_keys(client, cid, "damage_taken", damage_type="slashing")


async def test_parry_never_brings_the_damage_below_zero_nor_above_what_was_dealt(client, monkeypatch):
    cid = await _master(client, 7, "parry", dexterity=20)
    hp = (await _full(client, cid))["current_hit_points"]
    _fixed(monkeypatch, 8)
    await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 3, "damage_type": "slashing", "options": [_key("parry")]})
    assert (await _full(client, cid))["current_hit_points"] == hp
    low = await _master(client, 7, "parry", dexterity=3)  # Destrezza -4: dado 1 + (-4) = -3, il danno non cresce
    hp = (await _full(client, low))["current_hit_points"]
    _fixed(monkeypatch, 1)
    await client.patch(f"/characters/{low}/hp", json={"op": "damage", "value": 6, "damage_type": "slashing", "options": [_key("parry")]})
    assert (await _full(client, low))["current_hit_points"] == hp - 6


async def test_riposte_is_a_reaction_attack_that_does_not_count_as_an_attack_of_the_action(client, monkeypatch):
    cid = await _master(client, 7, "riposte")
    sword = await _sword(client, cid)
    _fixed(monkeypatch, 4)
    plain = (await _attack(client, cid, sword, confirm_extra_attack=True)).json()["damage_total"]
    body = (await _attack(client, cid, sword, options=[_key("riposte")])).json()
    assert body["damage_total"] == plain + 4
    turn = await _turn(client, cid)
    assert turn["reaction_used"] is True and turn["action_attacks"] == 1 and await _dice_left(client, cid) == 4
    assert _key("riposte") not in await _roll_keys(client, cid, "attack", item_id=sword)  # la reazione è spesa


async def test_riposte_is_only_for_melee_weapons(client):
    cid = await _master(client, 7, "riposte")
    bow = await _sword(client, cid, weapon_type="ranged", properties=["ammunition"])
    assert _key("riposte") not in await _roll_keys(client, cid, "attack", item_id=bow)


async def test_evasive_footwork_adds_the_die_to_ac_until_the_player_stops_moving(client, monkeypatch):
    cid = await _master(client, 7, "evasive_footwork")
    ac = (await _full(client, cid))["ac"]
    _fixed(monkeypatch, 4)
    r = await _use(client, cid, _key("evasive_footwork"))
    assert r.status_code == 200, r.text
    full = await _full(client, cid)
    assert full["ac"] == ac + 4 or full["ac_breakdown"]["rules"] == 4
    assert await _dice_left(client, cid) == 4 and (await _turn(client, cid))["bonus_used"] is False
    assert (await client.delete(f"/characters/{cid}/active-states/evasive_footwork")).status_code == 200
    assert (await _full(client, cid))["ac_breakdown"]["rules"] == 0


async def test_evasive_footwork_ends_with_the_turn_and_counts_in_the_session_ac(client, monkeypatch):
    cid = await _master(client, 7, "evasive_footwork")
    _fixed(monkeypatch, 3)
    await _use(client, cid, _key("evasive_footwork"))
    await client.post(f"/characters/{cid}/turn/new")
    assert (await _full(client, cid))["ac_breakdown"]["rules"] == 0


async def test_relentless_gives_back_a_die_at_initiative_only_with_none_left(client):
    cid = await _master(client, 15)
    assert "fighter.relentless" not in await _roll_keys(client, cid, "initiative")
    row = await _ability(client, cid, SD)
    await client.patch(f"/characters/{cid}/abilities/{row['id']}", json={"uses": 0})
    assert "fighter.relentless" in await _roll_keys(client, cid, "initiative")
    r = await client.post(f"/characters/{cid}/dice/initiative", json={"die": 8, "options": ["fighter.relentless"]})
    assert r.status_code == 200, r.text
    assert await _dice_left(client, cid) == 1
    assert "fighter.relentless" not in await _roll_keys(client, cid, "initiative")


async def test_relentless_is_for_the_battle_master_from_level_15(client):
    cid = await _master(client, 14)
    assert "fighter.relentless" not in (await _keys_of(client, cid))
    assert "fighter.relentless" in await _keys_of(client, await _master(client, 15))


async def test_passive_rows_of_the_battle_master(client):
    keys = await _keys_of(client, await _master(client, 10))
    assert {"fighter.know_your_enemy", "fighter.improved_combat_superiority"} <= keys
    assert "fighter.student_of_war" not in keys  # la competenza in uno strumento è in «lavori successivi»


async def test_a_maneuver_row_is_visible_in_turn_by_its_activation(client):
    cid = await _master(client, 15, "feinting", "commanders_strike", "rally", "evasive_footwork", "parry", "riposte", "trip",
                        "goading", "menacing")
    full = await _full(client, cid)
    rows = {a["feature_key"]: a for a in full["abilities"] if a["feature_key"].startswith("fighter.maneuver_")}
    assert rows[_key("feinting")]["has_on_use"] and rows[_key("feinting")]["spends_left"] == 6
    assert rows[_key("commanders_strike")]["action_type"] == "bonus_action" and rows[_key("rally")]["has_on_use"]
    assert rows[_key("parry")]["action_type"] == "reaction" and rows[_key("trip")]["is_passive"] is True
