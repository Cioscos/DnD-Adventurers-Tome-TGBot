"""Ranger 2014, Cacciatore (Task 26): Preda del Cacciatore, Tattiche Difensive, Multiattacco e Difesa del Cacciatore Superiore."""
from __future__ import annotations

import pytest

from tests.integration.rules.test_2014_barbarian_round1 import _combatant_states, _in_encounter
from tests.integration.rules.test_2014_bard import _ability, _full, _keys_of, _roll_keys, _use
from tests.integration.rules.test_2014_fighter_styles import _item
from tests.integration.rules.test_2014_paladin import _new_turn, _turn
from tests.integration.rules.test_2014_ranger import _choice, _ranger, _resolve, _states
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user

COLOSSUS, HORDE, GIANT = "ranger.colossus_slayer", "ranger.horde_breaker", "ranger.giant_killer"
ESCAPE, MULTI_DEF, STEEL = "ranger.escape_the_horde", "ranger.multiattack_defense", "ranger.steel_will"
WHIRLWIND, WHIRL_HIT, VOLLEY, VOLLEY_HIT = "ranger.whirlwind_attack", "ranger.whirlwind_attack_hit", "ranger.volley", "ranger.volley_hit"
EVASION, EVASION_OK, EVASION_KO = "ranger.evasion", "ranger.evasion_success", "ranger.evasion_failed"
TIDE, UNCANNY = "ranger.stand_against_the_tide", "ranger.uncanny_dodge"
PREY, TACTICS, MULTI, SUPERIOR = "hunters_prey", "defensive_tactics", "hunter_multiattack", "superior_hunters_defense"


async def _hunter(client, level, *picks: tuple[str, str], **scores) -> int:
    """Un Cacciatore con le scelte dell'archetipo già fatte: ``picks`` = (gruppo, opzione)."""
    cid = await _ranger(client, level, "hunter", **scores)
    for group, option in picks:
        r = await _resolve(client, cid, group, option)
        assert r.status_code == 200, r.text
    return cid


async def _sword(client, cid, **kw) -> int:
    return await _item(client, cid, "Spada", damage_dice="1d8", weapon_type="melee", properties=[], **kw)


async def _bow(client, cid) -> int:
    return await _item(client, cid, "Arco lungo", damage_dice="1d8", weapon_type="ranged", properties=["ammunition"],
                       equip="main_hand")


async def _attack(client, cid, wid, die=10, extra=True, **body):
    r = await client.post(f"/characters/{cid}/items/{wid}/attack",
                          json={"die": die, **({"confirm_extra_attack": True} if extra else {}), **body})
    return r


async def _hit(client, cid, wid, die=10, **body) -> dict:
    r = await _attack(client, cid, wid, die, defer_damage=True, **body)
    assert r.status_code == 200, r.text
    return r.json()


async def _damage(client, cid, hit, *options):
    return await client.post(f"/characters/{cid}/attack/{hit['attack_id']}/damage", json={"options": list(options)})


async def _hurt(client, cid, value, *options):
    return await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": value, "options": list(options)})


async def _full_hp(client, cid, hp=60):
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": hp})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": hp})


async def _save(client, cid, ability, *options, die=10):
    r = await client.post(f"/characters/{cid}/saving_throws/{ability}/roll", json={"die": die, "options": list(options)})
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# Le quattro scelte dell'archetipo
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,group,options", [
    (3, PREY, {"horde_breaker", "colossus_slayer", "giant_killer"}),
    (7, TACTICS, {"escape_the_horde", "multiattack_defense", "steel_will"}),
    (11, MULTI, {"whirlwind_attack", "volley"}),
    (15, SUPERIOR, {"evasion", "stand_against_the_tide", "uncanny_dodge"})])
async def test_each_hunter_choice_comes_at_its_level_with_its_options(client, level, group, options):
    before = _choice(await _full(client, await _ranger(client, level - 1, "hunter")), group)
    assert before is None
    choice = _choice(await _full(client, await _ranger(client, level, "hunter")), group)
    assert choice["count"] == 1 and {o["key"] for o in choice["options"]} == options
    assert all(o["name"]["it"] and o["name"]["en"] and o["summary"]["it"] for o in choice["options"])


async def test_only_the_chosen_option_becomes_a_row_and_the_choice_closes(client):
    cid = await _hunter(client, 3, (PREY, "colossus_slayer"))
    keys = await _keys_of(client, cid)
    assert COLOSSUS in keys and not {HORDE, GIANT} & keys and _choice(await _full(client, cid), PREY) is None


