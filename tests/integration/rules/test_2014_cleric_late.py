"""Chierico 2014 (Task 21): Intervento Divino, Collera Distruttiva, Colpo del Tuono e del Fulmine, Manto di Ombre,
Invocare Duplicato, Visioni del Passato e Nato dalla Tempesta."""
from __future__ import annotations

import pytest

from tests.integration.rules.test_2014_bard import _ability, _full, _keys_of, _roll_keys, _states, _use
from tests.integration.rules.test_2014_barbarian import _turn, _weapon
from tests.integration.rules.test_2014_cleric import POOL, _cleric

DI = "cleric.divine_intervention"


def _roll(monkeypatch, value: int) -> None:
    monkeypatch.setattr("api.services.rules_states.random.randint", lambda a, b: value)


# ---------------------------------------------------------------------------
# Intervento Divino
# ---------------------------------------------------------------------------

async def test_divine_intervention_success_blocks_the_feature_for_seven_days(client, monkeypatch):
    cid = await _cleric(client, 12)
    _roll(monkeypatch, 12)  # d100 <= livello da chierico
    r = await _use(client, cid, DI)
    assert r.status_code == 200, r.text
    assert r.json()["rolls"] == [12]
    state = r.json()["state"]
    assert state["data"] == {"roll": 12, "level": 12, "success": True} and state["ends_on"] == ["manual"]
    assert (await _turn(client, cid))["action_used"] is True
    await client.post(f"/characters/{cid}/turn/new")
    again = await _use(client, cid, DI)
    assert again.status_code == 409 and again.json()["detail"]["code"] == "feature_unavailable"
    await client.post(f"/characters/{cid}/rest", json={"rest_type": "long", "confirm_early": True})
    assert (await _use(client, cid, DI)).status_code == 409  # il blocco di 7 giorni regge al riposo lungo
    await client.delete(f"/characters/{cid}/active-states/divine_intervention")
    assert (await _use(client, cid, DI)).status_code == 200


async def test_divine_intervention_failure_comes_back_after_a_long_rest(client, monkeypatch):
    cid = await _cleric(client, 12)
    _roll(monkeypatch, 13)  # un punto sopra il livello
    state = (await _use(client, cid, DI)).json()["state"]
    assert state["data"]["success"] is False and set(state["ends_on"]) == {"rest_long", "manual"}
    assert (await _ability(client, cid, DI))["uses"] == 0
    await client.post(f"/characters/{cid}/rest", json={"rest_type": "long", "confirm_early": True})
    assert await _states(client, cid) == [] and (await _ability(client, cid, DI))["uses"] == 1


@pytest.mark.parametrize("rolled,success", [(1, True), (10, True), (11, False), (100, False)])
async def test_divine_intervention_compares_the_d100_with_the_level(client, monkeypatch, rolled, success):
    cid = await _cleric(client, 10)
    _roll(monkeypatch, rolled)
    assert (await _use(client, cid, DI)).json()["state"]["data"]["success"] is success


async def test_divine_intervention_at_level_20_always_works_without_rolling(client):
    cid = await _cleric(client, 20)
    r = await _use(client, cid, DI)
    assert r.status_code == 200 and r.json()["rolls"] == [] and r.json()["state"]["data"]["success"] is True


async def test_divine_intervention_appears_at_level_10(client):
    assert DI not in await _keys_of(client, await _cleric(client, 9))
    assert DI in await _keys_of(client, await _cleric(client, 10))


# ---------------------------------------------------------------------------
# Dominio della Tempesta
# ---------------------------------------------------------------------------

