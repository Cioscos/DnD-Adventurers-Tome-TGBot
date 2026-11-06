"""Warlock 2014 (Task 29): i tre patroni e l'Arcanum Mistico."""
from __future__ import annotations

import pytest

from tests.integration.rules.test_2014_barbarian import _keys, _weapon
from tests.integration.rules.test_2014_bard import _ability, _full, _keys_of, _use
from tests.integration.rules.test_2014_fighter_eldritch_knight import _hit, _spell
from tests.integration.rules.test_2014_paladin import _new_turn, _rest, _turn
from tests.integration.rules.test_2014_warlock import _choice, _pact_slots, _resolve, _set_used, _warlock
from tests.integration.rules.test_2014_warlock_invocations import _caster, _spells_by_index

FEY, MISTY, DEFENSES, DELIRIUM = "warlock.fey_presence", "warlock.misty_escape", "warlock.beguiling_defenses", "warlock.dark_delirium"
BLESSING, LUCK, RESILIENCE, HURL = "warlock.dark_ones_blessing", "warlock.dark_ones_own_luck", "warlock.fiendish_resilience", "warlock.hurl_through_hell"
WARD, SHIELD, THRALL = "warlock.entropic_ward", "warlock.thought_shield", "warlock.create_thrall"


def _states(full: dict) -> dict[str, dict]:
    return {s["key"]: s for s in full["active_states"] or []}


async def _patron(client, level, patron, **scores) -> int:
    return await _warlock(client, level, patron, **{"charisma": 16, **scores})


# ---------------------------------------------------------------------------
# Il patrono dà solo i suoi privilegi, ai suoi livelli
# ---------------------------------------------------------------------------

PATRON_ROWS = {
    "archfey": (FEY, MISTY, DEFENSES, DELIRIUM), "fiend": (BLESSING, LUCK, RESILIENCE, HURL),
    "great_old_one": ("warlock.awakened_mind", WARD, SHIELD, THRALL),
}


@pytest.mark.parametrize("patron", list(PATRON_ROWS))
async def test_a_patron_gives_its_own_features_only(client, patron):
    keys = await _keys_of(client, await _patron(client, 14, patron))
    mine = set(PATRON_ROWS[patron])
    others = {k for p, rows in PATRON_ROWS.items() if p != patron for k in rows}
    assert mine <= keys and not others & keys
    assert not keys & {f"warlock.expanded_spell_list_{p}" for p in PATRON_ROWS if p != patron}


@pytest.mark.parametrize("patron,levels", [("archfey", (1, 6, 10, 14)), ("fiend", (1, 6, 10, 14)), ("great_old_one", (1, 6, 10, 14))])
async def test_patron_features_arrive_at_levels_1_6_10_and_14(client, patron, levels):
    rows = PATRON_ROWS[patron]
    for level, expected in zip(levels, (rows[:1], rows[:2], rows[:3], rows[:4])):
        keys = await _keys_of(client, await _patron(client, level, patron))
        assert set(expected) <= keys
        assert not set(rows[len(expected):]) & keys
        if level == 1:  # 1° livello: solo Presenza Fatata / Benedizione dell'Oscuro / Mente Risvegliata
            assert (set(rows[:1]) & keys) == set(rows[:1])


@pytest.mark.parametrize("patron", list(PATRON_ROWS))
async def test_without_a_recognised_patron_there_are_no_patron_features(client, patron):
    keys = await _keys_of(client, await _patron(client, 14, None))
    assert not keys & set(PATRON_ROWS[patron])


# ---------------------------------------------------------------------------
# Il Signore Fatato
# ---------------------------------------------------------------------------

