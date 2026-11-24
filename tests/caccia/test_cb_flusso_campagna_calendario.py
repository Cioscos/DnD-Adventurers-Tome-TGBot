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


# --- aggiunte del giro del 2026-11-24 ---
from datetime import datetime, timedelta  # noqa: E402

from sqlalchemy import select  # noqa: E402

from core.db.models import CampaignSchedule  # noqa: E402
from tests.integration.test_campaigns_api import STRANGER_ID, _char, _enrolled, _new_campaign, act  # noqa: E402


def _iso_utc(delta: timedelta) -> str:
    return (datetime.utcnow() + delta).replace(microsecond=0).isoformat() + "Z"


async def _post_or_500(client, url, **kw):
    """Un'eccezione non gestita dell'app vale come risposta 500."""
    try:
        return (await client.post(url, **kw)).status_code
    except Exception:  # noqa: BLE001
        return 500


@pytest.mark.caccia(id="CB-137", fonte="invariante: un dato non valido è rifiutato con 422, non con un errore del server",
                    zona="flusso:campagna-calendario", voce="limiti", copre=["POST /campaigns/{campaign_id}/schedule"])
async def test_serata_oltre_l_anno_9999_e_rifiutata(client):
    act(GM_ID)
    camp = await _new_campaign(client)
    for quando in ("9999-12-31T23:00:00Z", "9999-12-31T23:59:59-05:00"):
        assert await _post_or_500(client, f"/campaigns/{camp['id']}/schedule", json={"starts_at": quando}) == 422, quando
    # niente di mezzo rimasto: la lista del calendario si legge ancora
    assert (await client.get(f"/campaigns/{camp['id']}/schedule")).status_code == 200


@pytest.mark.caccia(id="CB-138", fonte="invariante: una richiesta ripetuta non spende due volte (un PG sta in una sola campagna)",
                    zona="flusso:campagna-calendario", voce="ripetizione", copre=["POST /campaigns/enroll"])
async def test_doppia_iscrizione_insieme_una_sola_vale(client, test_session_factory):
    act(GM_ID)
    camp = await _new_campaign(client)
    cid = await _char(test_session_factory, PLAYER_ID)
    act(PLAYER_ID)

    async def prova():
        try:
            return (await client.post("/campaigns/enroll", json={"code": camp["invite_code"], "character_id": cid})).status_code
        except Exception:  # noqa: BLE001
            return 500
    esiti = sorted(await asyncio.gather(*[prova() for _ in range(6)]))
    assert esiti == [200] + [409] * 5
    async with test_session_factory() as s:
        n = len((await s.execute(select(CampaignMember).where(CampaignMember.character_id == cid))).scalars().all())
    assert n == 1


@pytest.mark.caccia(id="CB-139", fonte="invariante: il riepilogo è di chi era al tavolo o è iscritto alla campagna",
                    zona="flusso:campagna-calendario", voce="permessi", copre=["GET /sessions/{session_id}/recap"])
async def test_riepilogo_solo_per_chi_ne_ha_diritto(client, test_session_factory):
    f = test_session_factory
    camp, cid = await _enrolled(client, f)
    altro = await _char(f, 7777, "Bardo")
    act(7777)
    assert (await client.post("/campaigns/enroll", json={"code": camp["invite_code"], "character_id": altro})).status_code == 200
    act(GM_ID)
    sid = (await client.post("/sessions", json={"campaign_id": camp["id"]})).json()["id"]
    act(PLAYER_ID)
    assert (await client.post(f"/campaigns/{camp['id']}/session/join", json={"character_id": cid})).status_code == 200
    act(GM_ID)
    assert (await client.get(f"/sessions/{sid}/recap")).status_code == 404  # sessione ancora aperta
    assert (await client.post(f"/sessions/{sid}/close")).status_code == 204
    esiti = {}
    for uid in (GM_ID, PLAYER_ID, 7777, STRANGER_ID):
        act(uid)
        esiti[uid] = (await client.get(f"/sessions/{sid}/recap")).status_code
    assert esiti == {GM_ID: 200, PLAYER_ID: 200, 7777: 200, STRANGER_ID: 403}


