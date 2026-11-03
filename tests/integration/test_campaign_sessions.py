"""Sessions inside a campaign: start from campaign, one-tap join, active-for-me."""
from __future__ import annotations

from sqlalchemy import select

from api.tasks import session_cleanup
from core.db.models import CampaignMember, GameSession, SessionParticipant, SessionStatus
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID
from tests.integration.test_campaigns_api import STRANGER_ID, _char, _enrolled, act


async def _start(client, camp_id, title=None):
    body = {"campaign_id": camp_id}
    if title:
        body["title"] = title
    return await client.post("/sessions", json=body)


async def test_single_evening_unchanged(client, test_session_factory):
    act(GM_ID)
    r = await client.post("/sessions", json={"title": "Serata"})
    assert r.status_code == 201
    body = r.json()
    assert body["campaign_id"] is None and body["campaign_name"] is None
    act(PLAYER_ID)
    cid = await _char(test_session_factory, PLAYER_ID)
    r = await client.post("/sessions/join", json={"code": body["code"], "character_id": cid})
    assert r.status_code == 200 and len(body["code"]) == 6


async def test_create_in_campaign(client, test_session_factory):
    camp, _ = await _enrolled(client, test_session_factory)
    act(PLAYER_ID)
    assert (await _start(client, camp["id"])).status_code == 403
    act(GM_ID)
    r = await _start(client, camp["id"])
    assert r.status_code == 201
    assert r.json()["title"] == "Saga" and r.json()["campaign_name"] == "Saga"
    assert r.json()["campaign_id"] == camp["id"]
    me = (await client.get("/sessions/me")).json()
    assert me["campaign_id"] == camp["id"] and me["campaign_name"] == "Saga"


async def test_second_active_session_409(client, test_session_factory):
    camp, _ = await _enrolled(client, test_session_factory)
    # Active campaign session with no GM participant row, so the per-user rule
    # cannot fire and only the per-campaign check is exercised.
    async with test_session_factory() as s:
        s.add(GameSession(
            campaign_id=camp["id"], code="ZZZZZZ", gm_user_id=GM_ID,
            status=SessionStatus.ACTIVE, created_at="2026-01-01T00:00:00",
            last_activity_at="2026-01-01T00:00:00",
        ))
        await s.commit()
    act(GM_ID)
    r = await _start(client, camp["id"])
    assert r.status_code == 409 and r.json()["detail"] == "campaign_session_active"


async def test_join_and_preselection(client, test_session_factory):
    camp, cid = await _enrolled(client, test_session_factory)
    act(GM_ID)
    s1 = (await _start(client, camp["id"])).json()
    act(PLAYER_ID)
    r = await client.post(f"/campaigns/{camp['id']}/session/join", json={"character_id": cid})
    assert r.status_code == 200, r.text
    assert r.json()["id"] == s1["id"] and r.json()["campaign_name"] == "Saga"
    assert any(p["character_id"] == cid and p["display_name"] == "Eroe" for p in r.json()["participants"])
    act(GM_ID)
    await client.post(f"/sessions/{s1['id']}/close")
    s2 = (await _start(client, camp["id"])).json()
    act(PLAYER_ID)
    row = (await client.get("/campaigns/active-for-me")).json()
    assert row == [{
        "campaign_id": camp["id"], "campaign_name": "Saga",
        "session_id": s2["id"], "my_last_character_id": cid,
    }]


