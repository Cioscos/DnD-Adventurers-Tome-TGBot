"""Campaign atlas markers: private/public, custom types, sub-map links."""
from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from api.routers import atlas as atlas_router
from api.services import campaigns as svc
from core.db.models import CampaignMap, CampaignMapMarker, CampaignMarkerType, SessionMessage, SessionStatus
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID
from tests.integration.test_campaign_atlas_maps import PNG
from tests.integration.test_campaigns_api import _char, _enrolled, _session, act

PLAYER2_ID = 7777


@pytest.fixture(autouse=True)
def atlas_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(svc, "ATLAS_DIR", tmp_path / "atlas")
    monkeypatch.setattr(atlas_router, "DEV_USER_ID", None)
    monkeypatch.setattr(atlas_router, "verify_init_data", lambda raw: int(raw))
    return tmp_path / "atlas"


def _base(camp):
    return f"/campaigns/{camp['id']}/atlas"


async def _setup(client, factory, reveal=True):
    """Campaign with player 1 and player 2 enrolled and one map (revealed by default)."""
    camp, _ = await _enrolled(client, factory)
    cid2 = await _char(factory, PLAYER2_ID, name="Eroe2")
    act(PLAYER2_ID)
    r = await client.post("/campaigns/enroll", json={"code": camp["invite_code"], "character_id": cid2})
    assert r.status_code == 200, r.text
    act(GM_ID)
    mid = await _map(client, camp)
    if reveal:
        await client.post(f"{_base(camp)}/maps/{mid}/reveal")
    return camp, mid


async def _map(client, camp, name="Mondo"):
    r = await client.post(f"{_base(camp)}/maps", data={"name": name}, files={"file": ("m.png", PNG, "image/png")})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _mk(client, camp, mid, **over):
    body = {"name": "Rovine", "x": 0.3, "y": 0.4, "type_key": "poi", **over}
    return await client.post(f"{_base(camp)}/maps/{mid}/markers", json=body)


async def _list(client, camp, mid):
    return await client.get(f"{_base(camp)}/maps/{mid}/markers")


async def _feed(factory):
    async with factory() as s:
        rows = (await s.execute(select(SessionMessage))).scalars().all()
    return [json.loads(m.trade_payload) for m in rows]


async def test_player_private_marker_visible_only_to_author(client, test_session_factory):
    camp, mid = await _setup(client, test_session_factory)
    act(PLAYER_ID)
    r = await _mk(client, camp, mid)
    assert r.status_code == 201, r.text
    k = r.json()["id"]
    assert r.json()["visibility"] == "private" and r.json()["mine"] is True
    assert len((await _list(client, camp, mid)).json()) == 1
    for uid in (PLAYER2_ID, GM_ID):
        act(uid)
        assert (await _list(client, camp, mid)).json() == []
    m = f"{_base(camp)}/markers/{k}"
    calls = [await client.patch(m, json={"name": "x"}), await client.delete(m),
             await client.post(m + "/visibility", json={"visibility": "public"})]
    assert [c.status_code for c in calls] == [404] * 3
    assert all(c.json()["detail"] == "marker_not_found" for c in calls)


async def test_public_player_marker_visible_to_all_gm_can_delete_not_edit(client, test_session_factory):
    camp, mid = await _setup(client, test_session_factory)
    act(PLAYER_ID)
    k = (await _mk(client, camp, mid, visibility="public")).json()["id"]
    for uid in (PLAYER2_ID, GM_ID):
        act(uid)
        [mk] = (await _list(client, camp, mid)).json()
        assert mk["author_name"] == "Eroe" and mk["author_role"] == "player" and mk["mine"] is False
        assert mk["can_edit"] is False
    assert mk["can_delete"] is True  # GM
    m = f"{_base(camp)}/markers/{k}"
    assert (await client.patch(m, json={"name": "x"})).status_code == 403
    assert (await client.delete(m)).status_code == 204
    assert (await _list(client, camp, mid)).json() == []


async def test_gm_hidden_marker_then_public_writes_feed(client, test_session_factory):
    camp, mid = await _setup(client, test_session_factory)
    await _session(test_session_factory, camp["id"], status=SessionStatus.ACTIVE,
                   created="2026-06-08T20:00:00", last="2026-06-08T20:00:00")
    act(GM_ID)
    k = (await _mk(client, camp, mid, name="Tesoro")).json()["id"]
    act(PLAYER_ID)
    assert (await _list(client, camp, mid)).json() == []
    act(GM_ID)
    v = f"{_base(camp)}/markers/{k}/visibility"
    r = await client.post(v, json={"visibility": "public"})
    assert r.status_code == 200 and r.json()["visibility"] == "public"
    await client.post(v, json={"visibility": "public"})
    assert await _feed(test_session_factory) == [
        {"kind": "atlas_reveal", "map_id": mid, "marker_id": k, "title": "Tesoro"}]
    async with test_session_factory() as s:
        msg = (await s.execute(select(SessionMessage))).scalars().one()
    assert msg.body == "Il master ha rivelato: Tesoro" and msg.sender_display_name == "__GM__"
    act(PLAYER_ID)
    assert [x["id"] for x in (await _list(client, camp, mid)).json()] == [k]