@pytest.mark.caccia(id="CB-140", fonte="invariante: la serata ha lo stesso numero nel riepilogo e nell'elenco della campagna",
                    zona="flusso:campagna-calendario", voce="persistenza",
                    copre=["GET /sessions/{session_id}/recap", "GET /campaigns/{campaign_id}"])
async def test_numero_serata_uguale_in_riepilogo_ed_elenco(client, test_session_factory):
    camp, cid = await _enrolled(client, test_session_factory)
    act(GM_ID)
    ids = []
    for _ in range(3):
        sid = (await client.post("/sessions", json={"campaign_id": camp["id"]})).json()["id"]
        assert (await client.post(f"/sessions/{sid}/close")).status_code == 204
        ids.append(sid)
    elenco = {s["id"]: s["number"] for s in (await client.get(f"/campaigns/{camp['id']}")).json()["sessions"]}
    recap = {sid: (await client.get(f"/sessions/{sid}/recap")).json()["number"] for sid in ids}
    assert elenco == recap == {ids[0]: 1, ids[1]: 2, ids[2]: 3}


@pytest.mark.caccia(id="CB-141", fonte="invariante: togliere un PG dalla campagna lo toglie anche dalla serata aperta",
                    zona="flusso:campagna-calendario", voce="annullamento",
                    copre=["DELETE /campaigns/{campaign_id}/members/{character_id}", "GET /campaigns/active-for-me"])
async def test_pg_tolto_esce_dalla_serata_e_dal_banner(client, test_session_factory):
    camp, cid = await _enrolled(client, test_session_factory)
    act(GM_ID)
    sid = (await client.post("/sessions", json={"campaign_id": camp["id"]})).json()["id"]
    act(PLAYER_ID)
    assert (await client.get("/campaigns/active-for-me")).json()[0]["session_id"] == sid
    assert (await client.post(f"/campaigns/{camp['id']}/session/join", json={"character_id": cid})).status_code == 200
    assert (await client.get("/campaigns/active-for-me")).json() == []
    act(GM_ID)
    assert (await client.delete(f"/campaigns/{camp['id']}/members/{cid}")).status_code == 204
    assert (await client.get(f"/campaigns/{camp['id']}")).json()["members"] == []
    act(PLAYER_ID)
    assert (await client.get(f"/sessions/{sid}/stash")).status_code in (403, 404)
    assert (await client.get("/campaigns/active-for-me")).json() == []  # non è più membro: nessun invito alla serata
    assert (await client.get(f"/campaigns/{camp['id']}")).status_code == 404


@pytest.mark.caccia(id="CB-142", fonte="invariante: eliminata la campagna non resta nulla di suo, i PG restano e si possono iscrivere altrove",
                    zona="flusso:campagna-calendario", voce="annullamento", copre=["DELETE /campaigns/{campaign_id}"])
async def test_campagna_eliminata_non_lascia_orfani(client, test_session_factory):
    f = test_session_factory
    camp, cid = await _enrolled(client, f)
    act(GM_ID)
    await client.post(f"/campaigns/{camp['id']}/schedule", json={"starts_at": _iso_utc(timedelta(days=3))})
    stash_id = (await (client.get(f"/campaigns/{camp['id']}"))).json()["stash"]
    assert stash_id is not None
    sid = (await client.post("/sessions", json={"campaign_id": camp["id"]})).json()["id"]
    assert (await client.delete(f"/campaigns/{camp['id']}")).status_code == 409  # serata aperta
    await client.post(f"/sessions/{sid}/close")
    assert (await client.delete(f"/campaigns/{camp['id']}")).status_code == 204
    async with f() as s:
        assert (await s.execute(select(CampaignSchedule))).scalars().all() == []
        assert (await s.execute(select(CampaignMember))).scalars().all() == []
        assert (await s.get(Character, cid)) is not None
        assert (await s.execute(select(Character).where(Character.user_id == 0))).scalars().all() == []
    act(GM_ID)
    nuova = await _new_campaign(client, "Nuova")
    act(PLAYER_ID)
    assert (await client.post("/campaigns/enroll", json={"code": nuova["invite_code"], "character_id": cid})).status_code == 200
    act(GM_ID)
    assert (await client.get(f"/sessions/{sid}/recap")).status_code == 200  # il riepilogo del master resta


