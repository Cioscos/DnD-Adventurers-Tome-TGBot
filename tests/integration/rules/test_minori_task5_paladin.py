"""Minori rinviati, Task 5 (punto 23): Paladino."""
from __future__ import annotations

from tests.integration.rules.test_2014_bard import _ability, _roll_keys, _use
from tests.integration.rules.test_2014_paladin import LOH, _paladin
from tests.integration.rules.test_2014_paladin_round1_loh import _cure, _pool
from tests.integration.rules.test_2024_paladin import _paladin24


async def test_paladin_23_cure_of_an_absent_condition_costs_nothing_2014(client):
    cid = await _paladin(client, 5)
    r = await _use(client, cid, LOH, amount=1, params=_cure(["self"], ["poisoned"]))
    assert r.status_code == 409 and r.json()["detail"]["code"] == "nothing_to_remove"
    assert await _pool(client, cid) == 25


async def test_paladin_23_cure_of_an_absent_condition_costs_nothing_2024(client):
    cid = await _paladin24(client, 5)
    r = await _use(client, cid, LOH, amount=1, params=_cure(["self"], ["poisoned"]))
    assert r.status_code == 409 and r.json()["detail"]["code"] == "nothing_to_remove"
    assert await _pool(client, cid) == 25


async def test_paladin_23_only_the_present_conditions_are_paid(client):
    cid = await _paladin24(client, 14)
    await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"blinded": True}})
    r = await _use(client, cid, LOH, amount=1, params=_cure(["self"], ["blinded", "stunned"]))
    assert r.status_code == 200, r.text
    assert await _pool(client, cid) == 65


async def test_paladin_23_glorious_defense_strike_is_part_of_the_reaction_not_of_the_attack_action(client):
    from tests.integration.rules.test_2024_paladin_oaths import GD, _oath, _sword
    from tests.integration.rules.test_2014_paladin import _turn
    cid = await _oath(client, 15, "glory", charisma=16)
    wid = await _sword(client, cid)
    key = "paladin.glorious_defense_strike"
    assert key not in await _roll_keys(client, cid, "attack")
    assert (await _use(client, cid, GD)).status_code == 200
    assert key in await _roll_keys(client, cid, "attack")
    r = await client.post(f"/characters/{cid}/items/{wid}/attack", json={"die": 15, "options": [key]})
    assert r.status_code == 200, r.text
    assert (await _turn(client, cid))["action_attacks"] == 0
    assert key not in await _roll_keys(client, cid, "attack")  # una sola volta per reazione


async def test_paladin_23_faithful_steed_is_an_action_not_hidden_under_other(client):
    cid = await _paladin24(client, 5)
    assert (await _ability(client, cid, "paladin.faithful_steed"))["action_type"] == "action"


async def test_paladin_23_find_steed_cast_with_a_slot_creates_the_steed_at_the_slot_level(client):
    cid = await _paladin24(client, 9)  # slot di 3° livello
    spells = {s["srd_index"]: s for s in (await client.get(f"/characters/{cid}/spells")).json()}
    r = await client.post(f"/characters/{cid}/spells/{spells['find-steed']['id']}/use", json={"slot_level": 3, "confirm": []})
    assert r.status_code == 200, r.text
    [steed] = [c for c in (await client.get(f"/characters/{cid}/companions")).json() if c["feature_key"] == "paladin.faithful_steed"]
    assert (steed["armor_class"], steed["max_hp"]) == (13, 35)
    # l'uso gratuito del privilegio non si spende
    assert (await _ability(client, cid, "paladin.faithful_steed"))["uses"] == 1
