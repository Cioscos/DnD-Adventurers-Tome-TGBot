"""Minori rinviati, Task 5 (punto 24): Ladro (Mistificatore Arcano e Coltello dell'Anima, 2024)."""
from __future__ import annotations

from tests.integration.rules.test_2014_fighter_battle_master import _fixed
from tests.integration.rules.test_2014_rogue import _damage, _hit, _rapier
from tests.integration.rules.test_2014_rogue_trickster import _with_hand
from tests.integration.rules.test_2014_bard import _roll_keys, _use
from tests.integration.rules.test_2014_paladin import _new_turn
from tests.integration.rules.test_2024_rogue_subclasses import SNEAK, _k, _sub

VERSATILE_TRIP = "rogue.versatile_trip"


async def test_rogue_24_versatile_trickster_gives_a_second_apply_for_the_second_creature(client):
    cid = await _sub(client, "arcane_trickster", 13, dexterity=16)
    await _with_hand(client, cid)
    wid = await _rapier(client, cid)
    await _new_turn(client, cid)
    hit = await _hit(client, cid, wid, mode="advantage", dice=[10, 12])
    resp = await _damage(client, cid, hit, SNEAK, _k("trip"), VERSATILE_TRIP)
    assert resp.status_code == 200, resp.text
    assert set(resp.json()["option_result"]["targets"]) >= {_k("trip"), VERSATILE_TRIP}
    # senza Sgambetto, o senza Mano Magica, non c'è
    hit = await _hit(client, cid, wid, mode="advantage", dice=[10, 12])
    assert (await _damage(client, cid, hit, SNEAK, VERSATILE_TRIP)).status_code == 409


async def test_rogue_24_versatile_trip_needs_mage_hand(client):
    cid = await _sub(client, "arcane_trickster", 13, dexterity=16)
    wid = await _rapier(client, cid)
    await _new_turn(client, cid)
    hit = await _hit(client, cid, wid, mode="advantage", dice=[10, 12])
    assert (await _damage(client, cid, hit, SNEAK, _k("trip"), VERSATILE_TRIP)).status_code == 409


async def test_rogue_24_psychic_teleportation_says_the_distance(client, monkeypatch):
    cid = await _sub(client, "soulknife", 9)
    _fixed(monkeypatch, 5)
    r = await _use(client, cid, _k("psychic_teleportation"))
    assert r.status_code == 200, r.text
    assert "15 m" in r.json()["message"]["it"] and "50 ft" in r.json()["message"]["en"]


async def test_rogue_24_psychic_blade_is_not_offered_to_a_companion_attack(client):
    cid = await _sub(client, "soulknife", 9)
    assert _k("psychic_blade") in await _roll_keys(client, cid, "attack")
    keys = await _roll_keys(client, cid, "attack", attack_mode="companion")
    assert _k("psychic_blade") not in keys and _k("homing_strikes") not in keys