async def test_fey_presence_is_an_action_with_the_spell_dc_and_a_choice_of_effect(client):
    cid = await _patron(client, 1, "archfey", charisma=18)
    row = await _ability(client, cid, FEY)
    assert row["max_uses"] == 1 and row["restoration_type"] == "short_rest"
    assert (await _use(client, cid, FEY, params={"mode": "asleep"})).status_code == 422
    assert (await _turn(client, cid))["action_used"] is False
    r = await _use(client, cid, FEY, params={"mode": "charmed"})
    assert r.status_code == 200, r.text
    state = _states(await _full(client, cid))["fey_presence"]
    assert state["data"]["dc"] == 8 + 2 + 4 and state["data"]["save"] == "wisdom" and state["data"]["mode"] == "charmed"
    assert (await _turn(client, cid))["action_used"] is True and r.json()["targets"] == [FEY]
    assert (await _use(client, cid, FEY, params={"mode": "charmed"})).status_code == 409  # un solo uso
    await _rest(client, cid, "short")
    assert (await _ability(client, cid, FEY))["uses"] == 1


@pytest.mark.parametrize("mode", ["charmed", "frightened"])
async def test_fey_presence_charms_or_frightens_until_the_end_of_my_next_turn(client, mode):
    cid = await _patron(client, 1, "archfey")
    await _use(client, cid, FEY, params={"mode": mode})
    effect = (await client.get(f"/characters/{cid}/target-effects/{FEY}")).json()["result"]
    assert effect["condition"] == mode and effect["save_ability"] == "wisdom"
    assert effect["ends_at"] == {"anchor": "source", "edge": "end", "count": 1}


async def test_fey_presence_state_lasts_until_the_end_of_the_next_turn_out_of_an_encounter(client):
    cid = await _patron(client, 1, "archfey")
    await _use(client, cid, FEY, params={"mode": "charmed"})
    await _new_turn(client, cid)  # comincia il turno dopo: la presenza c'è ancora
    assert "fey_presence" in _states(await _full(client, cid))
    await _new_turn(client, cid)
    assert "fey_presence" not in _states(await _full(client, cid))


async def test_misty_escape_is_a_reaction_that_makes_me_invisible_until_my_next_turn_or_an_attack(client):
    cid = await _patron(client, 6, "archfey")
    r = await _use(client, cid, MISTY)
    assert r.status_code == 200, r.text
    full = await _full(client, cid)
    assert full["conditions"]["invisible"] is True and (await _turn(client, cid))["reaction_used"] is True
    assert (await _ability(client, cid, MISTY))["uses"] == 0
    await _new_turn(client, cid)
    assert not (await _full(client, cid))["conditions"].get("invisible")
    await _rest(client, cid, "short")
    await _use(client, cid, MISTY)
    await _new_turn(client, cid)  # (la reazione si ricarica col turno)
    assert not (await _full(client, cid))["conditions"].get("invisible")


async def test_misty_escape_ends_when_i_attack(client):
    cid = await _patron(client, 6, "archfey")
    sword = await _weapon(client, cid, "Spada", "main_hand", damage_dice="1d8")
    await _use(client, cid, MISTY)
    await _hit(client, cid, sword)
    assert not (await _full(client, cid))["conditions"].get("invisible")


async def test_beguiling_defenses_make_me_immune_to_charm_and_let_me_turn_it_back(client):
    low, cid = await _patron(client, 9, "archfey"), await _patron(client, 10, "archfey", charisma=18)
    r = await client.patch(f"/characters/{low}/conditions", json={"conditions": {"charmed": True}})
    assert r.json()["conditions"].get("charmed") is True
    r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"charmed": True, "prone": True}})
    assert r.json()["conditions"].get("charmed") is None and r.json()["conditions"]["prone"] is True
    r = await _use(client, cid, DEFENSES)
    assert r.status_code == 200, r.text
    effect = (await client.get(f"/characters/{cid}/target-effects/{DEFENSES}")).json()["result"]
    assert effect["condition"] == "charmed" and effect["save_ability"] == "wisdom" and effect["save_dc"] == 8 + 4 + 4 and effect["rounds"] == 10
    assert (await _turn(client, cid))["reaction_used"] is True
    assert (await _ability(client, cid, DEFENSES))["max_uses"] is None  # nessun limite di usi