async def _spell(client, cid, name, damage_type, level=3, dice="8d6") -> int:
    r = await client.post(f"/characters/{cid}/spells", json={
        "name": name, "level": level, "damage_dice": dice, "damage_type": damage_type, "is_prepared": True})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_destructive_wrath_maximises_lightning_and_thunder_dice(client):
    cid = await _cleric(client, 2, "tempest")
    bolt = await _spell(client, cid, "Fulmine", "lightning", 1, "3d6")
    fire = await _spell(client, cid, "Palla di fuoco", "fire", 1, "3d6")
    assert "cleric.destructive_wrath" in await _roll_keys(client, cid, "spell_damage", spell_id=bolt)
    assert "cleric.destructive_wrath" not in await _roll_keys(client, cid, "spell_damage", spell_id=fire)
    r = await client.post(f"/characters/{cid}/spells/{bolt}/roll_damage", json={
        "main_rolls": [1, 2, 3], "options": ["cleric.destructive_wrath"]})
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 18 and r.json()["main_rolls"] == [6, 6, 6]
    assert (await _ability(client, cid, POOL))["uses"] == 0
    assert "cleric.destructive_wrath" not in await _roll_keys(client, cid, "spell_damage", spell_id=bolt)


async def test_destructive_wrath_does_not_touch_other_spells(client):
    cid = await _cleric(client, 2, "tempest")
    fire = await _spell(client, cid, "Palla di fuoco", "fire", 1, "3d6")
    r = await client.post(f"/characters/{cid}/spells/{fire}/roll_damage", json={
        "main_rolls": [1, 2, 3], "options": ["cleric.destructive_wrath"]})
    assert r.status_code == 409


async def test_thunderbolt_strike_shows_the_push_for_lightning_only(client):
    cid = await _cleric(client, 6, "tempest")
    bolt = await _spell(client, cid, "Fulmine", "lightning", 1, "3d6")
    thunder = await _spell(client, cid, "Frantumare", "thunder", 1, "3d6")
    assert "cleric.thunderbolt_strike" in await _roll_keys(client, cid, "spell_damage", spell_id=bolt)
    assert "cleric.thunderbolt_strike" not in await _roll_keys(client, cid, "spell_damage", spell_id=thunder)
    r = await client.post(f"/characters/{cid}/spells/{bolt}/roll_damage", json={
        "main_rolls": [1, 2, 3], "options": ["cleric.thunderbolt_strike"]})
    assert r.status_code == 200, r.text
    assert "3 m" in r.json()["option_result"]["effects"][0]["it"]
    low = await _cleric(client, 5, "tempest")
    assert "cleric.thunderbolt_strike" not in await _roll_keys(
        client, low, "spell_damage", spell_id=await _spell(client, low, "Fulmine", "lightning", 1, "3d6"))


async def test_stormborn_flies_unless_suspended_indoors(client):
    cid = await _cleric(client, 17, "tempest")
    full = await _full(client, cid)
    assert full["computed"]["fly_speed"] == full["computed"]["speed"]
    assert (await _cleric_fly(client, await _cleric(client, 16, "tempest"))) is None
    r = await _use(client, cid, "cleric.stormborn")
    assert r.status_code == 200 and r.json()["state"]["key"] == "stormborn_off"
    assert (await _full(client, cid))["computed"]["fly_speed"] is None
    assert (await _use(client, cid, "cleric.stormborn")).status_code == 409
    await client.delete(f"/characters/{cid}/active-states/stormborn_off")
    assert (await _full(client, cid))["computed"]["fly_speed"] is not None


async def _cleric_fly(client, cid):
    return (await _full(client, cid))["computed"]["fly_speed"]


# ---------------------------------------------------------------------------
# Dominio dell'Inganno
# ---------------------------------------------------------------------------

async def test_cloak_of_shadows_ends_when_you_attack(client):
    cid = await _cleric(client, 6, "trickery", strength=14)
    sword = await _weapon(client, cid, "Mazza", damage_dice="1d6")
    assert "cleric.cloak_attack" not in await _roll_keys(client, cid, "attack", item_id=sword)
    r = await _use(client, cid, "cleric.cloak_of_shadows")
    assert r.status_code == 200 and r.json()["state"]["rounds_left"] == 2
    assert (await _ability(client, cid, POOL))["uses"] == 1
    assert "cleric.cloak_attack" in await _roll_keys(client, cid, "attack", item_id=sword)
    hit = await client.post(f"/characters/{cid}/items/{sword}/attack", json={"die": 10, "options": ["cleric.cloak_attack"]})
    assert hit.status_code == 200, hit.text
    assert hit.json()["mode"] == "advantage"
    assert await _states(client, cid) == []