@pytest.mark.caccia(id="CB-143", fonte="CLAUDE.md: ogni endpoint verifica la proprietà; il codice invito lo vede solo il master",
                    zona="flusso:campagna-calendario", voce="permessi",
                    copre=["PATCH /campaigns/{campaign_id}", "DELETE /campaigns/{campaign_id}", "POST /campaigns/{campaign_id}/invite-code",
                           "POST /campaigns/{campaign_id}/schedule", "PATCH /campaigns/{campaign_id}/members/{character_id}"])
async def test_giocatore_non_fa_cose_da_master(client, test_session_factory):
    f = test_session_factory
    camp, cid = await _enrolled(client, f)
    altro = await _char(f, 7777, "Bardo")
    act(7777)
    await client.post("/campaigns/enroll", json={"code": camp["invite_code"], "character_id": altro})
    act(PLAYER_ID)
    base = f"/campaigns/{camp['id']}"
    assert (await client.patch(base, json={"name": "X"})).status_code == 403
    assert (await client.delete(base)).status_code == 403
    assert (await client.post(f"{base}/invite-code")).status_code == 403
    assert (await client.post(f"{base}/schedule", json={"starts_at": _iso_utc(timedelta(days=2))})).status_code == 403
    assert (await client.patch(f"{base}/members/{altro}", json={"status": "dead"})).status_code == 403  # PG di un altro giocatore
    assert (await client.delete(f"{base}/members/{altro}")).status_code == 403
    det = (await client.get(base)).json()
    assert det["invite_code"] is None and det["name"] == "Saga"
    # un estraneo non vede neanche che esiste
    act(STRANGER_ID)
    assert (await client.get(f"{base}/schedule")).status_code == 404
    assert (await client.patch(base, json={"name": "X"})).status_code == 404


@pytest.mark.caccia(id="CB-144", fonte="invariante: un nome vuoto o solo spazi non è accettato, 120 caratteri sì e 121 no",
                    zona="flusso:campagna-calendario", voce="limiti", copre=["POST /campaigns", "PATCH /campaigns/{campaign_id}"])
async def test_nome_campagna_limiti(client):
    act(GM_ID)
    for brutto in ("", "   ", "\t\n", "x" * 121):
        assert (await client.post("/campaigns", json={"name": brutto})).status_code == 422, repr(brutto)
    ok = await client.post("/campaigns", json={"name": "  " + "è" * 120 + "  "})
    assert ok.status_code == 201 and ok.json()["name"] == "è" * 120
    cid = ok.json()["id"]
    for brutto in ("   ", "y" * 121):
        assert (await client.patch(f"/campaigns/{cid}", json={"name": brutto})).status_code == 422, repr(brutto)
    assert (await client.get(f"/campaigns/{cid}")).json()["name"] == "è" * 120


@pytest.mark.caccia(id="CB-145", fonte="invariante: la serata ha data con fuso, nota ≤200 caratteri, nota vuota = nessuna nota",
                    zona="flusso:campagna-calendario", voce="limiti", copre=["POST /campaigns/{campaign_id}/schedule", "PATCH /campaigns/{campaign_id}/schedule/{sid}"])
async def test_calendario_limiti_di_data_e_nota(client):
    act(GM_ID)
    camp = await _new_campaign(client)
    url = f"/campaigns/{camp['id']}/schedule"
    domani = datetime.utcnow().replace(microsecond=0) + timedelta(days=2)
    assert (await client.post(url, json={"starts_at": domani.isoformat()})).status_code == 422  # senza fuso
    assert (await client.post(url, json={"starts_at": "non una data"})).status_code == 422
    assert (await client.post(url, json={"starts_at": _iso_utc(timedelta(days=2)), "note": "n" * 201})).status_code == 422
    # 22:00 a +02:00 = 20:00 UTC
    r = await client.post(url, json={"starts_at": domani.strftime("%Y-%m-%dT22:00:00+02:00"), "note": "  è" + "n" * 198 + "  "})
    assert r.status_code == 201, r.text
    assert r.json()["starts_at"] == domani.strftime("%Y-%m-%dT20:00:00") and len(r.json()["note"]) == 199
    sid = r.json()["id"]
    r = await client.patch(f"{url}/{sid}", json={"note": "   "})
    assert r.json()["note"] is None and r.json()["starts_at"] == domani.strftime("%Y-%m-%dT20:00:00")
    assert (await client.patch(f"{url}/{sid}", json={"starts_at": _iso_utc(timedelta(hours=-1))})).status_code == 422
    assert (await client.get(url)).json()[0]["starts_at"] == domani.strftime("%Y-%m-%dT20:00:00")