async def test_dark_delirium_charms_or_frightens_for_a_minute_while_i_concentrate(client):
    cid = await _patron(client, 14, "archfey", charisma=18)
    r = await _use(client, cid, DELIRIUM, params={"mode": "frightened"})
    assert r.status_code == 200, r.text
    full = await _full(client, cid)
    state = _states(full)["dark_delirium"]
    assert state["rounds_left"] == 10 and state["data"]["dc"] == 8 + 5 + 4 and (await _turn(client, cid))["action_used"] is True
    assert "concentration_rounds_left" in full["settings"]
    effect = (await client.get(f"/characters/{cid}/target-effects/{DELIRIUM}")).json()["result"]
    assert effect["condition"] == "frightened" and effect["rounds"] == 10 and effect["save_ability"] == "wisdom"
    assert (await _use(client, cid, DELIRIUM, params={"mode": "charmed"})).status_code == 409
    await client.patch(f"/characters/{cid}/concentration", json={"spell_id": None})
    assert "dark_delirium" not in _states(await _full(client, cid))
    await _rest(client, cid, "short")
    assert (await _ability(client, cid, DELIRIUM))["uses"] == 1


# ---------------------------------------------------------------------------
# L'Immondo
# ---------------------------------------------------------------------------

async def _blessing_hit(client, cid, sword, *options) -> dict:
    hit = await _hit(client, cid, sword)
    r = await client.post(f"/characters/{cid}/attack/{hit['attack_id']}/damage", json={"options": list(options)})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.parametrize("level,charisma,expected", [(1, 16, 4), (5, 16, 8), (10, 8, 9), (1, 1, 1), (2, 2, 1)])
async def test_dark_ones_blessing_gives_charisma_plus_level_temporary_hit_points_and_at_least_one(client, level, charisma, expected):
    cid = await _patron(client, level, "fiend", charisma=charisma)
    sword = await _weapon(client, cid, "Spada", "main_hand", damage_dice="1d8")
    assert BLESSING in await _keys(client, cid, "attack", item_id=sword)
    expected = max(1, (charisma - 10) // 2 + level)
    block = (await _blessing_hit(client, cid, sword, BLESSING))["option_result"]
    assert str(expected) in block["effects"][0]["it"]
    assert (await _full(client, cid))["temp_hp"] == expected


async def test_dark_ones_blessing_does_not_stack_with_the_temporary_points_I_have(client):
    cid = await _patron(client, 3, "fiend", charisma=14)
    sword = await _weapon(client, cid, "Spada", "main_hand", damage_dice="1d8")
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_temp", "value": 20})
    await _blessing_hit(client, cid, sword, BLESSING)
    assert (await _full(client, cid))["temp_hp"] == 20
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_temp", "value": 2})
    await _blessing_hit(client, cid, sword, BLESSING)
    assert (await _full(client, cid))["temp_hp"] == 5  # Carisma +2 e livello 3: il maggiore fra 2 e 5


async def test_dark_ones_blessing_is_not_taken_unless_I_confirm_it(client):
    cid = await _patron(client, 3, "fiend")
    sword = await _weapon(client, cid, "Spada", "main_hand", damage_dice="1d8")
    await _blessing_hit(client, cid, sword)
    assert (await _full(client, cid))["temp_hp"] == 0


async def test_dark_ones_blessing_also_applies_to_the_damage_of_a_spell(client):
    cid = await _patron(client, 4, "fiend", charisma=16)
    spell = await _spell(client, cid, "Fiammata", 0, attack_save="DEX", damage_dice="1d8", damage_type="fire")
    assert "warlock.dark_ones_blessing_spell" in await _keys(client, cid, "spell_damage", spell_id=spell)
    r = await client.post(f"/characters/{cid}/spells/{spell}/roll_damage", json={"options": ["warlock.dark_ones_blessing_spell"], "main_rolls": [3]})
    assert r.status_code == 200, r.text
    assert (await _full(client, cid))["temp_hp"] == 3 + 4  # Carisma +3 e livello 4


async def test_dark_ones_own_luck_adds_1d10_to_a_check_or_save_after_the_roll_once_per_rest(client):
    cid = await _patron(client, 6, "fiend")
    assert LUCK not in await _keys(client, cid, "attack")
    first = (await client.post(f"/characters/{cid}/saving_throws/wisdom/roll", json={"die": 5})).json()
    options = (await client.get(f"/characters/{cid}/roll-options", params={"roll": "save", "ability": "wisdom"})).json()
    assert next(o for o in options if o["key"] == LUCK)["phase"] == "after_roll"
    r = await client.post(f"/characters/{cid}/last-roll/options", json={"options": [LUCK]})
    assert r.status_code == 200, r.text
    extra = r.json()["option_result"]
    assert len(extra["extra_rolls"]) == 1 and 1 <= extra["extra_total"] <= 10
    assert r.json()["total"] == first["total"] + extra["extra_total"]
    assert (await _ability(client, cid, LUCK))["uses"] == 0
    assert LUCK not in await _keys(client, cid, "save", ability="wisdom")
    await _rest(client, cid, "short")
    assert LUCK in await _keys(client, cid, "skill", skill="athletics")


@pytest.mark.parametrize("damage", ["fire", "psychic", "bludgeoning"])
async def test_fiendish_resilience_gives_resistance_to_the_chosen_type_until_another_is_chosen(client, damage):
    cid = await _patron(client, 10, "fiend")
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": 100})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 100})
    assert (await _use(client, cid, RESILIENCE, params={"damage_type": "mud"})).status_code == 422
    r = await _use(client, cid, RESILIENCE, params={"damage_type": damage})
    assert r.status_code == 200, r.text
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 10, "damage_type": damage})
    assert r.json()["current_hit_points"] == 95
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 10, "damage_type": "acid"})
    assert r.json()["current_hit_points"] == 85
    assert (await _turn(client, cid))["action_used"] is False  # nessuna azione: si sceglie al riposo


