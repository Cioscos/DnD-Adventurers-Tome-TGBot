"""Journal entries linked to a campaign (notes.campaign_id)."""
from __future__ import annotations

from sqlalchemy import select

from core.db.models import Campaign, Character
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID
from tests.integration.test_campaigns_api import _char, _enrolled, _new_campaign, act


async def _note(client, cid, title="Diario", **extra):
    return await client.post(f"/characters/{cid}/notes", json={"title": title, "body": "x", **extra})


async def test_create_note_with_current_campaign(client, test_session_factory):
    camp, cid = await _enrolled(client, test_session_factory)
    r = await _note(client, cid, campaign_id=camp["id"])
    assert r.status_code == 201, r.text
    n = r.json()[0]
    assert n["campaign_id"] == camp["id"] and n["campaign_name"] == camp["name"]


async def test_create_note_foreign_campaign_422(client, test_session_factory):
    act(GM_ID)
    other = await _new_campaign(client, "Altra")
    cid = await _char(test_session_factory, PLAYER_ID)
    act(PLAYER_ID)
    r = await _note(client, cid, campaign_id=other["id"])
    assert r.status_code == 422 and r.json()["detail"] == "campaign_not_allowed"


async def test_update_note_sets_and_clears_campaign(client, test_session_factory):
    camp, cid = await _enrolled(client, test_session_factory)
    await _note(client, cid)
    r = await client.patch(f"/characters/{cid}/notes/Diario", json={"body": "y", "campaign_id": camp["id"]})
    assert r.json()[0]["campaign_id"] == camp["id"]
    r = await client.patch(f"/characters/{cid}/notes/Diario", json={"body": "y", "clear_campaign": True})
    assert r.json()[0]["campaign_id"] is None


async def test_update_keeps_campaign_when_omitted(client, test_session_factory):
    camp, cid = await _enrolled(client, test_session_factory)
    await _note(client, cid, campaign_id=camp["id"])
    r = await client.patch(f"/characters/{cid}/notes/Diario", json={"body": "z"})
    assert r.json()[0]["campaign_id"] == camp["id"]


async def test_deleted_campaign_note_has_null_name(client, test_session_factory):
    camp, cid = await _enrolled(client, test_session_factory)
    await _note(client, cid, campaign_id=camp["id"])
    act(GM_ID)
    assert (await client.delete(f"/campaigns/{camp['id']}")).status_code in (200, 204)
    act(PLAYER_ID)
    n = (await client.get(f"/characters/{cid}/notes")).json()[0]
    assert n["campaign_id"] == camp["id"] and n["campaign_name"] is None


async def test_legacy_string_note_reads_campaign_none(client, test_session_factory):
    cid = await _char(test_session_factory, PLAYER_ID)
    async with test_session_factory() as s:
        c = (await s.execute(select(Character).where(Character.id == cid))).scalar_one()
        c.notes = {"Vecchia": "testo"}
        await s.commit()
    act(PLAYER_ID)
    n = (await client.get(f"/characters/{cid}/notes")).json()[0]
    assert n["campaign_id"] is None and n["campaign_name"] is None


async def test_export_keeps_campaign_id_and_duplicate_keeps_it(client, test_session_factory):
    camp, cid = await _enrolled(client, test_session_factory)
    await _note(client, cid, campaign_id=camp["id"])
    exp = (await client.get(f"/characters/{cid}/export")).json()
    assert exp["character"]["notes"]["Diario"]["campaign_id"] == camp["id"]
    dup = (await client.post(f"/characters/{cid}/duplicate")).json()
    notes = (await client.get(f"/characters/{dup['id']}/notes")).json()
    assert notes[0]["campaign_id"] == camp["id"]


async def test_import_strips_campaign_id(client, test_session_factory):
    camp, cid = await _enrolled(client, test_session_factory)
    await _note(client, cid, campaign_id=camp["id"])
    exp = (await client.get(f"/characters/{cid}/export")).json()
    r = await client.post("/characters/import", json=exp)
    assert r.status_code == 201, r.text
    notes = (await client.get(f"/characters/{r.json()['id']}/notes")).json()
    assert notes[0]["campaign_id"] is None


async def test_campaigns_list(client, test_session_factory):
    camp, cid = await _enrolled(client, test_session_factory)
    # nota che referenzia una campagna ora cancellata + una esistente non iscritta
    act(GM_ID)
    gone = await _new_campaign(client, "Sparita")
    async with test_session_factory() as s:
        c = (await s.execute(select(Character).where(Character.id == cid))).scalar_one()
        c.notes = {
            "A": {"body": "a", "campaign_id": camp["id"]},
            "B": {"body": "b", "campaign_id": gone["id"]},
            "C": {"body": "c", "campaign_id": 424242},
        }
        await s.commit()
    act(PLAYER_ID)
    r = await client.get(f"/characters/{cid}/notes/campaigns")
    assert r.status_code == 200
    assert sorted((x["id"], x["name"], x["current"]) for x in r.json()) == sorted([
        (camp["id"], camp["name"], True), (gone["id"], "Sparita", False),
    ])
    act(GM_ID)
    assert (await client.get(f"/characters/{cid}/notes/campaigns")).status_code == 403