@pytest.mark.caccia(id="CB-146", fonte="invariante: la serata programmata finisce «fatta» quando il master apre la sessione vicina",
                    zona="flusso:campagna-calendario", voce="normale",
                    copre=["POST /sessions", "GET /campaigns/{campaign_id}/schedule"])
async def test_serata_programmata_si_collega_alla_sessione(client):
    act(GM_ID)
    camp = await _new_campaign(client)
    url = f"/campaigns/{camp['id']}/schedule"
    lontana = (await client.post(url, json={"starts_at": _iso_utc(timedelta(days=5))})).json()["id"]
    vicina = (await client.post(url, json={"starts_at": _iso_utc(timedelta(hours=2))})).json()["id"]
    sid = (await client.post("/sessions", json={"campaign_id": camp["id"]})).json()["id"]
    righe = {r["id"]: r for r in (await client.get(url)).json()}
    assert righe[vicina]["status"] == "done" and righe[vicina]["session_id"] == sid
    assert righe[lontana]["status"] == "planned" and righe[lontana]["session_id"] is None
    await client.post(f"/sessions/{sid}/close")
    sid2 = (await client.post("/sessions", json={"campaign_id": camp["id"]})).json()["id"]  # seconda sessione: la riga fatta non si ricollega
    righe = {r["id"]: r for r in (await client.get(url)).json()}
    assert righe[vicina]["session_id"] == sid and righe[lontana]["session_id"] is None and sid2 != sid


@pytest.mark.caccia(id="CB-147", fonte="invariante: un PG morto non entra in serata né dal codice né dalla campagna e non riceve l'invito",
                    zona="flusso:campagna-calendario", voce="interazione",
                    copre=["PATCH /campaigns/{campaign_id}/members/{character_id}", "POST /campaigns/{campaign_id}/session/join", "POST /sessions/join", "GET /campaigns/active-for-me"])
async def test_pg_morto_non_entra_in_serata(client, test_session_factory):
    camp, cid = await _enrolled(client, test_session_factory)
    act(GM_ID)
    sess = (await client.post("/sessions", json={"campaign_id": camp["id"]})).json()
    act(PLAYER_ID)
    assert (await client.patch(f"/campaigns/{camp['id']}/members/{cid}", json={"status": "dead"})).status_code == 200
    r = await client.post(f"/campaigns/{camp['id']}/session/join", json={"character_id": cid})
    assert (r.status_code, r.json()["detail"]) == (422, "character_dead")
    r = await client.post("/sessions/join", json={"code": sess["code"], "character_id": cid})
    assert (r.status_code, r.json()["detail"]) == (422, "character_dead")
    assert (await client.get("/campaigns/active-for-me")).json() == []
    assert (await client.get(f"/campaigns/{camp['id']}")).json()["my_last_character_id"] is None


async def _esito(coro):
    try:
        return (await coro).status_code
    except Exception:  # noqa: BLE001
        return 500


@pytest.mark.caccia(id="CB-148", fonte="invariante: una richiesta ripetuta non spende due volte (una sola serata aperta per campagna)",
                    zona="flusso:campagna-calendario", voce="ripetizione", copre=["POST /sessions"])