@pytest.mark.parametrize("options", [[], ["colossus_slayer", "giant_killer"], ["steel_will"]])
async def test_exactly_one_option_of_the_group_is_taken(client, options):
    cid = await _ranger(client, 3, "hunter")
    assert (await _resolve(client, cid, PREY, *options)).status_code == 422


async def test_a_ranger_with_another_archetype_has_none_of_the_hunter_choices(client):
    full = await _full(client, await _ranger(client, 15, "beast_master"))
    assert not {PREY, TACTICS, MULTI, SUPERIOR} & {c.get("group") for c in full["pending_choices"]}


# ---------------------------------------------------------------------------
# Sterminatore di Colossi
# ---------------------------------------------------------------------------

async def test_colossus_slayer_adds_a_d8_after_the_hit_once_per_turn(client):
    cid = await _hunter(client, 3, (PREY, "colossus_slayer"))
    wid = await _sword(client, cid, equip="main_hand")
    hit = await _hit(client, cid, wid)
    assert COLOSSUS in await _roll_keys(client, cid, "attack", item_id=wid)
    r = await _damage(client, cid, hit, COLOSSUS)
    assert r.status_code == 200, r.text
    block = r.json()["option_result"]
    assert len(block["extra_rolls"]) == 1 and 1 <= block["extra_rolls"][0] <= 8
    assert r.json()["damage_total"] == hit["damage_total"] + block["extra_total"]
    assert COLOSSUS not in await _roll_keys(client, cid, "attack", item_id=wid)
    second = await _hit(client, cid, wid)
    refused = await _damage(client, cid, second, COLOSSUS)
    assert refused.status_code == 409 and refused.json()["detail"]["code"] == "option_unavailable"
    await _new_turn(client, cid)
    assert COLOSSUS in await _roll_keys(client, cid, "attack", item_id=wid)


async def test_colossus_slayer_dice_double_on_a_critical_hit(client):
    cid = await _hunter(client, 3, (PREY, "colossus_slayer"))
    wid = await _sword(client, cid, equip="main_hand")
    hit = await _hit(client, cid, wid, die=20)
    r = await _damage(client, cid, hit, COLOSSUS)
    assert len(r.json()["option_result"]["extra_rolls"]) == 2


async def test_colossus_slayer_is_not_there_for_the_other_choices(client):
    cid = await _hunter(client, 3, (PREY, "giant_killer"))
    wid = await _sword(client, cid, equip="main_hand")
    assert COLOSSUS not in await _roll_keys(client, cid, "attack", item_id=wid)


# ---------------------------------------------------------------------------
# Devastatore dell'Orda
# ---------------------------------------------------------------------------

async def test_horde_breaker_is_an_extra_attack_after_a_first_one_and_once_per_turn(client):
    cid = await _hunter(client, 3, (PREY, "horde_breaker"))
    wid = await _sword(client, cid, equip="main_hand")
    assert HORDE not in await _roll_keys(client, cid, "attack", item_id=wid)  # serve un primo attacco
    assert (await _attack(client, cid, wid, extra=False)).status_code == 200
    assert HORDE in await _roll_keys(client, cid, "attack", item_id=wid)
    r = await _attack(client, cid, wid, extra=False, options=[HORDE])  # oltre l'unico attacco dell'azione, senza conferma
    assert r.status_code == 200, r.text
    assert (await _turn(client, cid))["action_attacks"] == 1 and (await _turn(client, cid))["attacks_made"] == 2
    assert HORDE not in await _roll_keys(client, cid, "attack", item_id=wid)
    again = await _attack(client, cid, wid, options=[HORDE])
    assert again.status_code == 409 and again.json()["detail"]["code"] == "option_unavailable"
    await _new_turn(client, cid)
    assert HORDE not in await _roll_keys(client, cid, "attack", item_id=wid)


async def test_horde_breaker_does_not_use_the_reaction_or_the_bonus_action(client):
    cid = await _hunter(client, 3, (PREY, "horde_breaker"))
    wid = await _sword(client, cid, equip="main_hand")
    await _attack(client, cid, wid, extra=False)
    await _attack(client, cid, wid, extra=False, options=[HORDE])
    turn = await _turn(client, cid)
    assert turn["reaction_used"] is False and turn["bonus_used"] is False


# ---------------------------------------------------------------------------
# Uccisore di Giganti
# ---------------------------------------------------------------------------

