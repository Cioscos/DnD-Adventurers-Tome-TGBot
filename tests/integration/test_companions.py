from __future__ import annotations

from core.db.models import Character
from tests.integration.conftest import TEST_USER_ID

STATBLOCK = {
    "size": "Small", "type": "beast", "hit_points": 10,
    "actions": [
        {"name": "Bite", "attack_bonus": 4, "damage_dice": "1d6+2", "damage_type": "piercing"},
        {"name": "Howl"},
    ],
}


async def _char(factory, user_id=TEST_USER_ID) -> int:
    async with factory() as s:
        c = Character(user_id=user_id, name="Owner")
        s.add(c)
        await s.commit()
        return c.id


def _body(**kw):
    return {"kind": "familiar", "name": "Owl", "statblock": STATBLOCK,
            "max_hp": 10, "current_hp": 10, "armor_class": 12, **kw}


async def _add(client, cid, **kw):
    r = await client.post(f"/characters/{cid}/companions", json=_body(**kw))
    assert r.status_code == 201, r.text
    return r.json()


async def test_crud(client, test_session_factory):
    cid = await _char(test_session_factory)
    c = await _add(client, cid)
    assert c["name"] == "Owl" and c["is_active"] is False and c["created_at"]
    assert len((await client.get(f"/characters/{cid}/companions")).json()) == 1
    r = await client.patch(f"/characters/{cid}/companions/{c['id']}", json={"name": "Hawk", "notes": "x"})
    assert r.json()["name"] == "Hawk" and r.json()["notes"] == "x"
    assert (await client.delete(f"/characters/{cid}/companions/{c['id']}")).status_code == 204
    assert (await client.get(f"/characters/{cid}/companions")).json() == []


async def test_ownership_403_and_404(client, test_session_factory):
    other = await _char(test_session_factory, user_id=999)
    mine = await _char(test_session_factory)
    assert (await client.get(f"/characters/{other}/companions")).status_code == 403
    assert (await client.post(f"/characters/{other}/companions", json=_body())).status_code == 403
    assert (await client.get("/characters/9999/companions")).status_code == 404
    # companion of another character is not reachable through mine
    async with test_session_factory() as s:
        from core.db.models import Companion
        comp = Companion(character_id=other, kind="mount", name="Horse", created_at="x")
        s.add(comp)
        await s.commit()
        cid = comp.id
    assert (await client.patch(f"/characters/{mine}/companions/{cid}", json={"name": "x"})).status_code == 404
    assert (await client.delete(f"/characters/{mine}/companions/{cid}")).status_code == 404


async def test_hp_damage_temp_first_and_floor(client, test_session_factory):
    cid = await _char(test_session_factory)
    c = await _add(client, cid)
    url = f"/characters/{cid}/companions/{c['id']}/hp"
    assert (await client.patch(url, json={"op": "set_temp", "value": 3})).json()["temp_hp"] == 3
    r = (await client.patch(url, json={"op": "damage", "value": 5})).json()
    assert r["temp_hp"] == 0 and r["current_hp"] == 8 and r["down"] is False
    r = (await client.patch(url, json={"op": "damage", "value": 99})).json()
    assert r["current_hp"] == 0 and r["down"] is True
    r = (await client.patch(url, json={"op": "heal", "value": 99})).json()
    assert r["current_hp"] == 10 and r["down"] is False
    assert (await client.patch(url, json={"op": "damage", "value": -1})).status_code == 422


async def test_attack_advantage_uses_kept_die(client, test_session_factory):
    cid = await _char(test_session_factory)
    c = await _add(client, cid)
    url = f"/characters/{cid}/companions/{c['id']}/attack"
    r = await client.post(url, json={"action_index": 0, "mode": "advantage", "dice": [5, 17], "damage_rolls": [4]})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["to_hit_die"] == 17 and d["to_hit_bonus"] == 4 and d["to_hit_total"] == 21
    assert d["is_critical"] is False and d["damage_total"] == 6 and d["damage_type"] == "piercing"
    r = await client.post(url, json={"action_index": 0, "mode": "normal", "dice": [20], "damage_rolls": [4, 6]})
    assert r.json()["is_critical"] is True and r.json()["damage_total"] == 12
    hist = (await client.get(f"/characters/{cid}/history")).json()
    assert any("Owl" in str(h) for h in hist)


async def test_attack_validation(client, test_session_factory):
    cid = await _char(test_session_factory)
    c = await _add(client, cid)
    url = f"/characters/{cid}/companions/{c['id']}/attack"
    assert (await client.post(url, json={"action_index": 1})).status_code == 422  # no attack_bonus
    assert (await client.post(url, json={"action_index": 5})).status_code == 422
    assert (await client.post(url, json={"action_index": 0, "dice": [10], "damage_rolls": [9]})).status_code == 422
    assert (await client.post(url, json={"action_index": 0, "dice": [10], "damage_rolls": [1, 1]})).status_code == 422


async def test_companion_limit_422(client, test_session_factory):
    cid = await _char(test_session_factory)
    for _ in range(30):
        await _add(client, cid)
    r = await client.post(f"/characters/{cid}/companions", json=_body())
    assert r.status_code == 422


async def test_is_active_only_wild_shape_and_single(client, test_session_factory):
    cid = await _char(test_session_factory)
    r = await client.post(f"/characters/{cid}/companions", json=_body(is_active=True))
    assert r.status_code == 422
    a = await _add(client, cid, kind="wild_shape", is_active=True)
    b = await _add(client, cid, kind="wild_shape", is_active=True)
    items = {c["id"]: c for c in (await client.get(f"/characters/{cid}/companions")).json()}
    assert items[a["id"]]["is_active"] is False and items[b["id"]]["is_active"] is True
    r = await client.patch(f"/characters/{cid}/companions/{a['id']}", json={"is_active": True})
    assert r.json()["is_active"] is True
    assert (await client.get(f"/characters/{cid}/companions")).json()[1]["is_active"] is False


async def test_statblock_validation(client, test_session_factory):
    cid = await _char(test_session_factory)
    for sb in ([], {"actions": "x"}, {"actions": [{"attack_bonus": "x"}]}, {"actions": [{"damage_dice": "lots"}]}):
        r = await client.post(f"/characters/{cid}/companions", json=_body(statblock=sb))
        assert r.status_code == 422, sb


async def test_export_import_roundtrip(client, test_session_factory):
    cid = await _char(test_session_factory)
    await _add(client, cid, notes="n", srd_index="owl")
    await _add(client, cid, kind="wild_shape", name="Bear", is_active=True)
    first = (await client.get(f"/characters/{cid}/export")).json()
    assert len(first["companions"]) == 2
    r = await client.post("/characters/import", json=first)
    assert r.status_code == 201, r.text
    new_id = r.json()["id"]
    got = (await client.get(f"/characters/{new_id}/companions")).json()
    assert [c["name"] for c in got] == ["Owl", "Bear"] and got[1]["is_active"] is True
    assert got[0]["statblock"] == STATBLOCK and got[0]["srd_index"] == "owl"
    second = (await client.get(f"/characters/{new_id}/export")).json()
    assert first["companions"] == second["companions"]


async def test_import_rejects_too_many_companions(client, test_session_factory):
    cid = await _char(test_session_factory)
    data = (await client.get(f"/characters/{cid}/export")).json()
    data["companions"] = [{"kind": "mount", "name": "H"}] * 31
    assert (await client.post("/characters/import", json=data)).status_code == 422