async def test_fiendish_resilience_is_changed_at_a_rest_and_the_old_resistance_goes(client):
    cid = await _patron(client, 10, "fiend")
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": 100})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 100})
    await _use(client, cid, RESILIENCE, params={"damage_type": "fire"})
    r = await _use(client, cid, RESILIENCE, params={"damage_type": "cold"})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "already_chosen"  # una scelta per riposo
    await _rest(client, cid, "short")
    assert (await _use(client, cid, RESILIENCE, params={"damage_type": "cold"})).status_code == 200
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 10, "damage_type": "fire"})
    assert r.json()["current_hit_points"] == 90
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 10, "damage_type": "cold"})
    assert r.json()["current_hit_points"] == 85
    assert [s["key"] for s in (await _full(client, cid))["active_states"] if s["key"] == "fiendish_resilience"] == ["fiendish_resilience"]


async def test_the_resistance_choice_lock_is_hidden_internal_state(client):
    cid = await _patron(client, 10, "fiend")
    await _use(client, cid, RESILIENCE, params={"damage_type": "fire"})
    lock = _states(await _full(client, cid))["fiendish_resilience_lock"]
    assert lock["data"]["internal"] is True
    assert (await client.delete(f"/characters/{cid}/active-states/fiendish_resilience_lock")).status_code == 404


async def test_hurl_through_hell_adds_10d10_psychic_unless_the_target_is_a_fiend_and_spends_the_use(client):
    cid = await _patron(client, 14, "fiend")
    sword = await _weapon(client, cid, "Spada", "main_hand", damage_dice="1d8")
    keys = await _keys(client, cid, "attack", item_id=sword)
    assert HURL in keys and f"{HURL}_fiend" in keys
    block = (await _blessing_hit(client, cid, sword, HURL))["option_result"]
    assert "10d10" in block["effects"][0]["it"] and block["targets"] == [HURL]
    effect = (await client.get(f"/characters/{cid}/target-effects/{HURL}")).json()["result"]
    assert effect["condition"] == "custom:hurled" and effect["ends_at"] == {"anchor": "source", "edge": "end", "count": 1}
    assert (await _ability(client, cid, HURL))["uses"] == 0
    assert HURL not in await _keys(client, cid, "attack", item_id=sword)
    await _rest(client, cid, "long")
    assert (await _ability(client, cid, HURL))["uses"] == 1