async def test_doppio_inizio_serata_ne_apre_una_sola(client, test_session_factory):
    act(GM_ID)
    camp = await _new_campaign(client)
    esiti = sorted(await asyncio.gather(*[_esito(client.post("/sessions", json={"campaign_id": camp["id"]})) for _ in range(5)]))
    assert esiti == [201] + [409] * 4
    async with test_session_factory() as s:
        aperte = (await s.execute(select(GameSession).where(GameSession.campaign_id == camp["id"],
                                                            GameSession.status == SessionStatus.ACTIVE))).scalars().all()
    assert len(aperte) == 1


@pytest.mark.caccia(id="CB-149", fonte="invariante: una richiesta ripetuta non spende due volte (un PG siede una volta sola al tavolo)",
                    zona="flusso:campagna-calendario", voce="ripetizione", copre=["POST /campaigns/{campaign_id}/session/join"])
async def test_doppio_ingresso_in_serata_siede_una_volta(client, test_session_factory):
    camp, cid = await _enrolled(client, test_session_factory)
    act(GM_ID)
    sid = (await client.post("/sessions", json={"campaign_id": camp["id"]})).json()["id"]
    act(PLAYER_ID)
    esiti = sorted(await asyncio.gather(*[_esito(client.post(f"/campaigns/{camp['id']}/session/join", json={"character_id": cid})) for _ in range(5)]))
    assert 500 not in esiti, esiti
    assert esiti == [200] + [409] * 4
    async with test_session_factory() as s:
        posti = (await s.execute(select(SessionParticipant).where(SessionParticipant.session_id == sid,
                                                                  SessionParticipant.user_id == PLAYER_ID))).scalars().all()
    assert len(posti) == 1


@pytest.mark.caccia(id="CB-150", fonte="invariante: il codice invito rigenerato invalida il vecchio; il codice si scrive anche in minuscolo",
                    zona="flusso:campagna-calendario", voce="persistenza", copre=["POST /campaigns/{campaign_id}/invite-code", "POST /campaigns/enroll"])
async def test_codice_rigenerato_invalida_il_vecchio(client, test_session_factory):
    f = test_session_factory
    act(GM_ID)
    camp = await _new_campaign(client)
    vecchio = camp["invite_code"]
    nuovo = (await client.post(f"/campaigns/{camp['id']}/invite-code")).json()["invite_code"]
    assert nuovo != vecchio and len(nuovo) == 8
    cid = await _char(f, PLAYER_ID)
    act(PLAYER_ID)
    r = await client.post("/campaigns/enroll", json={"code": vecchio, "character_id": cid})
    assert (r.status_code, r.json()["detail"]) == (404, "campaign_not_found")
    altrui = await _char(f, STRANGER_ID)
    r = await client.post("/campaigns/enroll", json={"code": nuovo.lower(), "character_id": altrui})
    assert (r.status_code, r.json()["detail"]) == (403, "not_your_character")
    r = await client.post("/campaigns/enroll", json={"code": " " + nuovo.lower() + " ", "character_id": cid})
    assert r.status_code == 200
    act(GM_ID)
    assert (await client.get(f"/campaigns/{camp['id']}")).json()["invite_code"] == nuovo


@pytest.mark.caccia(id="CB-151", fonte="invariante: la serata è «saltata» solo dopo la finestra di 12 ore per collegare la sessione",
                    zona="flusso:campagna-calendario", voce="limiti", copre=["GET /campaigns/{campaign_id}/schedule"])
async def test_serata_saltata_dopo_dodici_ore(client, test_session_factory):
    act(GM_ID)
    camp = await _new_campaign(client)
    ora = datetime.utcnow().replace(microsecond=0)
    async with test_session_factory() as s:
        for ore in (-11, -13):
            s.add(CampaignSchedule(campaign_id=camp["id"], starts_at=(ora + timedelta(hours=ore)).isoformat(), created_at=ora.isoformat()))
        await s.commit()
    stati = [r["status"] for r in (await client.get(f"/campaigns/{camp['id']}/schedule")).json()]
    assert stati == ["skipped", "planned"]  # ordinate per data: -13 h poi -11 h


@pytest.mark.caccia(id="CB-152", fonte="invariante: chi esce e rientra nella serata compare una sola volta nel riepilogo, con i suoi dati",
                    zona="flusso:campagna-calendario", voce="persistenza", copre=["POST /sessions/{session_id}/leave", "GET /sessions/{session_id}/recap"])
