"""Campaign lore: drafts, reveal, files, feed row."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import select

from api.routers import lore as lore_router
from core.db.models import CampaignLore, CampaignMember, GameSession, SessionMessage, SessionStatus
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID
from tests.integration.test_campaigns_api import STRANGER_ID, _enrolled, act

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 20


@pytest.fixture(autouse=True)
def lore_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(lore_router, "LORE_DIR", tmp_path / "lore")
    # File routes authenticate by init_data (header/query), not the get_current_user override:
    # init_data is the user id itself.
    monkeypatch.setattr(lore_router, "DEV_USER_ID", None)
    monkeypatch.setattr(lore_router, "verify_init_data", lambda raw: int(raw))
    return tmp_path / "lore"


async def _create(client, camp, title="Il tempio", **extra):
    data = {"title": title, "body": "Antico", "tags": json.dumps(["luoghi"])}
    return await client.post(f"/campaigns/{camp['id']}/lore", data=data, **extra)


def _file(client, camp, lid, kind, uid):
    return client.get(_url(camp, lid, f"/{kind}"), params={"init_data": str(uid)})


def _url(camp, lore_id=None, tail=""):
    return f"/campaigns/{camp['id']}/lore" + (f"/{lore_id}" if lore_id else "") + tail


async def test_gm_creates_draft_member_cannot_see(client, test_session_factory):
    camp, _ = await _enrolled(client, test_session_factory)
    act(GM_ID)
    r = await _create(client, camp)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["revealed"] is False and body["tags"] == ["luoghi"] and body["has_image"] is False
    assert len((await client.get(_url(camp))).json()) == 1
    act(PLAYER_ID)
    assert (await client.get(_url(camp))).json() == []


async def test_reveal_makes_visible_to_members_any_status(client, test_session_factory):
    camp, cid = await _enrolled(client, test_session_factory)
    act(GM_ID)
    lid = (await _create(client, camp)).json()["id"]
    r = await client.post(_url(camp, lid, "/reveal"))
    assert r.json()["revealed"] is True and r.json()["revealed_at"]
    for st in ("reserve", "dead"):
        async with test_session_factory() as s:
            m = (await s.execute(select(CampaignMember).where(CampaignMember.character_id == cid))).scalar_one()
            m.status = st
            await s.commit()
        act(PLAYER_ID)
        assert [x["id"] for x in (await client.get(_url(camp))).json()] == [lid]


async def test_hide_returns_to_draft(client, test_session_factory):
    camp, _ = await _enrolled(client, test_session_factory)
    act(GM_ID)
    lid = (await _create(client, camp)).json()["id"]
    await client.post(_url(camp, lid, "/reveal"))
    r = await client.post(_url(camp, lid, "/hide"))
    assert r.json()["revealed"] is False and r.json()["revealed_at"] is None
    act(PLAYER_ID)
    assert (await client.get(_url(camp))).json() == []


async def test_non_member_403(client, test_session_factory):
    camp, _ = await _enrolled(client, test_session_factory)
    act(STRANGER_ID)
    assert (await client.get(_url(camp))).status_code == 403
    assert (await _file(client, camp, 1, "image", STRANGER_ID)).status_code == 403


async def test_non_gm_cannot_write_403(client, test_session_factory):
    camp, _ = await _enrolled(client, test_session_factory)
    act(GM_ID)
    lid = (await _create(client, camp)).json()["id"]
    act(PLAYER_ID)
    assert (await _create(client, camp)).status_code == 403
    assert (await client.patch(_url(camp, lid), data={"title": "x"})).status_code == 403
    assert (await client.delete(_url(camp, lid))).status_code == 403
    assert (await client.post(_url(camp, lid, "/reveal"))).status_code == 403
    assert (await client.post(_url(camp, lid, "/hide"))).status_code == 403


async def _feed_rows(factory):
    async with factory() as s:
        return (await s.execute(select(SessionMessage))).scalars().all()


async def test_reveal_idempotent_and_feed_row_only_with_active_session(client, test_session_factory):
    camp, _ = await _enrolled(client, test_session_factory)
    act(GM_ID)
    l1 = (await _create(client, camp, "Uno")).json()["id"]
    first = (await client.post(_url(camp, l1, "/reveal"))).json()
    assert await _feed_rows(test_session_factory) == []
    async with test_session_factory() as s:
        sess = GameSession(
            code="LORE01", gm_user_id=GM_ID, status=SessionStatus.ACTIVE, campaign_id=camp["id"],
            created_at="2026-11-03T10:00:00", last_activity_at="2026-11-03T10:00:00",
        )
        s.add(sess)
        await s.commit()
    l2 = (await _create(client, camp, "Due")).json()["id"]
    a = (await client.post(_url(camp, l2, "/reveal"))).json()
    b = (await client.post(_url(camp, l2, "/reveal"))).json()
    assert a["revealed_at"] == b["revealed_at"]
    again = (await client.post(_url(camp, l1, "/reveal"))).json()
    assert again["revealed_at"] == first["revealed_at"]
    rows = await _feed_rows(test_session_factory)
    assert len(rows) == 1
    assert rows[0].sender_display_name == "__GM__"
    assert json.loads(rows[0].trade_payload) == {"kind": "lore_reveal", "lore_id": l2, "title": "Due"}


async def test_image_draft_404_for_member_and_ok_for_gm(client, test_session_factory):
    camp, _ = await _enrolled(client, test_session_factory)
    act(GM_ID)
    r = await _create(client, camp, files={"image": ("a.png", PNG, "image/png")})
    assert r.json()["has_image"] is True
    lid = r.json()["id"]
    got = await _file(client, camp, lid, "image", GM_ID)
    assert got.status_code == 200 and got.content == PNG
    assert (await _file(client, camp, lid, "audio", GM_ID)).status_code == 404
    assert (await _file(client, camp, lid, "image", PLAYER_ID)).status_code == 404


async def test_image_revealed_ok_for_member_via_init_data_query(client, test_session_factory):
    camp, _ = await _enrolled(client, test_session_factory)
    act(GM_ID)
    lid = (await _create(client, camp, files={"image": ("a.png", PNG, "image/png")})).json()["id"]
    await client.post(_url(camp, lid, "/reveal"))
    assert (await client.get(_url(camp, lid, "/image"))).status_code == 401
    r = await _file(client, camp, lid, "image", PLAYER_ID)
    assert r.status_code == 200 and r.content == PNG


async def test_reject_bad_ext_and_oversize(client, test_session_factory, monkeypatch, lore_dir):
    camp, _ = await _enrolled(client, test_session_factory)
    act(GM_ID)
    r = await _create(client, camp, files={"image": ("a.exe", b"x", "application/octet-stream")})
    assert r.status_code == 400
    r = await _create(client, camp, files={"audio": ("a.png", b"x", "image/png")})
    assert r.status_code == 400
    monkeypatch.setattr(lore_router, "_MAX_IMAGE", 10)
    r = await _create(client, camp, files={"image": ("a.png", b"x" * 11, "image/png")})
    assert r.status_code == 400
    assert (await client.get(_url(camp))).json() == []
    assert not lore_dir.exists() or not list(lore_dir.rglob("*.*"))


async def test_patch_replaces_and_removes_files(client, test_session_factory):
    camp, _ = await _enrolled(client, test_session_factory)
    act(GM_ID)
    r = await _create(client, camp, files={"image": ("a.png", PNG, "image/png"), "audio": ("a.mp3", b"id3", "audio/mpeg")})
    lid = r.json()["id"]
    async with test_session_factory() as s:
        old = (await s.get(CampaignLore, lid)).image_path
    r = await client.patch(
        _url(camp, lid), data={"title": "Nuovo", "remove_audio": "true"},
        files={"image": ("b.jpg", PNG, "image/jpeg")},
    )
    j = r.json()
    assert j["title"] == "Nuovo" and j["has_image"] is True and j["has_audio"] is False
    assert not Path(old).exists()


async def test_delete_removes_files(client, test_session_factory):
    camp, _ = await _enrolled(client, test_session_factory)
    act(GM_ID)
    lid = (await _create(client, camp, files={"image": ("a.png", PNG, "image/png")})).json()["id"]
    async with test_session_factory() as s:
        path = Path((await s.get(CampaignLore, lid)).image_path)
    assert path.exists()
    assert (await client.delete(_url(camp, lid))).status_code == 204
    assert not path.exists()
    assert (await client.get(_url(camp))).json() == []


async def test_delete_campaign_removes_lore(client, test_session_factory):
    camp, _ = await _enrolled(client, test_session_factory)
    act(GM_ID)
    lid = (await _create(client, camp, files={"image": ("a.png", PNG, "image/png")})).json()["id"]
    async with test_session_factory() as s:
        path = Path((await s.get(CampaignLore, lid)).image_path)
    assert (await client.delete(f"/campaigns/{camp['id']}")).status_code == 204
    assert not path.exists()
    async with test_session_factory() as s:
        assert (await s.execute(select(CampaignLore))).scalars().all() == []
