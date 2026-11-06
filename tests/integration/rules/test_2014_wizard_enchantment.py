"""Scuola di Ammaliamento 2014 (Task 30): Sguardo Ipnotico, Fascino Istintivo, Ammaliamento Condiviso, Alterare Ricordi."""
from __future__ import annotations

import pytest

from tests.integration.rules.test_2014_bard import _ability, _full, _roll_keys, _use
from tests.integration.rules.test_2014_fighter_eldritch_knight import _cast, _spell
from tests.integration.rules.test_2014_wizard import _wizard

GAZE, CHARM, SPLIT, MEMORIES = "wizard.hypnotic_gaze", "wizard.instinctive_charm", "wizard.split_enchantment", "wizard.alter_memories"


async def _turn(client, cid) -> dict:
    return (await client.get(f"/characters/{cid}/turn-state")).json()["turn"]


async def _effect(client, cid, key) -> dict:
    return (await client.get(f"/characters/{cid}/target-effects/{key}")).json()["result"]


async def _enchantment(client, cid, name="Charme su persone", level=1, **extra) -> int:
    return await _spell(client, cid, name, level, school="enchantment", casting_time="1 azione", attack_save="WIS", **extra)


# ---------------------------------------------------------------------------
# Sguardo Ipnotico
# ---------------------------------------------------------------------------

async def test_hypnotic_gaze_is_an_action_for_the_enchanter_from_level_2(client):
    assert await _ability(client, await _wizard(client, 1), GAZE) is None
    assert await _ability(client, await _wizard(client, 5, "evocation"), GAZE) is None
    cid = await _wizard(client, 2, "enchantment")
    assert (await _ability(client, cid, GAZE))["has_on_use"] is True
    r = await _use(client, cid, GAZE)
    assert r.status_code == 200, r.text
    assert (await _turn(client, cid))["action_used"] is True and r.json()["targets"] == [GAZE]
    assert (await _use(client, cid, GAZE)).status_code == 409  # l'azione è già spesa


async def test_hypnotic_gaze_charms_and_incapacitates_with_a_wisdom_save_against_the_spell_dc(client):
    cid = await _wizard(client, 6, "enchantment", intelligence=16)  # competenza +3, Int +3
    await _use(client, cid, GAZE)
    effect = await _effect(client, cid, GAZE)
    assert (effect["condition"], effect["save_ability"], effect["save_dc"]) == ("charmed", "wisdom", 8 + 3 + 3)
    assert effect["also"] == ["incapacitated"]
    assert effect["ends_at"] == {"anchor": "source", "edge": "end", "count": 1}  # fino alla fine del prossimo turno del mago
    assert effect["extends"] is True and effect["immune_on_success"] is True and effect["note"] == "hypnotic_gaze"


# ---------------------------------------------------------------------------
# Fascino Istintivo
# ---------------------------------------------------------------------------

async def test_instinctive_charm_is_a_reaction_from_level_6(client):
    assert await _ability(client, await _wizard(client, 5, "enchantment"), CHARM) is None
    cid = await _wizard(client, 6, "enchantment", intelligence=16)
    r = await _use(client, cid, CHARM)
    assert r.status_code == 200, r.text
    assert (await _turn(client, cid))["reaction_used"] is True
    effect = await _effect(client, cid, CHARM)
    assert (effect["condition"], effect["save_ability"], effect["save_dc"]) == ("custom:instinctive_charm", "wisdom", 14)
    assert effect["immune_on_success"] is True and effect["note"] == "instinctive_charm"
    assert (await _use(client, cid, CHARM)).status_code == 409  # una sola reazione


# ---------------------------------------------------------------------------
# Ammaliamento Condiviso
# ---------------------------------------------------------------------------