async def test_gm_create_public_on_revealed_map_writes_feed(client, test_session_factory):
    camp, mid = await _setup(client, test_session_factory)
    await _session(test_session_factory, camp["id"], status=SessionStatus.ACTIVE,
                   created="2026-06-08T20:00:00", last="2026-06-08T20:00:00")
    act(GM_ID)
    k = (await _mk(client, camp, mid, visibility="public")).json()["id"]
    assert [p["marker_id"] for p in await _feed(test_session_factory)] == [k]


async def test_gm_create_public_on_hidden_map_no_feed(client, test_session_factory):
    camp, mid = await _setup(client, test_session_factory, reveal=False)
    await _session(test_session_factory, camp["id"], status=SessionStatus.ACTIVE,
                   created="2026-06-08T20:00:00", last="2026-06-08T20:00:00")
    act(GM_ID)
    assert (await _mk(client, camp, mid, visibility="public")).status_code == 201
    assert await _feed(test_session_factory) == []


async def test_player_visibility_change_never_writes_feed(client, test_session_factory):
    camp, mid = await _setup(client, test_session_factory)
    await _session(test_session_factory, camp["id"], status=SessionStatus.ACTIVE,
                   created="2026-06-08T20:00:00", last="2026-06-08T20:00:00")
    act(PLAYER_ID)
    assert (await _mk(client, camp, mid, visibility="public")).status_code == 201
    k = (await _mk(client, camp, mid)).json()["id"]
    r = await client.post(f"{_base(camp)}/markers/{k}/visibility", json={"visibility": "public"})
    assert r.status_code == 200
    assert await _feed(test_session_factory) == []


async def test_hidden_map_hides_player_markers_until_revealed_again(client, test_session_factory):
    camp, mid = await _setup(client, test_session_factory)
    act(PLAYER_ID)
    await _mk(client, camp, mid)
    act(GM_ID)
    await client.post(f"{_base(camp)}/maps/{mid}/hide")
    act(PLAYER_ID)
    r = await _list(client, camp, mid)
    assert r.status_code == 404 and r.json()["detail"] == "map_not_found"
    async with test_session_factory() as s:
        assert len((await s.execute(select(CampaignMapMarker))).scalars().all()) == 1
    act(GM_ID)
    await client.post(f"{_base(camp)}/maps/{mid}/reveal")
    act(PLAYER_ID)
    assert len((await _list(client, camp, mid)).json()) == 1


async def test_player_cannot_place_on_hidden_map(client, test_session_factory):
    camp, mid = await _setup(client, test_session_factory, reveal=False)
    act(PLAYER_ID)
    r = await _mk(client, camp, mid)
    assert r.status_code == 404 and r.json()["detail"] == "map_not_found"


async def test_link_rules(client, test_session_factory):
    camp, mid = await _setup(client, test_session_factory)
    other = await _map(client, camp, "Sotterranei")  # hidden
    act(PLAYER_ID)
    r = await _mk(client, camp, mid, link_map_id=other)
    assert r.status_code == 403 and r.json()["detail"] == "link_gm_only"
    act(GM_ID)
    r = await _mk(client, camp, mid, link_map_id=mid)
    assert r.status_code == 422 and r.json()["detail"] == "invalid_link"
    r = await _mk(client, camp, mid, link_map_id=other, visibility="public")
    assert r.status_code == 201 and r.json()["link_map_id"] == other
    act(PLAYER_ID)
    [mk] = (await _list(client, camp, mid)).json()
    assert mk["link_map_id"] is None
    act(GM_ID)
    await client.post(f"{_base(camp)}/maps/{other}/reveal")
    act(PLAYER_ID)
    assert (await _list(client, camp, mid)).json()[0]["link_map_id"] == other


async def test_coordinates_and_type_validated(client, test_session_factory):
    camp, mid = await _setup(client, test_session_factory)
    act(PLAYER_ID)
    assert (await _mk(client, camp, mid, x=1.2)).status_code == 422
    assert (await _mk(client, camp, mid, y=-0.1)).status_code == 422
    assert (await _mk(client, camp, mid, type_key="nope")).status_code == 422
    r = await _mk(client, camp, mid, custom_type_id=999)
    assert r.status_code == 422  # both type_key and custom_type_id
    r = await _mk(client, camp, mid, type_key=None, custom_type_id=999)
    assert r.status_code == 422 and r.json()["detail"] == "invalid_type"