async def test_hurl_through_hell_on_a_fiend_does_no_damage_and_cannot_be_taken_twice_at_once(client):
    cid = await _patron(client, 14, "fiend")
    sword = await _weapon(client, cid, "Spada", "main_hand", damage_dice="1d8")
    hit = await _hit(client, cid, sword)
    r = await client.post(f"/characters/{cid}/attack/{hit['attack_id']}/damage", json={"options": [HURL, f"{HURL}_fiend"]})
    assert r.status_code in (409, 422)  # stesso gruppo: una sola scelta per colpo
    r = await client.post(f"/characters/{cid}/attack/{hit['attack_id']}/damage", json={"options": [f"{HURL}_fiend"]})
    assert r.status_code == 200, r.text
    assert "Nessun danno" in r.json()["option_result"]["effects"][0]["it"]


# ---------------------------------------------------------------------------
# Il Grande Antico
# ---------------------------------------------------------------------------

async def test_entropic_ward_is_a_reaction_and_gives_advantage_on_the_next_attack_only_if_the_attack_missed(client):
    cid = await _patron(client, 6, "great_old_one")
    sword = await _weapon(client, cid, "Spada", "main_hand", damage_dice="1d8")
    assert "warlock.entropic_ward_advantage" not in await _keys(client, cid, "attack", item_id=sword)
    r = await _use(client, cid, WARD, params={"missed": True})
    assert r.status_code == 200, r.text
    assert (await _turn(client, cid))["reaction_used"] is True and (await _ability(client, cid, WARD))["uses"] == 0
    assert "warlock.entropic_ward_advantage" in await _keys(client, cid, "attack", item_id=sword)
    effect = (await client.get(f"/characters/{cid}/target-effects/{WARD}")).json()["result"]
    assert effect["condition"] == "custom:entropic_ward"
    r = await client.post(f"/characters/{cid}/items/{sword}/attack", json={"die": 10, "confirm_extra_attack": True, "options": ["warlock.entropic_ward_advantage"]})
    assert r.status_code == 200, r.text
    assert r.json()["mode_applied"] == "advantage"
    assert "warlock.entropic_ward_advantage" not in await _keys(client, cid, "attack", item_id=sword)  # usato


async def test_entropic_ward_gives_nothing_when_the_attack_hit(client):
    cid = await _patron(client, 6, "great_old_one")
    sword = await _weapon(client, cid, "Spada", "main_hand", damage_dice="1d8")
    await _use(client, cid, WARD, params={"missed": False})
    assert "warlock.entropic_ward_advantage" not in await _keys(client, cid, "attack", item_id=sword)


async def test_entropic_ward_advantage_lasts_until_the_end_of_my_next_turn(client):
    cid = await _patron(client, 6, "great_old_one")
    sword = await _weapon(client, cid, "Spada", "main_hand", damage_dice="1d8")
    await _use(client, cid, WARD, params={"missed": True})
    await _new_turn(client, cid)
    assert "warlock.entropic_ward_advantage" in await _keys(client, cid, "attack", item_id=sword)
    await _new_turn(client, cid)
    assert "warlock.entropic_ward_advantage" not in await _keys(client, cid, "attack", item_id=sword)


async def test_thought_shield_gives_resistance_to_psychic_damage_and_names_the_reflected_amount(client):
    low, cid = await _patron(client, 9, "great_old_one"), await _patron(client, 10, "great_old_one")
    for who in (low, cid):
        await client.patch(f"/characters/{who}/hp", json={"op": "set_max", "value": 100})
        await client.patch(f"/characters/{who}/hp", json={"op": "set_current", "value": 100})
    assert (await client.patch(f"/characters/{low}/hp", json={"op": "damage", "value": 10, "damage_type": "psychic"})).json()["current_hit_points"] == 90
    assert (await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 10, "damage_type": "psychic"})).json()["current_hit_points"] == 95
    options = (await client.get(f"/characters/{cid}/roll-options", params={"roll": "damage_taken", "damage_type": "psychic", "damage": 10})).json()
    assert SHIELD + "_reflection" in [o["key"] for o in options]
    options = (await client.get(f"/characters/{cid}/roll-options", params={"roll": "damage_taken", "damage_type": "fire"})).json()
    assert SHIELD + "_reflection" not in [o["key"] for o in options]


