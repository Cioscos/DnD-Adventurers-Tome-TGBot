"""Decisione 3 (UX playtest 16/11): un incantesimo che fa danni nei turni dopo (Guardiani spirituali) ricorda il livello del
lancio, così i danni si ritirano senza spendere un altro slot."""
from __future__ import annotations


async def test_concentration_remembers_the_cast_level_and_rerolling_damage_spends_no_slot(client):
    cid = (await client.post("/characters", json={"name": "Chierica"})).json()["id"]
    r = await client.post(f"/characters/{cid}/spells", json={
        "name": "Guardiani spirituali", "level": 3, "is_concentration": True, "duration": "Concentrazione, fino a 10 minuti",
        "damage_dice": "3d8", "damage_type": "radiant", "higher_levels_dice": "1d8"})
    assert r.status_code == 201, r.text
    spell = r.json()["id"]
    assert (await client.post(f"/characters/{cid}/spell_slots", json={"level": 4, "total": 1})).status_code == 201
    r = await client.post(f"/characters/{cid}/spells/{spell}/use", json={"slot_level": 4, "choices": {"damage_type": "radiant"}})
    assert r.status_code == 200, r.text
    sheet = r.json()
    assert sheet["concentrating_spell_id"] == spell and sheet["settings"]["concentration_level"] == 4
    for _ in range(2):  # i turni dopo: stessi dadi del lancio al 4°, nessuno slot speso
        r = await client.post(f"/characters/{cid}/spells/{spell}/roll_damage", json={"casting_level": 4})
        assert r.status_code == 200, r.text
        assert len(r.json()["rolls"]) == 4
    full = (await client.get(f"/characters/{cid}")).json()
    assert [s["available"] for s in full["spell_slots"] if s["level"] == 4] == [0]
    assert (await client.patch(f"/characters/{cid}/concentration", json={"spell_id": None})).status_code in (200, 204)
    assert "concentration_level" not in ((await client.get(f"/characters/{cid}")).json()["settings"] or {})