async def test_giant_killer_is_a_weapon_reaction_attack_outside_the_attack_action(client):
    cid = await _hunter(client, 3, (PREY, "giant_killer"))
    wid = await _sword(client, cid, equip="main_hand")
    bow = await _bow(client, cid)
    assert GIANT in await _roll_keys(client, cid, "attack", item_id=wid)
    await _attack(client, cid, wid, extra=False)  # l'attacco dell'azione è già fatto
    r = await _attack(client, cid, wid, extra=False, options=[GIANT])
    assert r.status_code == 200, r.text
    turn = await _turn(client, cid)
    assert turn["reaction_used"] is True and turn["action_attacks"] == 1
    assert GIANT not in await _roll_keys(client, cid, "attack", item_id=wid)
    again = await _attack(client, cid, wid, options=[GIANT])
    assert again.status_code == 409 and again.json()["detail"]["code"] == "option_unavailable"
    await _new_turn(client, cid)
    assert (await _turn(client, cid))["reaction_used"] is False and GIANT in await _roll_keys(client, cid, "attack", item_id=wid)
    # il manuale dice «attaccare la creatura», senza «in mischia» (R31): anche l'arco
    assert GIANT in await _roll_keys(client, cid, "attack", item_id=bow)
    assert (await _attack(client, cid, bow, extra=False, options=[GIANT])).status_code == 200


async def test_giant_killer_is_not_offered_after_taking_damage(client):
    cid = await _hunter(client, 3, (PREY, "giant_killer"))
    await _full_hp(client, cid)
    await _sword(client, cid, equip="main_hand")
    body = (await _hurt(client, cid, 5)).json()
    assert GIANT not in {o["key"] for o in body.get("reactions") or []}


# ---------------------------------------------------------------------------
# Tattiche Difensive
# ---------------------------------------------------------------------------

async def test_escape_the_horde_is_a_permanent_note_for_the_gm_and_the_group(client, test_session_factory, monkeypatch):
    sid, cid = await _in_encounter(client, test_session_factory, monkeypatch)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "ranger", "level": 7, "hit_die": 10,
                                                              "subclass": "Cacciatore"})
    assert r.status_code == 201, r.text
    await _resolve(client, cid, PREY, "colossus_slayer")
    assert "escape_the_horde" not in {s["key"] for s in await _states(client, cid)}
    assert (await _resolve(client, cid, TACTICS, "escape_the_horde")).status_code == 200
    assert "escape_the_horde" in {s["key"] for s in await _states(client, cid)}
    for viewer in (GM_ID, PLAYER_ID):
        states = {s["key"]: s for s in await _combatant_states(client, sid, viewer)}
        [other] = states["escape_the_horde"]["others"]
        assert other["key"] == ESCAPE and "opportunità" in other["text"] and "svantaggio" in other["text"]


async def test_multiattack_defense_adds_four_to_ac_after_a_hit_until_the_turn_changes(client):
    cid = await _hunter(client, 7, (PREY, "colossus_slayer"), (TACTICS, "multiattack_defense"))
    await _full_hp(client, cid)
    base = (await _full(client, cid))["ac"]
    assert MULTI_DEF in await _roll_keys(client, cid, "damage_taken")
    assert (await _hurt(client, cid, 5, MULTI_DEF)).status_code == 200
    full = await _full(client, cid)
    assert full["ac"] == base + 4 and full["current_hit_points"] == 55
    state = next(s for s in full["active_states"] if s["key"] == "multiattack_defense")
    assert state["data"]["others"] == [MULTI_DEF]
    assert MULTI_DEF in await _roll_keys(client, cid, "damage_taken")  # un altro colpo di un'altra creatura lo rinnova
    await _new_turn(client, cid)
    assert (await _full(client, cid))["ac"] == base and not any(
        s["key"] == "multiattack_defense" for s in await _states(client, cid))


async def test_multiattack_defense_ends_with_the_turn_of_the_attacker_in_an_encounter(client, test_session_factory, monkeypatch):
    sid, cid = await _in_encounter(client, test_session_factory, monkeypatch)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "ranger", "level": 7, "hit_die": 10,
                                                              "subclass": "Cacciatore"})
    assert r.status_code == 201, r.text
    await _resolve(client, cid, PREY, "colossus_slayer")
    await _resolve(client, cid, TACTICS, "multiattack_defense")
    await _full_hp(client, cid)
    base = (await _full(client, cid))["ac"]
    as_user(GM_ID)
    assert (await client.post(f"/sessions/{sid}/encounter/next-turn")).status_code == 200  # tocca al primo goblin
    as_user(PLAYER_ID)
    assert (await _hurt(client, cid, 5, MULTI_DEF)).status_code == 200
    assert (await _full(client, cid))["ac"] == base + 4
    as_user(GM_ID)
    assert (await client.post(f"/sessions/{sid}/encounter/next-turn")).status_code == 200  # finisce il turno del goblin
    as_user(PLAYER_ID)
    assert (await _full(client, cid))["ac"] == base and "multiattack_defense" not in {s["key"] for s in await _states(client, cid)}
    as_user(GM_ID)
    assert (await client.post(f"/sessions/{sid}/encounter/prev-turn")).status_code == 200  # l'annullamento la rimette
    as_user(PLAYER_ID)
    assert (await _full(client, cid))["ac"] == base + 4