async def test_create_thrall_charms_an_incapacitated_humanoid_and_a_new_use_replaces_the_thrall(client):
    cid = await _patron(client, 14, "great_old_one")
    r = await _use(client, cid, THRALL)
    assert r.status_code == 200, r.text
    assert (await _turn(client, cid))["action_used"] is True and r.json()["targets"] == [THRALL]
    effect = (await client.get(f"/characters/{cid}/target-effects/{THRALL}")).json()["result"]
    assert effect["condition"] == "charmed" and not effect.get("save_ability") and not effect.get("rounds")
    first = _states(await _full(client, cid))["create_thrall"]
    await _new_turn(client, cid)
    assert (await _use(client, cid, THRALL)).status_code == 200
    states = [s for s in (await _full(client, cid))["active_states"] if s["key"] == "create_thrall"]
    assert len(states) == 1 and first["rounds_left"] is None


# ---------------------------------------------------------------------------
# Arcanum Mistico
# ---------------------------------------------------------------------------

ARCANUM = [(11, 6), (13, 7), (15, 8), (17, 9)]


@pytest.mark.parametrize("level", [10, 11, 12, 13, 15, 16, 17, 20])
async def test_the_arcanum_choices_and_rows_follow_the_level(client, level):
    cid = await _warlock(client, level)
    full = await _full(client, cid)
    keys = await _keys_of(client, cid)
    for need, grade in ARCANUM:
        pending = _choice(full, f"arcanum_{grade}")
        assert (pending is not None) == (level >= need)
        assert (f"warlock.mystic_arcanum_{grade}" in keys) == (level >= need)
        if pending:
            assert pending["count"] == 1 and pending["spell_pick"] == {"free": True, "max_level": grade, "list": None, "exact": True}
            row = await _ability(client, cid, f"warlock.mystic_arcanum_{grade}")
            assert row["max_uses"] == 1 and row["restoration_type"] == "long_rest"


async def _arcanum(client, cid, grade=6, name="Cerchio della morte", **extra) -> int:
    pick = _choice(await _full(client, cid), f"arcanum_{grade}")
    r = await client.post(f"/characters/{cid}/spells", json={"name": name, "level": grade, "pick_id": pick["id"], "casting_time": "1 azione", **extra})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_the_arcanum_spell_must_have_exactly_the_level_of_the_grade(client):
    cid = await _warlock(client, 13)
    six = _choice(await _full(client, cid), "arcanum_6")["id"]
    for level in (5, 7):
        r = await client.post(f"/characters/{cid}/spells", json={"name": "Sbagliato", "level": level, "pick_id": six})
        assert r.status_code == 422 and r.json()["detail"]["code"] == "spell_pick_level"
    assert (await client.post(f"/characters/{cid}/spells", json={"name": "Giusto", "level": 6, "pick_id": six})).status_code == 201
    assert _choice(await _full(client, cid), "arcanum_6") is None and _choice(await _full(client, cid), "arcanum_7") is not None


async def test_an_arcanum_does_not_count_among_the_known_spells(client):
    cid = await _warlock(client, 11)
    await _arcanum(client, cid)
    assert (await _full(client, cid))["spellcasting"]["limits"][0]["known_count"] == 0


async def test_an_arcanum_is_cast_once_per_long_rest_without_a_slot_at_its_level(client):
    cid = await _warlock(client, 11)
    spell = await _arcanum(client, cid)
    found = next(s for s in (await client.get(f"/characters/{cid}/spells")).json() if s["id"] == spell)
    assert found["pact_cast"] == {"kind": "arcanum", "feature_key": "warlock.mystic_arcanum_6", "pact_only": False, "uses_left": 1}
    before = await _pact_slots(client, cid)
    r = await client.post(f"/characters/{cid}/spells/{spell}/use", json={"free_cast": True})
    assert r.status_code == 200, r.text
    assert await _pact_slots(client, cid) == before and (await _turn(client, cid))["action_used"] is True
    assert (await _ability(client, cid, "warlock.mystic_arcanum_6"))["uses"] == 0
    await _new_turn(client, cid)
    r = await client.post(f"/characters/{cid}/spells/{spell}/use", json={"free_cast": True})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_uses"
    await _rest(client, cid, "long")
    assert (await client.post(f"/characters/{cid}/spells/{spell}/use", json={"free_cast": True})).status_code == 200


