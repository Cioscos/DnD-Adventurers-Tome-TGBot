"""B14 (playtest 2026-11-16): il TS di concentrazione tirato dal danno accetta Normale / Vantaggio / Svantaggio."""
from __future__ import annotations


async def _concentrating(client) -> int:
    r = await client.post("/characters", json={"name": "Caster"})
    cid = r.json()["id"]
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": 40})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 40})
    spell = (await client.post(f"/characters/{cid}/spells", json={"name": "Benedizione", "level": 1, "is_concentration": True})).json()
    r = await client.patch(f"/characters/{cid}/concentration", json={"spell_id": spell["id"]})
    assert r.status_code == 200, r.text
    return cid


async def test_damage_concentration_save_takes_the_players_mode(client):
    cid = await _concentrating(client)
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 4, "concentration_mode": "disadvantage"})
    assert r.status_code == 200, r.text
    save = r.json()["concentration_save"]
    assert save["mode_applied"] == "disadvantage"
    assert len(save["dice"]) == 2


async def test_damage_concentration_save_is_normal_by_default(client):
    cid = await _concentrating(client)
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 4})
    assert r.json()["concentration_save"]["mode_applied"] == "normal"