async def test_multiattack_defense_is_only_for_the_hunter_who_chose_it(client):
    cid = await _hunter(client, 7, (PREY, "colossus_slayer"), (TACTICS, "steel_will"))
    assert MULTI_DEF not in await _roll_keys(client, cid, "damage_taken")


async def test_steel_will_gives_advantage_on_saves_against_being_frightened(client):
    cid = await _hunter(client, 7, (PREY, "colossus_slayer"), (TACTICS, "steel_will"))
    for ability in ("wisdom", "strength"):
        assert STEEL in await _roll_keys(client, cid, "save", ability=ability)
    r = await client.post(f"/characters/{cid}/saving_throws/wisdom/roll", json={"dice": [3, 17], "options": [STEEL]})
    assert r.status_code == 200 and r.json()["mode"] == "advantage" and r.json()["die"] == 17
    plain = await client.post(f"/characters/{cid}/saving_throws/wisdom/roll", json={"die": 10})
    assert plain.json()["mode"] == "normal"


async def test_steel_will_is_not_there_for_the_other_choices(client):
    cid = await _hunter(client, 7, (PREY, "colossus_slayer"), (TACTICS, "escape_the_horde"))
    assert STEEL not in await _roll_keys(client, cid, "save", ability="wisdom")


# ---------------------------------------------------------------------------
# Multiattacco
# ---------------------------------------------------------------------------

async def _multi(client, option, weapon="sword"):
    cid = await _hunter(client, 11, (PREY, "colossus_slayer"), (TACTICS, "steel_will"), (MULTI, option))
    wid = await (_sword(client, cid, equip="main_hand") if weapon == "sword" else _bow(client, cid))
    return cid, wid


async def test_whirlwind_attack_takes_the_action_once_and_opens_unlimited_melee_attacks(client):
    cid, wid = await _multi(client, "whirlwind_attack")
    assert WHIRL_HIT not in await _roll_keys(client, cid, "attack", attack_mode="melee")
    r = await _use(client, cid, WHIRLWIND)
    assert r.status_code == 200, r.text
    assert (await _turn(client, cid))["action_used"] is True
    assert any(s["key"] == "whirlwind_attack" for s in await _states(client, cid))
    for _ in range(5):  # un tiro per colpire separato per ogni creatura, senza limite
        r = await _attack(client, cid, wid, extra=False, options=[WHIRL_HIT])
        assert r.status_code == 200, r.text
    turn = await _turn(client, cid)
    assert turn["attacks_made"] == 5 and turn["action_attacks"] == 0
    await _new_turn(client, cid)
    assert WHIRL_HIT not in await _roll_keys(client, cid, "attack", attack_mode="melee")


async def test_whirlwind_attack_is_for_melee_weapons_only(client):
    cid, wid = await _multi(client, "whirlwind_attack")
    bow = await _bow(client, cid)
    await _use(client, cid, WHIRLWIND)
    assert (await _attack(client, cid, bow, extra=False, options=[WHIRL_HIT])).status_code == 409


async def test_whirlwind_attack_needs_the_action(client):
    cid, _ = await _multi(client, "whirlwind_attack")
    assert (await _use(client, cid, WHIRLWIND)).status_code == 200
    again = await _use(client, cid, WHIRLWIND)
    assert again.status_code == 409 and again.json()["detail"]["code"] == "turn_slot_used"


async def test_volley_takes_the_action_once_and_opens_unlimited_ranged_attacks(client):
    cid, bow = await _multi(client, "volley", "bow")
    sword = await _sword(client, cid)
    assert VOLLEY_HIT not in await _roll_keys(client, cid, "attack", attack_mode="melee")
    assert (await _use(client, cid, VOLLEY)).status_code == 200
    for _ in range(4):
        assert (await _attack(client, cid, bow, extra=False, options=[VOLLEY_HIT])).status_code == 200
    assert (await _turn(client, cid))["action_attacks"] == 0
    assert (await _attack(client, cid, sword, extra=False, options=[VOLLEY_HIT])).status_code == 409


