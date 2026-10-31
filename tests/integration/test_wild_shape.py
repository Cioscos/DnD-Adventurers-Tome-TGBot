from __future__ import annotations

from core.db.models import Ability
from tests.integration.test_hp_undo import _force_d20, _hp, _make_char, _start_concentration

STATBLOCK = {"size": "Medium", "type": "beast", "actions": []}


async def _druid_uses(factory, cid: int, uses: int) -> None:
    async with factory() as s:
        s.add(Ability(character_id=cid, name="Forma selvatica", feature_key="druid.wild_shape",
                      max_uses=2, uses=uses))
        await s.commit()


async def _uses(factory, cid: int) -> int:
    from sqlalchemy import select
    async with factory() as s:
        return (await s.execute(select(Ability.uses).where(Ability.character_id == cid))).scalar_one()


async def _form(client, cid, hp=10, **kw) -> dict:
    r = await client.post(f"/characters/{cid}/companions", json={
        "kind": "wild_shape", "name": "Orso", "statblock": STATBLOCK,
        "max_hp": hp, "current_hp": 1, "armor_class": 11, **kw})
    assert r.status_code == 201, r.text
    return r.json()


async def _activate(client, cid, comp_id, **body):
    return await client.post(f"/characters/{cid}/companions/{comp_id}/activate", json=body)


async def _comp(client, cid, comp_id) -> dict:
    return next(c for c in (await client.get(f"/characters/{cid}/companions")).json() if c["id"] == comp_id)


async def test_wild_shape_activation_spends_use(client, test_session_factory):
    cid = await _make_char(client)
    await _druid_uses(test_session_factory, cid, 2)
    f = await _form(client, cid, hp=10)
    r = await _activate(client, cid, f["id"])
    assert r.status_code == 200, r.text
    assert r.json()["is_active"] is True and r.json()["current_hp"] == 10  # full HP on activation
    assert await _uses(test_session_factory, cid) == 1
    full = (await client.get(f"/characters/{cid}")).json()
    assert full["active_form"] == {"companion_id": f["id"], "name": "Orso", "current_hp": 10,
                                   "max_hp": 10, "temp_hp": 0, "armor_class": 11}
    # activating another deactivates the previous one
    g = await _form(client, cid, hp=6)
    assert (await _activate(client, cid, g["id"])).status_code == 200
    assert (await _comp(client, cid, f["id"]))["is_active"] is False
    r = await client.post(f"/characters/{cid}/companions/{g['id']}/deactivate")
    assert r.status_code == 200 and r.json()["is_active"] is False
    assert (await client.get(f"/characters/{cid}")).json()["active_form"] is None


async def test_wild_shape_no_uses_409_force_ok(client, test_session_factory):
    cid = await _make_char(client)
    await _druid_uses(test_session_factory, cid, 0)
    f = await _form(client, cid)
    r = await _activate(client, cid, f["id"])
    assert r.status_code == 409 and r.json()["detail"] == "no_wild_shape_uses"
    assert (await _comp(client, cid, f["id"]))["is_active"] is False
    r = await _activate(client, cid, f["id"], force=True)
    assert r.status_code == 200 and r.json()["is_active"] is True
    assert await _uses(test_session_factory, cid) == 0


async def test_wild_shape_damage_absorbed_by_form(client):
    cid = await _make_char(client, 20)
    f = await _form(client, cid, hp=10, temp_hp=3)
    await _activate(client, cid, f["id"])
    await client.patch(f"/characters/{cid}/companions/{f['id']}", json={"temp_hp": 3})
    body = await _hp(client, cid, "damage", 6)
    assert body["current_hit_points"] == 20 and body["temp_hp"] == 0
    assert body["active_form"]["temp_hp"] == 0 and body["active_form"]["current_hp"] == 7


async def test_wild_shape_overflow_hits_character(client):
    cid = await _make_char(client, 20)
    await _hp(client, cid, "set_temp", 2)
    f = await _form(client, cid, hp=5)
    await _activate(client, cid, f["id"])
    body = await _hp(client, cid, "damage", 12)
    assert body["active_form"] is None
    assert (await _comp(client, cid, f["id"]))["is_active"] is False
    assert body["temp_hp"] == 0 and body["current_hit_points"] == 15  # 7 overflow: 2 temp + 5 HP
    hist = (await client.get(f"/characters/{cid}/history")).json()
    assert any("Forma selvatica terminata" in h["description"] for h in hist)


async def test_wild_shape_concentration_save_on_damage(client, monkeypatch):
    cid = await _make_char(client, 20)
    await _start_concentration(client, cid)
    f = await _form(client, cid, hp=40)
    await _activate(client, cid, f["id"])
    _force_d20(monkeypatch, 20)
    body = await _hp(client, cid, "damage", 30)
    assert body["current_hit_points"] == 20
    assert body["concentration_save"]["dc"] == 15  # full damage, absorbed by the form
    # overflow case: a single save, DC from the overflow only
    cid2 = await _make_char(client, 40)
    await _start_concentration(client, cid2)
    g = await _form(client, cid2, hp=20)
    await _activate(client, cid2, g["id"])
    body = await _hp(client, cid2, "damage", 50)  # form 20, overflow 30 -> DC 15, not 25
    assert body["current_hit_points"] == 10 and body["concentration_save"]["dc"] == 15


async def test_heal_heals_form(client):
    cid = await _make_char(client, 20, current=10)
    f = await _form(client, cid, hp=10)
    await _activate(client, cid, f["id"])
    await _hp(client, cid, "damage", 8)
    body = await _hp(client, cid, "heal", 5)
    assert body["current_hit_points"] == 10
    assert body["active_form"]["current_hp"] == 7


async def test_massive_damage_overflow_uses_overflow_only(client):
    cid = await _make_char(client, 20)
    f = await _form(client, cid, hp=30)
    await _activate(client, cid, f["id"])
    # 45 total >= 20 max would be instant death; overflow is only 15
    body = await _hp(client, cid, "damage", 45)
    assert body["is_dead"] is False and body["current_hit_points"] == 5