async def test_join_errors(client, test_session_factory):
    camp, cid = await _enrolled(client, test_session_factory)
    act(PLAYER_ID)
    url = f"/campaigns/{camp['id']}/session/join"
    r = await client.post(url, json={"character_id": cid})
    assert r.status_code == 404 and r.json()["detail"] == "no_active_session"
    act(STRANGER_ID)
    r = await client.post(url, json={"character_id": cid})
    assert r.status_code == 404 and r.json()["detail"] == "campaign_not_found"
    act(GM_ID)
    await _start(client, camp["id"])
    act(PLAYER_ID)
    other = await _char(test_session_factory, PLAYER_ID, "Fuori")
    r = await client.post(url, json={"character_id": other})
    assert r.status_code == 422 and r.json()["detail"] == "not_a_member"
    gm_char = await _char(test_session_factory, GM_ID, "Altrui")
    r = await client.post(url, json={"character_id": gm_char})
    assert r.status_code == 403 and r.json()["detail"] == "not_your_character"
    async with test_session_factory() as s:
        m = (await s.execute(select(CampaignMember).where(CampaignMember.character_id == cid))).scalar_one()
        m.status = "dead"
        await s.commit()
    r = await client.post(url, json={"character_id": cid})
    assert r.status_code == 422 and r.json()["detail"] == "character_dead"
    assert (await client.get("/campaigns/active-for-me")).json() == []


async def test_join_when_in_other_session_409(client, test_session_factory):
    camp, cid = await _enrolled(client, test_session_factory)
    act(GM_ID)
    await _start(client, camp["id"])
    act(PLAYER_ID)
    gm2 = await client.post("/sessions", json={})
    assert gm2.status_code == 201
    r = await client.post(f"/campaigns/{camp['id']}/session/join", json={"character_id": cid})
    assert r.status_code == 409 and r.json()["detail"] == "You already have an active session"
    async with test_session_factory() as s:
        n = (await s.execute(select(SessionParticipant).where(SessionParticipant.character_id == cid))).scalars().all()
        assert n == []


async def test_active_for_me_excludes_joined_and_gm(client, test_session_factory):
    camp, cid = await _enrolled(client, test_session_factory)
    act(GM_ID)
    await _start(client, camp["id"])
    assert (await client.get("/campaigns/active-for-me")).json() == []
    act(PLAYER_ID)
    assert len((await client.get("/campaigns/active-for-me")).json()) == 1
    await client.post(f"/campaigns/{camp['id']}/session/join", json={"character_id": cid})
    assert (await client.get("/campaigns/active-for-me")).json() == []


async def test_sweep_closes_campaign_sessions(client, test_session_factory, monkeypatch):
    camp, _ = await _enrolled(client, test_session_factory)
    act(GM_ID)
    sid = (await _start(client, camp["id"])).json()["id"]
    async with test_session_factory() as s:
        g = await s.get(GameSession, sid)
        g.last_activity_at = "2000-01-01T00:00:00"
        await s.commit()
    monkeypatch.setattr(session_cleanup, "AsyncSessionLocal", test_session_factory)
    assert await session_cleanup._sweep_once() == 1
    async with test_session_factory() as s:
        assert (await s.get(GameSession, sid)).status == SessionStatus.CLOSED


async def test_preselection_skips_dead_or_unenrolled(client, test_session_factory):
    camp, cid = await _enrolled(client, test_session_factory)
    act(GM_ID)
    s1 = (await _start(client, camp["id"])).json()
    act(PLAYER_ID)
    await client.post(f"/campaigns/{camp['id']}/session/join", json={"character_id": cid})
    act(GM_ID)
    await client.post(f"/sessions/{s1['id']}/close")
    await _start(client, camp["id"])
    act(PLAYER_ID)
    assert (await client.get("/campaigns/active-for-me")).json()[0]["my_last_character_id"] == cid
    async with test_session_factory() as s:
        m = (await s.execute(select(CampaignMember).where(CampaignMember.character_id == cid))).scalar_one()
        m.status = "dead"
        await s.commit()
    # the only PG is dead: nothing to offer (and no banner at all)
    assert (await client.get("/campaigns/active-for-me")).json() == []
    async with test_session_factory() as s:
        m = (await s.execute(select(CampaignMember).where(CampaignMember.character_id == cid))).scalar_one()
        m.status = "active"
        await s.commit()
    r = await client.delete(f"/campaigns/{camp['id']}/members/{cid}")
    assert r.status_code == 204
    assert (await client.get("/campaigns/active-for-me")).json() == []