async def test_volley_uses_one_piece_of_ammunition_for_each_target(client):
    cid, bow = await _multi(client, "volley", "bow")
    arrows = await _item(client, cid, "Frecce", "ammunition", equip="ammunition")
    await client.patch(f"/characters/{cid}/items/{arrows}", json={"quantity": 5})
    await _use(client, cid, VOLLEY)
    for _ in range(3):
        await _attack(client, cid, bow, extra=False, options=[VOLLEY_HIT])
    left = next(i["quantity"] for i in (await _full(client, cid))["items"] if i["id"] == arrows)
    assert left == 2


async def test_only_the_chosen_multiattack_is_a_row(client):
    cid, _ = await _multi(client, "volley", "bow")
    keys = await _keys_of(client, cid)
    assert VOLLEY in keys and WHIRLWIND not in keys


# ---------------------------------------------------------------------------
# Difesa del Cacciatore Superiore
# ---------------------------------------------------------------------------

async def _superior(client, option, **scores):
    return await _hunter(client, 15, (PREY, "colossus_slayer"), (TACTICS, "steel_will"), (MULTI, "volley"),
                         (SUPERIOR, option), **scores)


async def test_evasion_takes_no_damage_on_a_success_and_half_on_a_failure(client):
    cid = await _superior(client, "evasion")
    await _full_hp(client, cid)
    assert EVASION in await _roll_keys(client, cid, "save", ability="dexterity")
    assert EVASION not in await _roll_keys(client, cid, "save", ability="wisdom")
    body = await _save(client, cid, "dexterity", EVASION)
    assert "Elusione" in body["option_result"]["effects"][0]["it"]
    keys = await _roll_keys(client, cid, "damage_taken")
    assert EVASION_OK in keys and EVASION_KO in keys
    assert (await _hurt(client, cid, 20, EVASION_OK)).json()["current_hit_points"] == 60
    assert EVASION_OK not in await _roll_keys(client, cid, "damage_taken")
    await _save(client, cid, "dexterity", EVASION)
    assert (await _hurt(client, cid, 20, EVASION_KO)).json()["current_hit_points"] == 50


async def test_evasion_damage_options_need_the_confirmed_save(client):
    cid = await _superior(client, "evasion")
    await _full_hp(client, cid)
    r = await _hurt(client, cid, 20, EVASION_OK)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "option_unavailable"


async def test_evasion_has_no_incapacitated_exception_in_the_ranger_text(client):
    cid = await _superior(client, "evasion")
    await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"incapacitated": True}})
    assert EVASION in await _roll_keys(client, cid, "save", ability="dexterity")


async def test_uncanny_dodge_halves_the_damage_and_spends_the_reaction(client):
    cid = await _superior(client, "uncanny_dodge")
    await _full_hp(client, cid)
    assert UNCANNY in await _roll_keys(client, cid, "damage_taken")
    assert (await _hurt(client, cid, 21, UNCANNY)).json()["current_hit_points"] == 60 - 10  # per difetto
    assert (await _turn(client, cid))["reaction_used"] is True
    assert UNCANNY not in await _roll_keys(client, cid, "damage_taken")
    refused = await _hurt(client, cid, 20, UNCANNY)
    assert refused.status_code == 409 and refused.json()["detail"]["code"] == "option_unavailable"
    await _new_turn(client, cid)
    assert UNCANNY in await _roll_keys(client, cid, "damage_taken")


async def test_stand_against_the_tide_is_a_reaction_with_a_note_for_the_gm(client):
    cid = await _superior(client, "stand_against_the_tide")
    row = await _ability(client, cid, TIDE)
    assert row["action_type"] == "reaction"
    r = await _use(client, cid, TIDE)
    assert r.status_code == 200, r.text
    assert (await _turn(client, cid))["reaction_used"] is True
    state = next(s for s in await _states(client, cid) if s["key"] == "stand_against_the_tide")
    assert state["data"]["others"] == [TIDE]
    again = await _use(client, cid, TIDE)
    assert again.status_code == 409 and again.json()["detail"]["code"] == "turn_slot_used"


async def test_only_the_chosen_superior_defense_is_a_row(client):
    keys = await _keys_of(client, await _superior(client, "uncanny_dodge"))
    assert UNCANNY in keys and not {TIDE, EVASION} & keys