async def test_custom_type_create_list_delete_falls_back_to_poi(client, test_session_factory):
    camp, mid = await _setup(client, test_session_factory)
    act(PLAYER_ID)
    r = await client.post(f"{_base(camp)}/marker-types", json={"name": "Taverna", "icon": "beer", "color": "amber"})
    assert r.status_code == 201, r.text
    tid = r.json()["id"]
    listed = (await client.get(f"{_base(camp)}/marker-types")).json()
    assert [t["key"] for t in listed[:6]] == ["city", "dungeon", "poi", "danger", "npc", "quest"]
    assert listed[0]["builtin"] is True and listed[0]["can_delete"] is False and listed[0]["id"] is None
    assert listed[6]["id"] == tid and listed[6]["can_delete"] is True
    k = (await _mk(client, camp, mid, type_key=None, custom_type_id=tid)).json()
    assert k["type"]["id"] == tid and k["type"]["name"] == "Taverna"
    act(PLAYER2_ID)
    assert (await client.delete(f"{_base(camp)}/marker-types/{tid}")).status_code == 403
    act(GM_ID)
    assert (await client.delete(f"{_base(camp)}/marker-types/{tid}")).status_code == 204
    act(PLAYER_ID)
    [mk] = (await _list(client, camp, mid)).json()
    assert mk["type"]["key"] == "poi" and mk["type"]["id"] is None


async def test_custom_type_rejects_unknown_icon_and_color(client, test_session_factory):
    camp, _ = await _setup(client, test_session_factory)
    act(PLAYER_ID)
    url = f"{_base(camp)}/marker-types"
    assert (await client.post(url, json={"name": "T", "icon": "nope", "color": "amber"})).status_code == 422
    assert (await client.post(url, json={"name": "T", "icon": "beer", "color": "nope"})).status_code == 422
    assert (await client.post(url, json={"name": "x" * 41, "icon": "beer", "color": "amber"})).status_code == 422


async def test_patch_own_marker(client, test_session_factory):
    camp, mid = await _setup(client, test_session_factory)
    act(PLAYER_ID)
    k = (await _mk(client, camp, mid)).json()["id"]
    r = await client.patch(f"{_base(camp)}/markers/{k}", json={"name": "Nuovo", "x": 0.9})
    assert r.status_code == 200 and r.json()["name"] == "Nuovo" and r.json()["x"] == 0.9


async def test_delete_map_counts_private_player_markers(client, test_session_factory):
    camp, mid = await _setup(client, test_session_factory)
    act(PLAYER_ID)
    await _mk(client, camp, mid)
    act(GM_ID)
    assert (await client.delete(f"{_base(camp)}/maps/{mid}")).json() == {"deleted_markers": 1}


async def test_delete_map_nulls_links_from_other_maps(client, test_session_factory):
    camp, mid = await _setup(client, test_session_factory)
    other = await _map(client, camp, "Altra")
    act(GM_ID)
    k = (await _mk(client, camp, mid, link_map_id=other)).json()["id"]
    assert (await client.delete(f"{_base(camp)}/maps/{other}")).status_code == 200
    async with test_session_factory() as s:
        assert (await s.get(CampaignMapMarker, k)).link_map_id is None


async def test_marker_on_hidden_map_answers_like_missing_id(client, test_session_factory):
    camp, mid = await _setup(client, test_session_factory)
    act(GM_ID)
    k = (await _mk(client, camp, mid, visibility="public")).json()["id"]
    await client.post(f"{_base(camp)}/maps/{mid}/hide")
    act(PLAYER_ID)
    hidden = await client.patch(f"{_base(camp)}/markers/{k}", json={"name": "x"})
    missing = await client.patch(f"{_base(camp)}/markers/999999", json={"name": "x"})
    assert hidden.status_code == missing.status_code == 404
    assert hidden.json()["detail"] == missing.json()["detail"] == "marker_not_found"


async def test_delete_campaign_removes_atlas_rows_and_folder(client, test_session_factory, atlas_dir):
    camp, mid = await _setup(client, test_session_factory)
    act(PLAYER_ID)
    tid = (await client.post(f"{_base(camp)}/marker-types", json={"name": "Taverna", "icon": "beer", "color": "amber"})).json()["id"]
    assert (await _mk(client, camp, mid, type_key=None, custom_type_id=tid)).status_code == 201
    folder = atlas_dir / str(camp["id"])
    (folder / "orphan.bin").write_bytes(b"x")
    act(GM_ID)
    assert (await client.delete(f"/campaigns/{camp['id']}")).status_code == 204
    assert not folder.exists()
    async with test_session_factory() as s:
        for model in (CampaignMap, CampaignMapMarker, CampaignMarkerType):
            assert (await s.execute(select(model))).scalars().all() == []
