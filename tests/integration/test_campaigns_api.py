"""Campaigns REST API: CRUD, enrollment by code, member status, invite share."""
from __future__ import annotations

from sqlalchemy import select

from api.auth import TelegramUser, get_current_telegram_user
from api.main import app
from core.db.models import (
    Campaign, CampaignMember, Character, CharacterClass, GameSession, Item,
    SessionParticipant, SessionRole, SessionStatus,
)
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user
from tests.integration._telegram_stub import install_fake_telegram

STRANGER_ID = 9999


def act(uid: int) -> None:
    as_user(uid)
    app.dependency_overrides[get_current_telegram_user] = (
        lambda: TelegramUser(id=uid, first_name=f"User{uid}")
    )


async def _char(factory, uid: int, name: str = "Eroe", level: int = 3) -> int:
    async with factory() as s:
        c = Character(user_id=uid, name=name)
        s.add(c)
        await s.flush()
        s.add(CharacterClass(character_id=c.id, class_name="wizard", level=level))
        await s.commit()
        return c.id


async def _new_campaign(client, name="Saga") -> dict:
    r = await client.post("/campaigns", json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()


async def _enrolled(client, factory):
    """GM campaign + PLAYER enrolled with one PG. Returns (campaign, char_id)."""
    act(GM_ID)
    camp = await _new_campaign(client)
    cid = await _char(factory, PLAYER_ID)
    act(PLAYER_ID)
    r = await client.post("/campaigns/enroll", json={"code": camp["invite_code"], "character_id": cid})
    assert r.status_code == 200, r.text
    return camp, cid


async def test_create_and_list_visibility(client, test_session_factory):
    camp, cid = await _enrolled(client, test_session_factory)
    assert len(camp["invite_code"]) == 8 and camp["is_gm"] is True
    for uid, expected in ((GM_ID, 1), (PLAYER_ID, 1), (STRANGER_ID, 0)):
        act(uid)
        r = await client.get("/campaigns")
        assert r.status_code == 200
        assert len(r.json()) == expected
    act(PLAYER_ID)
    row = (await client.get("/campaigns")).json()[0]
    assert row["is_gm"] is False and row["member_count"] == 1
    assert row["active_session_id"] is None and row["last_session_at"] is None


async def test_detail_access_and_code_hidden(client, test_session_factory):
    camp, cid = await _enrolled(client, test_session_factory)
    act(GM_ID)
    d = (await client.get(f"/campaigns/{camp['id']}")).json()
    assert d["invite_code"] == camp["invite_code"] and d["is_gm"] is True
    assert d["stash"]["items"] == [] and d["stash"]["currency"]["gold"] == 0
    act(PLAYER_ID)
    d = (await client.get(f"/campaigns/{camp['id']}")).json()
    assert d["invite_code"] is None and d["is_gm"] is False
    m = d["members"][0]
    assert m["character_id"] == cid and m["is_mine"] is True
    assert m["total_level"] == 3 and m["player_name"] == f"User{PLAYER_ID}"
    assert m["status"] == "active" and "wizard" in m["class_summary"]
    act(STRANGER_ID)
    r = await client.get(f"/campaigns/{camp['id']}")
    assert r.status_code == 404 and r.json()["detail"] == "campaign_not_found"


async def test_enroll_errors(client, test_session_factory):
    act(GM_ID)
    camp = await _new_campaign(client)
    gm_char = await _char(test_session_factory, GM_ID)
    r = await client.post("/campaigns/enroll", json={"code": camp["invite_code"], "character_id": gm_char})
    assert r.status_code == 422 and r.json()["detail"] == "gm_cannot_enroll"
    act(PLAYER_ID)
    mine = await _char(test_session_factory, PLAYER_ID)
    r = await client.post("/campaigns/enroll", json={"code": "ZZZZZZZZ", "character_id": mine})
    assert r.status_code == 404 and r.json()["detail"] == "campaign_not_found"
    r = await client.post("/campaigns/enroll", json={"code": camp["invite_code"], "character_id": gm_char})
    assert r.status_code == 403
    ok = await client.post("/campaigns/enroll", json={"code": camp["invite_code"].lower(), "character_id": mine})
    assert ok.status_code == 200
    r = await client.post("/campaigns/enroll", json={"code": camp["invite_code"], "character_id": mine})
    assert r.status_code == 409 and r.json()["detail"] == "already_in_campaign"
    # a character already in a campaign cannot join another one
    act(GM_ID + 1)
    other = await _new_campaign(client, "Altra")
    act(PLAYER_ID)
    r = await client.post("/campaigns/enroll", json={"code": other["invite_code"], "character_id": mine})
    assert r.status_code == 409 and r.json()["detail"] == "already_in_campaign"


async def test_member_status_and_removal(client, test_session_factory):
    camp, cid = await _enrolled(client, test_session_factory)
    url = f"/campaigns/{camp['id']}/members/{cid}"
    act(STRANGER_ID)
    assert (await client.patch(url, json={"status": "dead"})).status_code == 404
    act(PLAYER_ID)
    assert (await client.patch(url, json={"status": "reserve"})).status_code == 200
    act(GM_ID)
    assert (await client.patch(url, json={"status": "dead"})).status_code == 200
    assert (await client.patch(url, json={"status": "bogus"})).status_code == 422
    d = (await client.get(f"/campaigns/{camp['id']}")).json()
    assert d["members"][0]["status"] == "dead"
    # another enrolled player cannot touch it
    other = await _char(test_session_factory, STRANGER_ID)
    act(STRANGER_ID)
    await client.post("/campaigns/enroll", json={"code": camp["invite_code"], "character_id": other})
    assert (await client.patch(url, json={"status": "active"})).status_code == 403
    assert (await client.delete(url)).status_code == 403
    act(PLAYER_ID)
    assert (await client.delete(url)).status_code == 204
    async with test_session_factory() as s:
        assert await s.get(Character, cid) is not None
        assert (await s.execute(select(CampaignMember).where(CampaignMember.character_id == cid))).first() is None


async def test_regenerate_code(client, test_session_factory):
    camp, cid = await _enrolled(client, test_session_factory)
    act(PLAYER_ID)
    assert (await client.post(f"/campaigns/{camp['id']}/invite-code")).status_code == 403
    act(GM_ID)
    r = await client.post(f"/campaigns/{camp['id']}/invite-code")
    new = r.json()["invite_code"]
    assert r.status_code == 200 and new != camp["invite_code"] and len(new) == 8
    act(STRANGER_ID)
    other = await _char(test_session_factory, STRANGER_ID)
    r = await client.post("/campaigns/enroll", json={"code": camp["invite_code"], "character_id": other})
    assert r.status_code == 404


async def test_rename_renames_stash(client, test_session_factory):
    act(GM_ID)
    camp = await _new_campaign(client)
    r = await client.patch(f"/campaigns/{camp['id']}", json={"name": "Nuova"})
    assert r.status_code == 200 and r.json()["name"] == "Nuova"
    async with test_session_factory() as s:
        c = await s.get(Campaign, camp["id"])
        assert (await s.get(Character, c.stash_character_id)).name == "Nuova"
    act(PLAYER_ID)
    assert (await client.patch(f"/campaigns/{camp['id']}", json={"name": "x"})).status_code in (403, 404)


async def _session(factory, camp_id, *, status, created, last, uid=GM_ID, char_id=None, code="AAA111"):
    async with factory() as s:
        gs = GameSession(code=code, gm_user_id=GM_ID, status=status, created_at=created,
                         last_activity_at=last, campaign_id=camp_id)
        s.add(gs)
        await s.flush()
        s.add(SessionParticipant(session_id=gs.id, user_id=GM_ID, role=SessionRole.GAME_MASTER, joined_at=created))
        if char_id:
            s.add(SessionParticipant(session_id=gs.id, user_id=uid, character_id=char_id,
                                     role=SessionRole.PLAYER, joined_at=created))
        await s.commit()
        return gs.id


async def test_detail_sessions_duration_and_last_char(client, test_session_factory):
    camp, cid = await _enrolled(client, test_session_factory)
    f = test_session_factory
    old = await _session(f, camp["id"], status=SessionStatus.CLOSED, created="2026-06-01T20:00:00",
                         last="2026-06-01T22:30:00", uid=PLAYER_ID, char_id=cid, code="OLD111")
    act(PLAYER_ID)
    d = (await client.get(f"/campaigns/{camp['id']}")).json()
    assert [s["id"] for s in d["sessions"]] == [old]
    assert d["sessions"][0]["duration_seconds"] == 9000
    assert d["my_last_character_id"] == cid and d["active_session_id"] is None
    new = await _session(f, camp["id"], status=SessionStatus.ACTIVE, created="2026-06-08T20:00:00",
                         last="2026-06-08T20:10:00", code="NEW111")
    d = (await client.get(f"/campaigns/{camp['id']}")).json()
    assert [s["id"] for s in d["sessions"]] == [new, old]
    assert d["active_session_id"] == new
    # latest session has no PG row for me: fall back to the last one I played
    assert d["my_last_character_id"] == cid
    lst = (await client.get("/campaigns")).json()[0]
    assert lst["active_session_id"] == new and lst["last_session_at"] == "2026-06-08T20:00:00"


async def test_delete_campaign(client, test_session_factory):
    camp, cid = await _enrolled(client, test_session_factory)
    f = test_session_factory
    async with f() as s:
        stash_id = (await s.get(Campaign, camp["id"])).stash_character_id
        s.add(Item(character_id=stash_id, name="Corda"))
        await s.commit()
    sid = await _session(f, camp["id"], status=SessionStatus.ACTIVE, created="2026-06-08T20:00:00",
                         last="2026-06-08T20:10:00")
    act(PLAYER_ID)
    assert (await client.delete(f"/campaigns/{camp['id']}")).status_code == 403
    act(GM_ID)
    r = await client.delete(f"/campaigns/{camp['id']}")
    assert r.status_code == 409 and r.json()["detail"] == "campaign_session_active"
    async with f() as s:
        (await s.get(GameSession, sid)).status = SessionStatus.CLOSED
        await s.commit()
    assert (await client.delete(f"/campaigns/{camp['id']}")).status_code == 204
    async with f() as s:
        assert await s.get(Campaign, camp["id"]) is None
        assert await s.get(Character, stash_id) is None
        assert (await s.execute(select(Item).where(Item.character_id == stash_id))).first() is None
        assert await s.get(Character, cid) is not None
        assert (await s.get(GameSession, sid)).campaign_id is None
        assert (await s.execute(select(CampaignMember))).first() is None


async def test_share_campaign_invite(client, test_session_factory, monkeypatch):
    captured = install_fake_telegram(monkeypatch)
    act(GM_ID)
    camp = await _new_campaign(client)
    act(PLAYER_ID)
    assert (await client.post(f"/share/campaign-invite/{camp['id']}")).status_code in (403, 404)
    act(GM_ID)
    r = await client.post(f"/share/campaign-invite/{camp['id']}")
    assert r.status_code == 200 and r.json()["prepared_message_id"] == "prep-1"
    blob = str(captured)
    assert f"startapp=camp_{camp['invite_code']}" in blob


async def test_blank_name_rejected_and_trimmed(client):
    act(GM_ID)
    assert (await client.post("/campaigns", json={"name": "   "})).status_code == 422
    camp = await _new_campaign(client, "  Saga  ")
    assert camp["name"] == "Saga"
    assert (await client.patch(f"/campaigns/{camp['id']}", json={"name": "  "})).status_code == 422
    assert (await client.patch(f"/campaigns/{camp['id']}", json={"name": " Nuova "})).json()["name"] == "Nuova"


async def test_share_campaign_invite_escapes_markdown(client, monkeypatch):
    captured = install_fake_telegram(monkeypatch)
    act(GM_ID)
    camp = await _new_campaign(client, "Il_regno *rosso*")
    r = await client.post(f"/share/campaign-invite/{camp['id']}")
    assert r.status_code == 200
    call = next(c for c in captured if "savePreparedInlineMessage" in c["url"])
    text = call["json"]["result"]["input_message_content"]["message_text"]
    assert r"*Il\_regno \*rosso\**" in text
