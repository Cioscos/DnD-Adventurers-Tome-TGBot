"""Il giocatore tira i TS in sospeso (spec §4)."""
from __future__ import annotations

from sqlalchemy import select

from api.services.condition_effects import SaveSpec, upsert_effect
from core.db.models import Character, ConditionEffect, PendingSave
from tests.integration._encounter_helpers import as_user


async def _setup(client, factory, *, dc=10, status="pending", inspiration=False):
    r = await client.post("/characters", json={"name": "Eroe"})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    async with factory() as s:
        ch = await s.get(Character, cid)
        ch.conditions = {"poisoned": True}
        ch.heroic_inspiration = inspiration
        eff = await upsert_effect(s, ("character", cid), "poisoned",
                                  save=SaveSpec("constitution", dc, "end"))
        ps = PendingSave(effect_id=eff.id, character_id=cid, ability="constitution", dc=dc,
                         status=status, created_at="2026-10-31T10:00:00")
        s.add(ps)
        await s.commit()
        return cid, ps.id



async def _post(client, cid, psid, body=None):
    return await client.post(f"/characters/{cid}/pending-saves/{psid}/roll", json=body)


async def _conds(factory, cid):
    async with factory() as s:
        ch = await s.get(Character, cid)
        effs = (await s.execute(select(ConditionEffect))).scalars().all()
        return ch.conditions, ch.heroic_inspiration, len(effs)


async def test_roll_pass_removes_condition(client, test_session_factory):
    cid, psid = await _setup(client, test_session_factory, dc=10)
    r = await _post(client, cid, psid, {"die": 20})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["passed"] is True and b["condition_removed"] is True
    assert b["save"]["status"] == "passed" and b["save"]["slug"] == "poisoned"
    assert b["roll"]["die"] == 20
    conds, _, n_eff = await _conds(test_session_factory, cid)
    assert not conds.get("poisoned") and n_eff == 0
    hist = (await client.get(f"/characters/{cid}/history")).json()
    assert any("per Avvelenato" in h["description"] and "(CD 10)" in h["description"]
               for h in hist), hist
    assert any("Liberato da: " in h["description"] for h in hist), hist


async def test_roll_fail_keeps_condition(client, test_session_factory):
    cid, psid = await _setup(client, test_session_factory, dc=30)
    r = await _post(client, cid, psid, {"die": 5})
    b = r.json()
    assert r.status_code == 200 and b["passed"] is False and b["condition_removed"] is False
    assert b["save"]["status"] == "failed" and b["save"]["last_roll"]
    conds, _, n_eff = await _conds(test_session_factory, cid)
    assert conds["poisoned"] is True and n_eff == 1


async def test_advantage_uses_two_dice(client, test_session_factory):
    cid, psid = await _setup(client, test_session_factory, dc=30)
    r = await _post(client, cid, psid, {"mode": "advantage", "dice": [4, 17]})
    assert r.json()["roll"]["die"] == 17 and r.json()["roll"]["dice"] == [4, 17]


async def test_inspiration_reroll_only_after_fail(client, test_session_factory):
    cid, psid = await _setup(client, test_session_factory, dc=10, inspiration=True)
    # pending + inspiration: not rerollable
    r = await _post(client, cid, psid, {"die": 20, "with_inspiration": True})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "not_rerollable"
    async with test_session_factory() as s:
        (await s.get(PendingSave, psid)).status = "failed"
        await s.commit()
    # failed without flag: not rerollable
    r = await _post(client, cid, psid, {"die": 20})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "not_rerollable"
    r = await _post(client, cid, psid, {"die": 20, "with_inspiration": True})
    assert r.status_code == 200 and r.json()["passed"] is True
    assert (await _conds(test_session_factory, cid))[1] is False


async def test_inspiration_unavailable_is_409(client, test_session_factory):
    cid, psid = await _setup(client, test_session_factory, status="failed", inspiration=False)
    r = await _post(client, cid, psid, {"die": 20, "with_inspiration": True})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "inspiration_unavailable"


async def test_roll_after_condition_removed_is_409(client, test_session_factory):
    cid, psid = await _setup(client, test_session_factory)
    async with test_session_factory() as s:
        ch = await s.get(Character, cid)
        ch.conditions = {}
        await s.commit()
    r = await _post(client, cid, psid, {"die": 20})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "condition_gone"
    async with test_session_factory() as s:
        assert (await s.get(PendingSave, psid)).dismissed is True


async def test_other_users_save_is_404(client, test_session_factory):
    cid, psid = await _setup(client, test_session_factory)
    as_user(999)
    r = await _post(client, cid, psid, {"die": 20})
    assert r.status_code == 403

async def test_save_of_another_character_is_404(client, test_session_factory):
    cid, psid = await _setup(client, test_session_factory)
    # same user, different character: the save does not belong to it
    other = (await client.post("/characters", json={"name": "Altro"})).json()["id"]
    r = await _post(client, other, psid, {"die": 20})
    assert r.status_code == 404


async def test_turn_state_lists_pending_and_dismiss(client, test_session_factory):
    cid, psid = await _setup(client, test_session_factory, dc=30)
    ts = (await client.get(f"/characters/{cid}/turn-state")).json()
    assert [p["id"] for p in ts["pending_saves"]] == [psid]
    assert (await client.post(f"/characters/{cid}/pending-saves/{psid}/dismiss")).status_code == 409
    await _post(client, cid, psid, {"die": 1})
    assert (await client.post(f"/characters/{cid}/pending-saves/{psid}/dismiss")).status_code == 204
    ts = (await client.get(f"/characters/{cid}/turn-state")).json()
    assert ts["pending_saves"] == []


async def test_inspiration_reroll_blocked_by_newer_pending(client, test_session_factory):
    cid, psid = await _setup(client, test_session_factory, status="failed", inspiration=True)
    async with test_session_factory() as s:
        old = await s.get(PendingSave, psid)
        s.add(PendingSave(effect_id=old.effect_id, character_id=cid, ability="constitution",
                          dc=10, status="pending", created_at="2026-10-31T11:00:00"))
        await s.commit()
    r = await _post(client, cid, psid, {"die": 20, "with_inspiration": True})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "not_rerollable"
    assert (await _conds(test_session_factory, cid))[1] is True