async def test_a_short_rest_does_not_give_the_arcanum_back(client):
    cid = await _warlock(client, 11)
    spell = await _arcanum(client, cid)
    await client.post(f"/characters/{cid}/spells/{spell}/use", json={"free_cast": True})
    await _rest(client, cid, "short")
    assert (await _ability(client, cid, "warlock.mystic_arcanum_6"))["uses"] == 0


async def test_each_grade_has_its_own_use(client):
    cid = await _warlock(client, 13)
    six, seven = await _arcanum(client, cid, 6, "Cerchio della morte"), await _arcanum(client, cid, 7, "Dito della morte")
    assert (await client.post(f"/characters/{cid}/spells/{six}/use", json={"free_cast": True})).status_code == 200
    assert (await _ability(client, cid, "warlock.mystic_arcanum_7"))["uses"] == 1
    await _new_turn(client, cid)
    assert (await client.post(f"/characters/{cid}/spells/{seven}/use", json={"free_cast": True})).status_code == 200


async def test_a_level_6_spell_cannot_be_cast_without_a_slot_unless_it_is_the_arcanum(client):
    cid = await _warlock(client, 11)
    plain = await _spell(client, cid, "Disintegrazione", 6)
    assert (await client.post(f"/characters/{cid}/spells/{plain}/use", json={"free_cast": True})).status_code == 409
    assert (await client.post(f"/characters/{cid}/spells/{plain}/use", json={})).status_code == 400


async def test_the_arcanum_is_not_castable_when_the_character_has_lost_the_feature(client):
    cid = await _warlock(client, 11)
    spell = await _arcanum(client, cid)
    klass = (await _full(client, cid))["classes"][0]
    await client.patch(f"/characters/{cid}/classes/{klass['id']}", json={"level": 5})
    assert (await client.post(f"/characters/{cid}/spells/{spell}/use", json={"free_cast": True})).status_code == 409


async def test_two_casts_of_the_same_arcanum_at_once_spend_the_use_once(client):
    import asyncio
    cid = await _warlock(client, 11)
    spell = await _arcanum(client, cid)
    results = await asyncio.gather(*(client.post(f"/characters/{cid}/spells/{spell}/use", json={"free_cast": True}) for _ in range(2)))
    assert sorted(r.status_code for r in results) == [200, 409]
    assert (await _ability(client, cid, "warlock.mystic_arcanum_6"))["uses"] == 0


async def test_a_saved_character_declares_the_arcanum_it_already_has_on_the_sheet(client, test_session_factory):
    from core.db.models import Character
    cid = await _warlock(client, 11)
    arcanum = await _spell(client, cid, "Cerchio della morte", 6)  # scritto a mano, senza classe
    lower = await _spell(client, cid, "Palla di fuoco", 3)
    async with test_session_factory() as s:
        char = await s.get(Character, cid)
        char.pending_choices = [{**c, "retrofit": True} for c in char.pending_choices]
        await s.commit()
    pick = _choice(await _full(client, cid), "arcanum_6")
    assert [o["id"] for o in pick["spell_pick"]["owned"]] == [arcanum]  # solo del suo grado
    url = f"/characters/{cid}/choices/{pick['id']}/resolve"
    assert (await client.post(url, json={"kind": "class_option", "options": [str(lower)]})).status_code == 422
    assert (await client.post(url, json={"kind": "class_option", "options": [str(arcanum)]})).status_code == 200
    assert (await client.post(f"/characters/{cid}/spells/{arcanum}/use", json={"free_cast": True})).status_code == 200
