"""Anteprima del riposo: deve coincidere con quello che /rest poi cambia."""
from __future__ import annotations

import random

from tests.integration.test_item_charges import _ch, _cur
from tests.integration.test_magic_items import _char, _item


async def _setup(client):
    cid = await _char(client)
    cls = (await client.get(f"/characters/{cid}")).json()["classes"][0]["id"]
    for sl in (await client.get(f"/characters/{cid}")).json()["spell_slots"]:
        used = {1: 3, 2: 1}.get(sl["level"], 0)
        await client.patch(f"/characters/{cid}/spell_slots/{sl['id']}", json={"used": used})
    await client.post(f"/characters/{cid}/spell_slots", json={"level": 3, "total": 2, "used": 1, "is_pact": True})
    await client.post(f"/characters/{cid}/abilities", json={
        "name": "Recupero", "max_uses": 2, "uses": 0, "restoration_type": "long_rest"})
    await client.post(f"/characters/{cid}/abilities", json={
        "name": "Fiato", "max_uses": 1, "uses": 0, "restoration_type": "short_rest"})
    await client.post(f"/characters/{cid}/abilities", json={
        "name": "Pieno", "max_uses": 1, "uses": 1, "restoration_type": "long_rest"})
    await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"exhaustion": 2}})
    await _item(client, cid, name="Bacchetta", charges=_ch(cur=0, amount="1d6+1"))
    await _item(client, cid, name="Anello", charges=_ch(mx=3, cur=1, recharge="short_rest"))
    await client.post(f"/characters/{cid}/hit_dice/spend", json={"class_id": cls, "count": 3, "rolls": [1, 1, 1]})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 1})
    sp = (await client.post(f"/characters/{cid}/spells", json={
        "name": "Benedizione", "level": 1, "is_concentration": True})).json()["id"]
    await client.patch(f"/characters/{cid}/concentration", json={"spell_id": sp})
    return cid, cls


async def _snapshot(client, cid):
    char = (await client.get(f"/characters/{cid}")).json()
    hist = (await client.get(f"/characters/{cid}/history")).json()
    return char, (hist if isinstance(hist, list) else hist.get("items", []))


async def test_long_preview_matches_rest(client, monkeypatch):
    cid, cls = await _setup(client)
    before, hist_before = await _snapshot(client, cid)
    p = (await client.get(f"/characters/{cid}/rest/preview", params={"rest_type": "long"})).json()
    after_preview, hist_after = await _snapshot(client, cid)
    assert after_preview == before and len(hist_after) == len(hist_before)  # nessuna scrittura

    assert p["hp_gain"] == before["hit_points"] - 1
    assert p["hit_dice_regain"] == {str(cls): 2}  # 5 livelli -> meta' = 2, ne servono 3 spesi
    assert p["slots"] == {"1": 3, "2": 1}
    assert p["pact_slots"] == 1
    assert sorted(p["abilities"]) == ["Fiato", "Recupero"]
    assert p["exhaustion_change"] == -1
    assert p["ends_concentration"] is True
    assert any("Bacchetta" in s and "1d6+1" in s for s in p["item_charges"])
    assert any("Anello" in s for s in p["item_charges"])

    monkeypatch.setattr(random, "randint", lambda a, b: 4)
    r = (await client.post(f"/characters/{cid}/rest", json={"rest_type": "long"})).json()
    assert r["current_hit_points"] == 1 + p["hp_gain"]
    assert r["classes"][0]["hit_dice_used"] == 3 - p["hit_dice_regain"][str(cls)]
    assert all(s["used"] == 0 for s in r["spell_slots"])
    assert all(a["uses"] == a["max_uses"] for a in r["abilities"])
    assert r["conditions"]["exhaustion"] == 2 + p["exhaustion_change"]
    assert r["concentrating_spell_id"] is None


async def test_short_preview_matches_rest(client):
    cid, _ = await _setup(client)
    before, _h = await _snapshot(client, cid)
    p = (await client.get(f"/characters/{cid}/rest/preview", params={"rest_type": "short"})).json()
    assert (await _snapshot(client, cid))[0] == before
    assert p["hp_gain"] == 0 and p["hit_dice_regain"] == {} and p["slots"] == {}
    assert p["pact_slots"] == 1 and p["abilities"] == ["Fiato"]
    assert p["exhaustion_change"] == 0 and p["ends_concentration"] is True
    assert len(p["item_charges"]) == 1 and "Anello" in p["item_charges"][0]

    r = (await client.post(f"/characters/{cid}/rest", json={"rest_type": "short"})).json()
    pact = next(s for s in r["spell_slots"] if s["is_pact"])
    assert pact["used"] == 0
    assert next(s for s in r["spell_slots"] if s["level"] == 1 and not s["is_pact"])["used"] == 3
    assert next(a for a in r["abilities"] if a["name"] == "Fiato")["uses"] == 1
    assert next(a for a in r["abilities"] if a["name"] == "Recupero")["uses"] == 0
    assert r["conditions"]["exhaustion"] == 2


async def test_preview_dead_character_recovers_nothing(client):
    cid, _ = await _setup(client)
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 0})
    await _kill(client, cid)
    assert (await client.get(f"/characters/{cid}")).json()["is_dead"] is True
    p = (await client.get(f"/characters/{cid}/rest/preview", params={"rest_type": "long"})).json()
    assert p["hp_gain"] == 0 and p["slots"] == {} and p["abilities"] == []
    assert p["exhaustion_change"] == 0 and p["ends_concentration"] is False


async def _kill(client, cid):
    for _ in range(3):
        await client.patch(f"/characters/{cid}/death_saves", json={"action": "failure"})


async def test_preview_validates_and_checks_ownership(client):
    cid = await _char(client)
    assert (await client.get(f"/characters/{cid}/rest/preview", params={"rest_type": "x"})).status_code in (400, 422)
    assert (await client.get("/characters/99999/rest/preview", params={"rest_type": "long"})).status_code == 404
