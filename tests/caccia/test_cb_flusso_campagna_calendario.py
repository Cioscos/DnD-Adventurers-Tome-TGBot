"""Controlli della zona flusso:campagna-calendario."""
import asyncio

import pytest

from api.locks import _LOCKS
from core.db.models import CampaignMember, Character, GameSession, SessionParticipant, SessionRole, SessionStatus
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user


@pytest.mark.caccia(id="CB-007", fonte="invariante: una nota non mostra una campagna a cui il PG non ha partecipato",
                    zona="flusso:campagna-calendario", voce="annullamento",
                    copre=["DELETE /campaigns/{campaign_id}", "GET /characters/{char_id}/notes"])
async def test_campagna_eliminata_scollega_le_note(client, test_session_factory):
    as_user(PLAYER_ID)
    cid = (await client.post("/characters", json={"name": "P"})).json()["id"]
    as_user(GM_ID)
    a = (await client.post("/campaigns", json={"name": "A"})).json()["id"]
    async with test_session_factory() as s:
        s.add(CampaignMember(campaign_id=a, character_id=cid, user_id=PLAYER_ID, status="active", joined_at="2026-06-09T10:00:00"))
        await s.commit()
    as_user(PLAYER_ID)
    await client.post(f"/characters/{cid}/notes", json={"title": "n", "body": "x", "tags": ["t"], "campaign_id": a})
    as_user(GM_ID)
    assert (await client.delete(f"/campaigns/{a}")).status_code == 204
    await client.post("/campaigns", json={"name": "B segreta"})
    as_user(PLAYER_ID)
    nota = (await client.get(f"/characters/{cid}/notes")).json()[0]
    assert (nota["campaign_id"], nota["campaign_name"]) == (None, None)
    assert (nota["body"], nota["tags"]) == ("x", ["t"])
    assert (await client.get(f"/characters/{cid}/notes/campaigns")).json() == []


@pytest.mark.caccia(id="CB-020", fonte="invariante: riepilogo e campagna danno la stessa durata", zona="flusso:campagna-calendario",
                    voce="persistenza", copre=["POST /sessions/{session_id}/leave", "GET /campaigns/{campaign_id}"])
async def test_durata_dopo_l_uscita_del_master(client, test_session_factory):
    as_user(GM_ID)
    camp = (await client.post("/campaigns", json={"name": "A"})).json()["id"]
    async with test_session_factory() as s:
        gs = GameSession(code="ZZZ111", gm_user_id=GM_ID, status=SessionStatus.ACTIVE, campaign_id=camp,
                         created_at="2026-06-09T20:00:00", last_activity_at="2026-06-09T21:00:00")
        s.add(gs)
        await s.flush()
        s.add(SessionParticipant(session_id=gs.id, user_id=GM_ID, role=SessionRole.GAME_MASTER, joined_at="2026-06-09T20:00:00"))
        await s.commit()
        sid = gs.id
    await client.post(f"/sessions/{sid}/leave")
    assert (await client.get(f"/sessions/{sid}/recap")).json()["duration_seconds"] == 3600
    assert (await client.get(f"/campaigns/{camp}")).json()["sessions"][0]["duration_seconds"] == 3600


@pytest.mark.caccia(id="CB-036", fonte="invariante: due richieste insieme non si sovrascrivono", zona="flusso:campagna-calendario",
                    voce="ripetizione", copre=["DELETE /campaigns/{campaign_id}", "PATCH /characters/{char_id}/notes/{title:path}"])
async def test_eliminare_la_campagna_aspetta_la_nota_in_corso(client, test_session_factory):
    as_user(PLAYER_ID)
    cid = (await client.post("/characters", json={"name": "P"})).json()["id"]
    as_user(GM_ID)
    a = (await client.post("/campaigns", json={"name": "A"})).json()["id"]
    async with test_session_factory() as s:
        s.add(CampaignMember(campaign_id=a, character_id=cid, user_id=PLAYER_ID, status="active", joined_at="2026-06-09T10:00:00"))
        await s.commit()
    as_user(PLAYER_ID)
    await client.post(f"/characters/{cid}/notes", json={"title": "n", "body": "x", "campaign_id": a})
    as_user(GM_ID)
    async with _LOCKS[id(asyncio.get_running_loop()), f"char:{cid}"]:  # una scrittura del giocatore è in corso
        elimina = asyncio.create_task(client.delete(f"/campaigns/{a}"))
        await asyncio.sleep(0.3)
        assert not elimina.done()
        async with test_session_factory() as s:
            pg = await s.get(Character, cid)
            pg.notes = {**pg.notes, "nuova": {"body": "y", "tags": [], "campaign_id": a}}
            await s.commit()
    assert (await elimina).status_code == 204
    as_user(PLAYER_ID)
    note = (await client.get(f"/characters/{cid}/notes")).json()
    assert [(n["title"], n["campaign_id"]) for n in note] == [("n", None), ("nuova", None)]