async def test_uscita_e_rientro_un_solo_pg_nel_riepilogo(client, test_session_factory):
    camp, cid = await _enrolled(client, test_session_factory)
    act(GM_ID)
    sid = (await client.post("/sessions", json={"campaign_id": camp["id"]})).json()["id"]
    act(PLAYER_ID)
    await client.post(f"/campaigns/{camp['id']}/session/join", json={"character_id": cid})
    for op, v in (("set_max", 20), ("set_current", 20), ("damage", 5)):
        await client.patch(f"/characters/{cid}/hp", json={"op": op, "value": v})
    await client.post(f"/sessions/{sid}/leave")
    await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 2})
    assert (await client.post(f"/campaigns/{camp['id']}/session/join", json={"character_id": cid})).status_code == 200
    await client.patch(f"/characters/{cid}/hp", json={"op": "heal", "value": 4})
    act(GM_ID)
    await client.post(f"/sessions/{sid}/close")
    rec = (await client.get(f"/sessions/{sid}/recap")).json()
    assert [(c["character_id"], c["damage_taken"], c["healed"]) for c in rec["characters"]] == [(cid, 7, 4)]


@pytest.mark.caccia(id="CB-153", fonte="invariante: solo il master apre e chiude la serata della sua campagna",
                    zona="flusso:campagna-calendario", voce="permessi", copre=["POST /sessions", "POST /sessions/{session_id}/close", "GET /campaigns/{campaign_id}/schedule"])
async def test_serata_di_campagna_solo_il_master(client, test_session_factory):
    camp, cid = await _enrolled(client, test_session_factory)
    act(PLAYER_ID)
    r = await client.post("/sessions", json={"campaign_id": camp["id"]})
    assert (r.status_code, r.json()["detail"]) == (403, "gm_only")
    act(GM_ID)
    sid = (await client.post("/sessions", json={"campaign_id": camp["id"]})).json()["id"]
    act(PLAYER_ID)
    await client.post(f"/campaigns/{camp['id']}/session/join", json={"character_id": cid})
    assert (await client.post(f"/sessions/{sid}/close")).status_code == 403
    act(STRANGER_ID)
    assert (await client.post(f"/sessions/{sid}/close")).status_code == 403
    act(GM_ID)
    assert (await client.get(f"/campaigns/{camp['id']}")).json()["active_session_id"] == sid


async def _hp(client, cid, *ops):
    for op, v in ops:
        assert (await client.patch(f"/characters/{cid}/hp", json={"op": op, "value": v})).status_code == 200


@pytest.mark.caccia(id="CB-159", fonte="invariante: il riepilogo racconta chi ha giocato la serata", zona="flusso:campagna-calendario",
                    voce="annullamento", copre=["DELETE /campaigns/{campaign_id}/members/{character_id}", "GET /sessions/{session_id}/recap"])
async def test_pg_tolto_resta_nel_riepilogo(client, test_session_factory):
    camp, cid = await _enrolled(client, test_session_factory)
    act(GM_ID)
    sid = (await client.post("/sessions", json={"campaign_id": camp["id"]})).json()["id"]
    act(PLAYER_ID)
    assert (await client.post(f"/campaigns/{camp['id']}/session/join", json={"character_id": cid})).status_code == 200
    await _hp(client, cid, ("set_max", 20), ("set_current", 20), ("damage", 7))
    act(GM_ID)
    assert (await client.delete(f"/campaigns/{camp['id']}/members/{cid}")).status_code == 204
    await client.post(f"/sessions/{sid}/close")
    rec = (await client.get(f"/sessions/{sid}/recap")).json()
    assert [(c["character_id"], c["damage_taken"]) for c in rec["characters"]] == [(cid, 7)]


@pytest.mark.caccia(id="CB-160", fonte="invariante: il riepilogo di un PG parte da quando si siede", zona="flusso:campagna-calendario",
                    voce="interazione", copre=["POST /campaigns/{campaign_id}/session/join", "GET /sessions/{session_id}/recap"])