async def test_cloak_of_shadows_ends_when_you_cast(client):
    cid = await _cleric(client, 6, "trickery")
    await _use(client, cid, "cleric.cloak_of_shadows")
    spell = await _spell(client, cid, "Dardo", "force", 1, "1d4")
    assert "cleric.cloak_cast" in await _roll_keys(client, cid, "cast", spell_id=spell)
    r = await client.post(f"/characters/{cid}/spells/{spell}/use", json={"slot_level": 1, "options": ["cleric.cloak_cast"]})
    assert r.status_code == 200, r.text
    assert await _states(client, cid) == []


async def test_invoke_duplicity_needs_concentration_and_unlocks_the_bonus_move(client):
    cid = await _cleric(client, 2, "trickery")
    move = "cleric.invoke_duplicity_move"
    assert (await _use(client, cid, move)).status_code == 409
    r = await _use(client, cid, "cleric.invoke_duplicity")
    assert r.status_code == 200, r.text
    assert r.json()["state"]["rounds_left"] == 10 and r.json()["state"]["data"]["duplicates"] == 1
    full = await _full(client, cid)
    assert full["settings"]["concentration_item_spell"]["name"] == "Invocare Duplicato"
    await client.post(f"/characters/{cid}/turn/new")
    assert (await _use(client, cid, move)).status_code == 200 and (await _turn(client, cid))["bonus_used"] is True
    assert "cleric.duplicity_advantage" in await _roll_keys(client, cid, "attack")


async def test_losing_concentration_ends_the_duplicate(client):
    cid = await _cleric(client, 2, "trickery")
    await _use(client, cid, "cleric.invoke_duplicity")
    await client.patch(f"/characters/{cid}/concentration", json={"spell_id": None})
    assert await _states(client, cid) == []
    assert "cleric.duplicity_advantage" not in await _roll_keys(client, cid, "attack")


async def test_invoke_duplicity_gives_four_duplicates_from_level_17(client):
    cid = await _cleric(client, 17, "trickery")
    assert (await _use(client, cid, "cleric.invoke_duplicity")).json()["state"]["data"]["duplicates"] == 4


async def test_starting_a_second_concentration_ends_the_duplicate(client):
    cid = await _cleric(client, 3, "trickery")
    await _use(client, cid, "cleric.invoke_duplicity")
    spell = (await client.post(f"/characters/{cid}/spells", json={
        "name": "Benedizione", "level": 1, "is_concentration": True, "duration": "Concentrazione, fino a 1 minuto"})).json()["id"]
    await client.patch(f"/characters/{cid}/concentration", json={"spell_id": spell, "rounds": 10})
    assert await _states(client, cid) == []


# ---------------------------------------------------------------------------
# Dominio della Conoscenza
# ---------------------------------------------------------------------------

async def test_visions_of_the_past_lasts_wisdom_minutes_in_concentration(client):
    cid = await _cleric(client, 17, "knowledge", wisdom=18)
    key = "cleric.visions_of_the_past"
    assert (await _ability(client, cid, key))["max_uses"] == 1
    r = await _use(client, cid, key)
    assert r.status_code == 200, r.text
    assert r.json()["state"]["rounds_left"] == 18 * 10 and "concentration_end" in r.json()["state"]["ends_on"]
    assert (await _use(client, cid, key)).status_code == 409  # un solo uso
    await client.post(f"/characters/{cid}/rest", json={"rest_type": "short"})
    assert (await _ability(client, cid, key))["uses"] == 1


async def test_visions_of_the_past_ends_with_the_concentration(client):
    cid = await _cleric(client, 17, "knowledge")
    await _use(client, cid, "cleric.visions_of_the_past")
    await client.patch(f"/characters/{cid}/concentration", json={"spell_id": None})
    assert await _states(client, cid) == []


async def test_object_and_area_reading_are_text_only_rows(client):
    cid = await _cleric(client, 17, "knowledge")
    for key in ("cleric.object_reading", "cleric.area_reading"):
        row = await _ability(client, cid, key)
        assert row["is_passive"] is True and row["max_uses"] is None
