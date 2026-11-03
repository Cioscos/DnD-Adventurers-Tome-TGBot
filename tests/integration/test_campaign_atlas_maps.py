"""Campaign atlas maps: upload, hidden/visible, reveal feed row, files."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import select

from api.routers import atlas as atlas_router
from api.services import campaigns as svc
from core.db.models import SessionMessage, SessionStatus
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID
from tests.integration.test_campaigns_api import STRANGER_ID, _enrolled, _session, act

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 20


@pytest.fixture(autouse=True)
def atlas_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(svc, "ATLAS_DIR", tmp_path / "atlas")
    monkeypatch.setattr(atlas_router, "DEV_USER_ID", None)
    monkeypatch.setattr(atlas_router, "verify_init_data", lambda raw: int(raw))
    return tmp_path / "atlas"


def _url(camp, tail=""):
    return f"/campaigns/{camp['id']}/atlas/maps{tail}"


async def _create(client, camp, name="Mondo", filename="m.png", content=PNG):
    return await client.post(_url(camp), data={"name": name}, files={"file": (filename, content, "image/png")})


def _image(client, camp, mid, uid):
    return client.get(_url(camp, f"/{mid}/image"), params={"init_data": str(uid)})


def _files(d: Path) -> list[Path]:
    return [p for p in d.rglob("*") if p.is_file()]


async def test_gm_uploads_hidden_map_player_cannot_see(client, test_session_factory):
    camp, _ = await _enrolled(client, test_session_factory)
    act(GM_ID)
    r = await _create(client, camp)
    assert r.status_code == 201, r.text
    assert r.json()["revealed"] is False
    mid = r.json()["id"]
    assert len((await client.get(_url(camp))).json()) == 1
    act(PLAYER_ID)
    assert (await client.get(_url(camp))).json() == []
    assert (await _image(client, camp, mid, PLAYER_ID)).status_code == 404
    assert (await _image(client, camp, mid, GM_ID)).status_code == 200


async def test_reveal_writes_feed_row_and_player_sees_map(client, test_session_factory):
    camp, cid = await _enrolled(client, test_session_factory)
    sid = await _session(test_session_factory, camp["id"], status=SessionStatus.ACTIVE,
                         created="2026-06-08T20:00:00", last="2026-06-08T20:00:00")
    act(GM_ID)
    mid = (await _create(client, camp)).json()["id"]
    r = await client.post(_url(camp, f"/{mid}/reveal"))
    assert r.json()["revealed"] is True and r.json()["revealed_at"]
    async with test_session_factory() as s:
        msgs = (await s.execute(select(SessionMessage).where(SessionMessage.session_id == sid))).scalars().all()
    assert [json.loads(m.trade_payload) for m in msgs] == [
        {"kind": "atlas_reveal", "map_id": mid, "marker_id": None, "title": "Mondo"}]
    assert msgs[0].body == "Il master ha rivelato: Mondo" and msgs[0].sender_display_name == "__GM__"
    act(PLAYER_ID)
    assert [m["id"] for m in (await client.get(_url(camp))).json()] == [mid]
    assert (await _image(client, camp, mid, PLAYER_ID)).status_code == 200


async def test_reveal_twice_writes_one_row(client, test_session_factory):
    camp, _ = await _enrolled(client, test_session_factory)
    await _session(test_session_factory, camp["id"], status=SessionStatus.ACTIVE,
                   created="2026-06-08T20:00:00", last="2026-06-08T20:00:00")
    act(GM_ID)
    mid = (await _create(client, camp)).json()["id"]
    await client.post(_url(camp, f"/{mid}/reveal"))
    await client.post(_url(camp, f"/{mid}/reveal"))
    async with test_session_factory() as s:
        assert len((await s.execute(select(SessionMessage))).scalars().all()) == 1


async def test_replace_image_deletes_old_file_and_bumps_updated_at(client, test_session_factory, monkeypatch, atlas_dir):
    camp, _ = await _enrolled(client, test_session_factory)
    stamps = iter(["2026-01-01T10:00:00", "2026-01-01T11:00:00"])
    monkeypatch.setattr(atlas_router, "_now", lambda: next(stamps))
    act(GM_ID)
    created = (await _create(client, camp)).json()
    [old] = _files(atlas_dir)
    r = await client.put(_url(camp, f"/{created['id']}/image"), files={"file": ("n.jpg", PNG, "image/jpeg")})
    assert r.status_code == 200, r.text
    assert r.json()["updated_at"] != created["updated_at"]
    assert not old.exists()
    [new] = _files(atlas_dir)
    assert new.suffix == ".jpg"


async def test_player_cannot_manage_maps(client, test_session_factory):
    camp, _ = await _enrolled(client, test_session_factory)
    act(GM_ID)
    mid = (await _create(client, camp)).json()["id"]
    await client.post(_url(camp, f"/{mid}/reveal"))
    act(PLAYER_ID)
    base = _url(camp, f"/{mid}")
    calls = [
        await _create(client, camp),
        await client.patch(base, json={"name": "x"}),
        await client.put(base + "/image", files={"file": ("n.png", PNG, "image/png")}),
        await client.post(base + "/reveal"),
        await client.post(base + "/hide"),
        await client.delete(base),
    ]
    assert [c.status_code for c in calls] == [403] * 6
    assert all(c.json()["detail"] == "gm_only" for c in calls)


async def test_upload_rejects_gif_and_oversize(client, test_session_factory, atlas_dir):
    camp, _ = await _enrolled(client, test_session_factory)
    act(GM_ID)
    assert (await _create(client, camp, filename="m.gif")).status_code == 400
    assert (await _create(client, camp, content=b"0" * (10 * 1024 * 1024 + 1))).status_code == 400
    assert (await _create(client, camp, name="x" * 81)).status_code == 422
    assert _files(atlas_dir) == []


async def test_delete_map_returns_count_and_removes_file(client, test_session_factory, atlas_dir):
    camp, _ = await _enrolled(client, test_session_factory)
    act(GM_ID)
    mid = (await _create(client, camp)).json()["id"]
    assert len(_files(atlas_dir)) == 1
    r = await client.delete(_url(camp, f"/{mid}"))
    assert r.status_code == 200 and r.json() == {"deleted_markers": 0}
    assert _files(atlas_dir) == []
    assert (await client.get(_url(camp))).json() == []


async def test_non_member_403(client, test_session_factory):
    camp, _ = await _enrolled(client, test_session_factory)
    act(STRANGER_ID)
    assert (await client.get(_url(camp))).status_code == 403
    assert (await _image(client, camp, 1, STRANGER_ID)).status_code == 403