async def test_split_enchantment_is_offered_for_an_enchantment_of_first_level_or_more(client):
    cid = await _wizard(client, 10, "enchantment")
    charm = await _enchantment(client, cid)
    cantrip = await _enchantment(client, cid, "Amicizia", 0)
    fire = await _spell(client, cid, "Dardo di fuoco", 1, school="evocation", casting_time="1 azione")
    assert SPLIT in await _roll_keys(client, cid, "cast", spell_id=charm)
    assert SPLIT not in await _roll_keys(client, cid, "cast", spell_id=cantrip)
    assert SPLIT not in await _roll_keys(client, cid, "cast", spell_id=fire)


async def test_split_enchantment_costs_nothing_and_says_the_spell_has_a_second_target(client):
    cid = await _wizard(client, 10, "enchantment")
    charm = await _enchantment(client, cid)
    r = await client.post(f"/characters/{cid}/spells/{charm}/use", json={"slot_level": 1, "options": [SPLIT]})
    assert r.status_code == 200, r.text
    block = r.json()["option_result"]
    assert block["targets"] == [] and "seconda" in block["effects"][0]["it"] and "second" in block["effects"][0]["en"]


async def test_split_enchantment_needs_level_10(client):
    cid = await _wizard(client, 9, "enchantment")
    assert SPLIT not in await _roll_keys(client, cid, "cast", spell_id=await _enchantment(client, cid))


# ---------------------------------------------------------------------------
# Alterare Ricordi
# ---------------------------------------------------------------------------

async def test_alter_memories_needs_an_enchantment_cast_just_before(client):
    cid = await _wizard(client, 14, "enchantment")
    r = await _use(client, cid, MEMORIES)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "feature_unavailable"
    charm = await _enchantment(client, cid)
    assert (await _cast(client, cid, charm, slot_level=1)).status_code == 200
    assert (await _use(client, cid, MEMORIES)).status_code == 200


@pytest.mark.parametrize("charisma,hours", [(8, 1), (10, 1), (14, 3), (20, 6)])
async def test_alter_memories_forgets_one_hour_plus_charisma_at_least_one(client, charisma, hours):
    cid = await _wizard(client, 14, "enchantment", intelligence=16, charisma=charisma)
    await _cast(client, cid, await _enchantment(client, cid), slot_level=1)
    r = await _use(client, cid, MEMORIES)
    assert r.status_code == 200, r.text
    assert f" {hours} " in r.json()["message"]["it"] and f" {hours} " in r.json()["message"]["en"]
    effect = await _effect(client, cid, MEMORIES)
    assert (effect["condition"], effect["save_ability"], effect["save_dc"]) == ("custom:altered_memory", "intelligence", 8 + 5 + 3)
    assert (await _turn(client, cid))["action_used"] is True


async def test_alter_memories_works_once_per_spell(client):
    cid = await _wizard(client, 14, "enchantment")
    await _cast(client, cid, await _enchantment(client, cid), slot_level=1)
    assert (await _use(client, cid, MEMORIES)).status_code == 200
    await client.post(f"/characters/{cid}/turn/new")
    again = await _use(client, cid, MEMORIES)
    assert again.status_code == 409 and again.json()["detail"]["code"] == "feature_unavailable"


async def test_another_spell_closes_the_alter_memories_window(client):
    cid = await _wizard(client, 14, "enchantment")
    await _cast(client, cid, await _enchantment(client, cid), slot_level=1)
    other = await _spell(client, cid, "Dardo incantato", 1, school="evocation", casting_time="1 azione")
    await client.post(f"/characters/{cid}/turn/new")
    await _cast(client, cid, other, slot_level=1)
    assert (await _use(client, cid, MEMORIES)).status_code == 409


async def test_a_cantrip_does_not_open_the_alter_memories_window(client):
    cid = await _wizard(client, 14, "enchantment")
    await _cast(client, cid, await _enchantment(client, cid, "Amicizia", 0))
    assert (await _use(client, cid, MEMORIES)).status_code == 409


async def test_alter_memories_is_for_the_enchanter_only(client):
    assert await _ability(client, await _wizard(client, 14, "illusion"), MEMORIES) is None
    assert await _ability(client, await _wizard(client, 13, "enchantment"), MEMORIES) is None