async def test_riepilogo_parte_da_quando_il_pg_si_siede(client, test_session_factory):
    camp, cid = await _enrolled(client, test_session_factory)
    act(GM_ID)
    sid = (await client.post("/sessions", json={"campaign_id": camp["id"]})).json()["id"]
    act(PLAYER_ID)
    await _hp(client, cid, ("set_max", 20), ("set_current", 20), ("damage", 5), ("heal", 2))
    assert (await client.post(f"/campaigns/{camp['id']}/session/join", json={"character_id": cid})).status_code == 200
    await _hp(client, cid, ("damage", 1))
    act(GM_ID)
    await client.post(f"/sessions/{sid}/close")
    c = (await client.get(f"/sessions/{sid}/recap")).json()["characters"][0]
    assert (c["damage_taken"], c["healed"]) == (1, 0)


@pytest.mark.caccia(id="CB-161", fonte="invariante: una serata già giocata non cambia data", zona="flusso:campagna-calendario",
                    voce="limiti", copre=["PATCH /campaigns/{campaign_id}/schedule/{sid}"])
async def test_serata_fatta_non_si_sposta(client):
    act(GM_ID)
    camp = await _new_campaign(client)
    url = f"/campaigns/{camp['id']}/schedule"
    riga = (await client.post(url, json={"starts_at": _iso_utc(timedelta(hours=2))})).json()["id"]
    await client.post("/sessions", json={"campaign_id": camp["id"]})
    assert (await client.get(url)).json()[0]["status"] == "done"
    r = await client.patch(f"{url}/{riga}", json={"starts_at": _iso_utc(timedelta(days=10))})
    assert r.status_code in (409, 422), r.text


@pytest.mark.caccia(id="CB-162", fonte="invariante: dopo l'eliminazione di una campagna nessun riferimento punta al suo id", zona="flusso:campagna-calendario",
                    voce="persistenza", copre=["DELETE /campaigns/{campaign_id}", "GET /sessions/{session_id}/recap"])
async def test_riepilogo_non_punta_alla_campagna_eliminata(client):
    act(GM_ID)
    camp = await _new_campaign(client)
    sid = (await client.post("/sessions", json={"campaign_id": camp["id"]})).json()["id"]
    await client.post(f"/sessions/{sid}/close")
    assert (await client.delete(f"/campaigns/{camp['id']}")).status_code == 204
    assert (await client.get(f"/sessions/{sid}/recap")).json()["campaign_id"] is None


@pytest.mark.caccia(id="CB-766", fonte="invariante: il riepilogo racconta chi ha giocato la serata", zona="flusso:campagna-calendario",
                    voce="annullamento", copre=["DELETE /characters/{char_id}", "GET /sessions/{session_id}/recap"])
@pytest.mark.parametrize("uscito", [False, True])
async def test_pg_eliminato_resta_nel_riepilogo(client, test_session_factory, uscito):
    camp, cid = await _enrolled(client, test_session_factory)
    act(GM_ID)
    sid = (await client.post("/sessions", json={"campaign_id": camp["id"]})).json()["id"]
    act(PLAYER_ID)
    assert (await client.post(f"/campaigns/{camp['id']}/session/join", json={"character_id": cid})).status_code == 200
    await _hp(client, cid, ("set_max", 20), ("set_current", 20), ("damage", 7))
    if uscito:  # si alza prima, poi elimina il personaggio a serata ancora aperta
        assert (await client.post(f"/sessions/{sid}/leave")).status_code == 204
    nome = (await client.get(f"/characters/{cid}")).json()["name"]
    assert (await client.delete(f"/characters/{cid}")).status_code == 204
    # SQLite riusa l'id: il PG nuovo non eredita la serata di quello eliminato
    await client.post("/characters", json={"name": "Nuovo"})
    act(GM_ID)
    assert (await client.post(f"/sessions/{sid}/close")).status_code == 204
    rec = (await client.get(f"/sessions/{sid}/recap")).json()
    assert [(c["name"], c["damage_taken"]) for c in rec["characters"]] == [(nome, 7)]
    act(PLAYER_ID)
    assert (await client.get(f"/sessions/{sid}/recap")).status_code == 200
