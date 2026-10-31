"""Cariche degli oggetti con ricarica e incantesimi lanciati dagli oggetti."""
from __future__ import annotations

import random

from tests.integration.test_magic_items import _char, _item


def _ch(mx=7, cur=7, recharge="dawn", amount="all"):
    return {"max": mx, "current": cur, "recharge": recharge, "recharge_amount": amount}


async def _cur(client, cid, iid):
    import json
    items = (await client.get(f"/characters/{cid}/items")).json()
    meta = next(i for i in items if i["id"] == iid)["item_metadata"]
    return (json.loads(meta) if isinstance(meta, str) else meta)["charges"]["current"]


async def test_charges_delta_clamped(client):
    cid = await _char(client)
    iid = await _item(client, cid, charges=_ch(mx=5, cur=3))
    assert (await client.post(f"/characters/{cid}/items/{iid}/charges", json={"delta": 50})).status_code == 200
    assert await _cur(client, cid, iid) == 5
    await client.post(f"/characters/{cid}/items/{iid}/charges", json={"delta": -9})
    assert await _cur(client, cid, iid) == 0


async def test_long_rest_recharges_dawn_dice(client, monkeypatch):
    cid = await _char(client)
    iid = await _item(client, cid, charges=_ch(cur=0, amount="1d6+1"))
    monkeypatch.setattr(random, "randint", lambda a, b: 4)
    r = await client.post(f"/characters/{cid}/rest", json={"rest_type": "long"})
    assert r.status_code == 200, r.text
    assert await _cur(client, cid, iid) == 5
    hist = (await client.get(f"/characters/{cid}/history")).json()
    assert any("Cariche ricaricate" in h["description"] for h in (hist if isinstance(hist, list) else hist.get("items", [])))


async def test_dice_recharge_clamped_to_max(client, monkeypatch):
    cid = await _char(client)
    iid = await _item(client, cid, charges=_ch(mx=3, cur=2, amount="1d6+1"))
    monkeypatch.setattr(random, "randint", lambda a, b: 6)
    await client.post(f"/characters/{cid}/rest", json={"rest_type": "long"})
    assert await _cur(client, cid, iid) == 3


async def test_short_rest_only_short(client):
    cid = await _char(client)
    d = await _item(client, cid, name="Alba", charges=_ch(cur=0, recharge="dawn"))
    s = await _item(client, cid, name="Breve", charges=_ch(cur=0, recharge="short_rest"))
    await client.post(f"/characters/{cid}/rest", json={"rest_type": "short"})
    assert await _cur(client, cid, d) == 0
    assert await _cur(client, cid, s) == 7


async def test_long_rest_also_recharges_short_rest_charges(client):
    cid = await _char(client)
    s = await _item(client, cid, name="Breve", charges=_ch(cur=0, recharge="short_rest"))
    n = await _item(client, cid, name="Mai", charges=_ch(cur=0, recharge="none"))
    await client.post(f"/characters/{cid}/rest", json={"rest_type": "long"})
    assert await _cur(client, cid, s) == 7
    assert await _cur(client, cid, n) == 0


BOLT = {"name": "Dardo Incantato", "level": 1, "charges_cost": 2}


async def test_cast_from_item_spends_charges_not_slots(client):
    cid = await _char(client)
    iid = await _item(client, cid, charges=_ch(cur=7), granted_spells=[BOLT])
    before = (await client.get(f"/characters/{cid}")).json()["spell_slots"]
    r = await client.post(f"/characters/{cid}/items/{iid}/cast", json={"spell_index": 0})
    assert r.status_code == 200, r.text
    assert await _cur(client, cid, iid) == 5
    assert r.json()["spell_slots"] == before


async def test_cast_requires_attunement(client):
    cid = await _char(client)
    iid = await _item(client, cid, requires_attunement=True, charges=_ch(), granted_spells=[BOLT])
    r = await client.post(f"/characters/{cid}/items/{iid}/cast", json={"spell_index": 0})
    assert r.status_code == 409 and r.json()["detail"] == "attunement_required"


async def test_cast_not_enough_charges_409(client):
    cid = await _char(client)
    iid = await _item(client, cid, charges=_ch(cur=1), granted_spells=[BOLT])
    r = await client.post(f"/characters/{cid}/items/{iid}/cast", json={"spell_index": 0})
    assert r.status_code == 409 and r.json()["detail"] == "not_enough_charges"
    assert await _cur(client, cid, iid) == 1


async def test_cast_concentration_from_item(client):
    cid = await _char(client)
    spell = {"name": "Foschia", "level": 1, "charges_cost": 1, "is_concentration": True,
             "duration": "Concentrazione, fino a 1 minuto"}
    iid = await _item(client, cid, charges=_ch(), granted_spells=[spell])
    r = await client.post(f"/characters/{cid}/items/{iid}/cast", json={"spell_index": 0})
    body = r.json()
    assert body["concentrating_spell_id"] is None
    assert body["settings"]["concentration_item_spell"] == {"item_id": iid, "name": "Foschia"}
    assert body["settings"]["concentration_rounds_left"] == 10
    # Un incantesimo del personaggio sostituisce la concentrazione dell'oggetto.
    sp = (await client.post(f"/characters/{cid}/spells", json={
        "name": "Benedizione", "level": 1, "is_concentration": True})).json()["id"]
    r = await client.patch(f"/characters/{cid}/concentration", json={"spell_id": sp})
    assert "concentration_item_spell" not in r.json()["settings"]
    # ...e matchare uno spell del personaggio per nome usa quello.
    spell2 = {"name": "benedizione", "level": 1, "charges_cost": 0, "is_concentration": True}
    iid2 = await _item(client, cid, name="Bacchetta", charges=_ch(), granted_spells=[spell2])
    r = await client.post(f"/characters/{cid}/items/{iid2}/cast", json={"spell_index": 0})
    assert r.json()["concentrating_spell_id"] == sp
