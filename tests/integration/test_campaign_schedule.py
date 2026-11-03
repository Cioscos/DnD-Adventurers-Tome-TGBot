"""Campaign calendar: CRUD, session linking, Telegram reminders."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from api.services import campaigns as svc
from api.tasks.campaign_reminders import _remind_once
from core.db.models import BotUser, CampaignMember, CampaignSchedule
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID
from tests.integration._telegram_stub import install_fake_telegram
from tests.integration.test_campaigns_api import STRANGER_ID, _char, _enrolled, _new_campaign, act


@pytest.fixture(autouse=True)
def _env(tmp_path, monkeypatch):
    monkeypatch.delenv("SEND_CAMPAIGN_MESSAGES", raising=False)
    monkeypatch.setattr(svc, "LORE_DIR", tmp_path / "lore")


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def _in(**kw) -> datetime:
    return datetime.utcnow() + timedelta(**kw)


async def _add(client, camp_id, when: datetime, note=None) -> dict:
    act(GM_ID)
    r = await client.post(f"/campaigns/{camp_id}/schedule",
                          json={"starts_at": _iso(when) + "Z", "note": note})
    assert r.status_code == 201, r.text
    return r.json()


async def _row(factory, sid) -> CampaignSchedule:
    async with factory() as s:
        return await s.get(CampaignSchedule, sid)


async def _insert(factory, camp_id, when: datetime, **kw) -> int:
    async with factory() as s:
        row = CampaignSchedule(campaign_id=camp_id, starts_at=_iso(when), created_at=_iso(datetime.utcnow()), **kw)
        s.add(row)
        await s.commit()
        return row.id


def _sends(captured):
    return [c["json"] for c in captured if "sendMessage" in c["url"]]


async def test_gm_crud_schedule_member_reads(client, test_session_factory):
    camp, _ = await _enrolled(client, test_session_factory)
    when = _in(days=3)
    # offset input is normalised to naive UTC
    local = when.replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=2)))
    act(GM_ID)
    r = await client.post(f"/campaigns/{camp['id']}/schedule", json={"starts_at": local.isoformat(), "note": "  Cena  "})
    assert r.status_code == 201, r.text
    item = r.json()
    assert item["starts_at"] == _iso(when) and item["note"] == "Cena" and item["status"] == "planned"

    act(PLAYER_ID)
    assert [x["id"] for x in (await client.get(f"/campaigns/{camp['id']}/schedule")).json()] == [item["id"]]

    act(GM_ID)
    later = _in(days=5)
    r = await client.patch(f"/campaigns/{camp['id']}/schedule/{item['id']}",
                           json={"starts_at": _iso(later) + "Z", "note": None})
    assert r.status_code == 200 and r.json()["starts_at"] == _iso(later) and r.json()["note"] is None
    r = await client.delete(f"/campaigns/{camp['id']}/schedule/{item['id']}")
    assert r.status_code == 204
    assert (await client.get(f"/campaigns/{camp['id']}/schedule")).json() == []


async def test_past_starts_at_422(client, test_session_factory):
    camp, _ = await _enrolled(client, test_session_factory)
    act(GM_ID)
    for body in ({"starts_at": _iso(_in(hours=-1)) + "Z"}, {"starts_at": _iso(_in(days=2))}):  # past; naive
        r = await client.post(f"/campaigns/{camp['id']}/schedule", json=body)
        assert r.status_code == 422, r.text
    item = await _add(client, camp["id"], _in(days=2))
    r = await client.patch(f"/campaigns/{camp['id']}/schedule/{item['id']}",
                           json={"starts_at": _iso(_in(hours=-1)) + "Z"})
    assert r.status_code == 422


async def test_non_gm_cannot_write(client, test_session_factory):
    camp, _ = await _enrolled(client, test_session_factory)
    item = await _add(client, camp["id"], _in(days=2))
    body = {"starts_at": _iso(_in(days=4)) + "Z"}
    act(PLAYER_ID)
    assert (await client.post(f"/campaigns/{camp['id']}/schedule", json=body)).status_code == 403
    assert (await client.patch(f"/campaigns/{camp['id']}/schedule/{item['id']}", json=body)).status_code == 403
    assert (await client.delete(f"/campaigns/{camp['id']}/schedule/{item['id']}")).status_code == 403
    act(STRANGER_ID)
    assert (await client.get(f"/campaigns/{camp['id']}/schedule")).status_code == 404


async def test_status_planned_done_skipped(client, test_session_factory):
    camp, _ = await _enrolled(client, test_session_factory)
    f = test_session_factory
    planned = await _insert(f, camp["id"], _in(days=1))
    skipped = await _insert(f, camp["id"], _in(days=-1))
    done = await _insert(f, camp["id"], _in(days=-2), session_id=5)
    act(GM_ID)
    got = {x["id"]: x["status"] for x in (await client.get(f"/campaigns/{camp['id']}/schedule")).json()}
    assert got == {planned: "planned", skipped: "skipped", done: "done"}


async def test_session_create_links_nearest_within_12h(client, test_session_factory):
    camp, _ = await _enrolled(client, test_session_factory)
    f = test_session_factory
    far = await _insert(f, camp["id"], _in(hours=20))
    near = await _insert(f, camp["id"], _in(hours=-3))
    nearer = await _insert(f, camp["id"], _in(hours=2))
    act(GM_ID)
    r = await client.post("/sessions", json={"campaign_id": camp["id"]})
    assert r.status_code == 201, r.text
    sid = r.json()["id"]
    assert (await _row(f, nearer)).session_id == sid
    assert (await _row(f, near)).session_id is None and (await _row(f, far)).session_id is None


async def test_session_create_no_link_outside_12h(client, test_session_factory):
    camp, _ = await _enrolled(client, test_session_factory)
    row = await _insert(test_session_factory, camp["id"], _in(hours=13))
    act(GM_ID)
    assert (await client.post("/sessions", json={"campaign_id": camp["id"]})).status_code == 201
    assert (await _row(test_session_factory, row)).session_id is None


async def test_day_reminder_once(client, test_session_factory, monkeypatch):
    camp, _ = await _enrolled(client, test_session_factory)
    captured = install_fake_telegram(monkeypatch)
    monkeypatch.setenv("SEND_CAMPAIGN_MESSAGES", "1")
    f = test_session_factory
    async with f() as s:
        s.add(BotUser(user_id=PLAYER_ID, language_code="en", created_at="2026-01-01T00:00:00"))
        await s.commit()
    now = datetime.utcnow()
    await _insert(f, camp["id"], now + timedelta(hours=10), note="Porta il vino")
    assert await _remind_once(now, f) == 1
    assert await _remind_once(now, f) == 0
    sends = _sends(captured)
    assert sorted(p["chat_id"] for p in sends) == sorted([GM_ID, PLAYER_ID])
    by_chat = {p["chat_id"]: p for p in sends}
    assert by_chat[GM_ID]["text"].startswith("📅 Fra circa 10 ore") and "Porta il vino" in by_chat[GM_ID]["text"]
    assert by_chat[PLAYER_ID]["text"].startswith("📅 Game in about 10 hours")
    url = by_chat[GM_ID]["reply_markup"]["inline_keyboard"][0][0]["web_app"]["url"]
    assert url.endswith(f"/campaign/{camp['id']}")


async def test_hour_reminder_sets_day_flag_too(client, test_session_factory, monkeypatch):
    camp, _ = await _enrolled(client, test_session_factory)
    captured = install_fake_telegram(monkeypatch)
    monkeypatch.setenv("SEND_CAMPAIGN_MESSAGES", "1")
    f = test_session_factory
    now = datetime.utcnow()
    sid = await _insert(f, camp["id"], now + timedelta(minutes=30))
    assert await _remind_once(now, f) == 1
    row = await _row(f, sid)
    assert row.reminded_hour_at and row.reminded_day_at
    assert all(p["text"].startswith("⏰") for p in _sends(captured)) and len(_sends(captured)) == 2
    assert await _remind_once(now, f) == 0


async def test_day_then_hour_reminders(client, test_session_factory, monkeypatch):
    camp, _ = await _enrolled(client, test_session_factory)
    captured = install_fake_telegram(monkeypatch)
    monkeypatch.setenv("SEND_CAMPAIGN_MESSAGES", "1")
    f = test_session_factory
    now = datetime.utcnow()
    await _insert(f, camp["id"], now + timedelta(hours=5))
    assert await _remind_once(now, f) == 1
    assert await _remind_once(now + timedelta(hours=4, minutes=10), f) == 1
    texts = [p["text"][:1] for p in _sends(captured)]
    assert texts.count("📅") == 2 and texts.count("⏰") == 2


async def test_move_resets_flags(client, test_session_factory, monkeypatch):
    camp, _ = await _enrolled(client, test_session_factory)
    install_fake_telegram(monkeypatch)
    monkeypatch.setenv("SEND_CAMPAIGN_MESSAGES", "1")
    f = test_session_factory
    now = datetime.utcnow()
    item = await _add(client, camp["id"], now + timedelta(hours=10))
    assert await _remind_once(now, f) == 1
    act(GM_ID)
    r = await client.patch(f"/campaigns/{camp['id']}/schedule/{item['id']}",
                           json={"starts_at": _iso(now + timedelta(hours=12)) + "Z"})
    assert r.status_code == 200
    row = await _row(f, item["id"])
    assert row.reminded_day_at is None and row.reminded_hour_at is None
    assert await _remind_once(now, f) == 1


async def test_no_reminder_after_start(client, test_session_factory, monkeypatch):
    camp, _ = await _enrolled(client, test_session_factory)
    captured = install_fake_telegram(monkeypatch)
    monkeypatch.setenv("SEND_CAMPAIGN_MESSAGES", "1")
    f = test_session_factory
    now = datetime.utcnow()
    await _insert(f, camp["id"], now - timedelta(minutes=5))
    await _insert(f, camp["id"], now + timedelta(hours=2), session_id=3)  # already played
    assert await _remind_once(now, f) == 0
    assert _sends(captured) == []


async def test_no_send_without_flag(client, test_session_factory, monkeypatch):
    camp, _ = await _enrolled(client, test_session_factory)
    captured = install_fake_telegram(monkeypatch)
    f = test_session_factory
    now = datetime.utcnow()
    sid = await _insert(f, camp["id"], now + timedelta(hours=10))
    assert await _remind_once(now, f) == 0
    row = await _row(f, sid)
    assert row.reminded_day_at is None and _sends(captured) == []
    monkeypatch.setenv("SEND_CAMPAIGN_MESSAGES", "1")  # flag turned on later: still due
    assert await _remind_once(now, f) == 1


async def test_dead_members_and_stash_excluded(client, test_session_factory, monkeypatch):
    camp, _ = await _enrolled(client, test_session_factory)
    f = test_session_factory
    dead_cid = await _char(f, STRANGER_ID, "Morto")
    async with f() as s:
        s.add(CampaignMember(campaign_id=camp["id"], character_id=dead_cid, user_id=STRANGER_ID,
                             status="dead", joined_at="2026-01-01T00:00:00"))
        s.add(CampaignMember(campaign_id=camp["id"], character_id=(await _char(f, 0, "Stash")), user_id=0,
                             status="active", joined_at="2026-01-01T00:00:00"))
        await s.commit()
    captured = install_fake_telegram(monkeypatch)
    monkeypatch.setenv("SEND_CAMPAIGN_MESSAGES", "1")
    now = datetime.utcnow()
    await _insert(f, camp["id"], now + timedelta(hours=10))
    await _remind_once(now, f)
    assert sorted(p["chat_id"] for p in _sends(captured)) == sorted([GM_ID, PLAYER_ID])


async def test_delete_campaign_removes_schedule(client, test_session_factory):
    act(GM_ID)
    camp = await _new_campaign(client)
    await _add(client, camp["id"], _in(days=2))
    assert (await client.delete(f"/campaigns/{camp['id']}")).status_code == 204
    async with test_session_factory() as s:
        assert (await s.execute(select(CampaignSchedule))).first() is None


async def test_player_with_two_pgs_gets_one_reminder(client, test_session_factory, monkeypatch):
    camp, _ = await _enrolled(client, test_session_factory)
    f = test_session_factory
    second = await _char(f, PLAYER_ID, "Secondo")
    async with f() as s:
        s.add(CampaignMember(campaign_id=camp["id"], character_id=second, user_id=PLAYER_ID,
                             status="active", joined_at="2026-01-01T00:00:00"))
        await s.commit()
    captured = install_fake_telegram(monkeypatch)
    monkeypatch.setenv("SEND_CAMPAIGN_MESSAGES", "1")
    now = datetime.utcnow()
    await _insert(f, camp["id"], now + timedelta(hours=10))
    await _remind_once(now, f)
    assert sorted(p["chat_id"] for p in _sends(captured)) == sorted([GM_ID, PLAYER_ID])
