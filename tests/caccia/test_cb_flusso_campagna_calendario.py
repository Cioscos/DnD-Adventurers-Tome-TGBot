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


@pytest.mark.caccia(id="CB-769", fonte="invariante: il PG nuovo non eredita nulla da quello eliminato, anche se SQLite riusa l'id", zona="flusso:campagna-calendario",
                    voce="interazione", copre=["DELETE /characters/{char_id}", "GET /sessions/{session_id}/recap"])
async def test_id_riusato_non_mescola_le_voci_del_riepilogo(client, test_session_factory):
    from core.db.models import CharacterHistory

    camp, cid = await _enrolled(client, test_session_factory)
    act(GM_ID)
    sid = (await client.post("/sessions", json={"campaign_id": camp["id"]})).json()["id"]
    act(PLAYER_ID)
    await client.post(f"/campaigns/{camp['id']}/session/join", json={"character_id": cid})
    act(GM_ID)
    altro = (await client.post("/characters", json={"name": "Curato"})).json()["id"]
    async with test_session_factory() as s:
        gs = await s.get(GameSession, sid)
        s.add(SessionParticipant(session_id=sid, user_id=GM_ID + 7, character_id=altro, role=SessionRole.PLAYER, joined_at=gs.created_at))
        s.add(CharacterHistory(character_id=altro, event_type="hp_change", description="x", timestamp=gs.created_at,
                               meta={"op": "HEAL", "amount": 6, "by_id": cid}))
        await s.commit()
    act(PLAYER_ID)
    assert (await client.delete(f"/characters/{cid}")).status_code == 204
    async with test_session_factory() as s:  # il PG nuovo nasce con lo stesso id e si siede
        s.add(Character(id=cid, user_id=PLAYER_ID, name="Nuovo"))
        await s.flush()
        s.add(CampaignMember(campaign_id=camp["id"], character_id=cid, user_id=PLAYER_ID, status="active", joined_at="2026-06-09T10:00:00"))
        await s.commit()
    assert (await client.post(f"/campaigns/{camp['id']}/session/join", json={"character_id": cid})).status_code == 200
    act(GM_ID)
    await client.post(f"/sessions/{sid}/close")
    pg = (await client.get(f"/sessions/{sid}/recap")).json()["characters"]
    assert len({c["character_id"] for c in pg}) == len(pg) == 3
    assert {c["name"]: c["healing_given"] for c in pg} == {"Eroe": 6, "Nuovo": 0, "Curato": 0}


# --- aggiunte del giro del 2026-11-24 (seconda parte) ---
import re  # noqa: E402

from api.services import telegram_notify  # noqa: E402,F401
from api.services.recap import format_recap_text  # noqa: E402
from api.tasks import campaign_reminders  # noqa: E402
from tests.integration._telegram_stub import install_fake_telegram  # noqa: E402

_CHIAVI_PG = {"character_id", "name", "player_name", "class_summary", "level", "dice", "damage_taken", "healed", "downed",
              "death_saves", "spells_cast", "slots_used", "rests", "conditions", "condition_levels", "healing_given"}
_CHIAVI_RECAP = {"version", "session_id", "campaign_id", "campaign_name", "number", "started_at", "ended_at", "duration_seconds",
                 "characters", "combat", "items", "lore", "places", "highlights"}


async def _apri_serata(client, camp_id, uid_pg):
    """Il master apre la serata; `uid_pg` = [(utente, personaggio)] si siedono. Restituisce l'id della sessione."""
    act(GM_ID)
    sid = (await client.post("/sessions", json={"campaign_id": camp_id})).json()["id"]
    for uid, pg in uid_pg:
        act(uid)
        r = await client.post(f"/campaigns/{camp_id}/session/join", json={"character_id": pg})
        assert r.status_code == 200, r.text
    return sid


def _messaggi(cap):
    return [(c["json"]["chat_id"], c["json"]["text"]) for c in cap if str(c["url"]).endswith("/sendMessage")]


@pytest.mark.caccia(id="CB-873", fonte="webapp/src/types/index.ts SessionRecap: il frontend legge gli stessi campi per ogni PG, anche eliminato",
                    zona="flusso:campagna-calendario", voce="contratto",
                    copre=["GET /sessions/{session_id}/recap", "DELETE /characters/{char_id}"])
async def test_riepilogo_ha_i_campi_letti_dal_frontend_anche_per_il_pg_eliminato(client, test_session_factory):
    f = test_session_factory
    camp, cid = await _enrolled(client, f)
    altro = await _char(f, 7777, "Bardo")
    act(7777)
    assert (await client.post("/campaigns/enroll", json={"code": camp["invite_code"], "character_id": altro})).status_code == 200
    sid = await _apri_serata(client, camp["id"], [(PLAYER_ID, cid), (7777, altro)])
    act(PLAYER_ID)
    await _hp(client, cid, ("set_max", 20), ("set_current", 20), ("damage", 4))
    assert (await client.delete(f"/characters/{cid}")).status_code == 204
    act(GM_ID)
    assert (await client.post(f"/sessions/{sid}/close")).status_code == 204
    rec = (await client.get(f"/sessions/{sid}/recap")).json()
    assert set(rec) == _CHIAVI_RECAP
    assert len(rec["characters"]) == 2
    for c in rec["characters"]:
        assert set(c) == _CHIAVI_PG, c["name"]
        assert set(c["dice"]) == {"rolls", "nat20", "nat1", "highest"}
        assert set(c["death_saves"]) == {"successes", "failures"} and set(c["rests"]) == {"short", "long"}
    assert set(rec["combat"]) >= {"encounters", "rounds", "monsters", "defeated", "damage_dealt"}
    assert set(rec["items"]) == {"gm_grants", "trades", "stash"}


@pytest.mark.caccia(id="CB-874", fonte="CLAUDE.md: promemoria Telegram 24h e 1h prima della serata; docstring del task: il promemoria del giorno non scatta dopo quello dell'ora",
                    zona="flusso:campagna-calendario", voce="normale", copre=["POST /campaigns/{campaign_id}/schedule"])
async def test_promemoria_del_giorno_e_dell_ora_una_volta_sola(client, test_session_factory, monkeypatch):
    f = test_session_factory
    cap = install_fake_telegram(monkeypatch)
    monkeypatch.setenv("SEND_CAMPAIGN_MESSAGES", "1")
    camp, cid = await _enrolled(client, f)
    act(GM_ID)
    r = await client.post(f"/campaigns/{camp['id']}/schedule", json={"starts_at": _iso_utc(timedelta(hours=20)), "note": "porta i dadi"})
    assert r.status_code == 201
    now = datetime.utcnow()
    esiti = [await campaign_reminders._remind_once(now + timedelta(minutes=m), f) for m in (0, 5, 19 * 60 + 10, 19 * 60 + 15)]
    assert esiti == [1, 0, 1, 0]
    destinatari = sorted(u for u, _t in _messaggi(cap))
    assert destinatari == sorted([GM_ID, PLAYER_ID] * 2)
    assert all("Saga" in t and "porta i dadi" in t for _u, t in _messaggi(cap))


@pytest.mark.caccia(id="CB-875", fonte="invariante: spostare una serata riarma i promemoria, cambiare solo la nota no",
                    zona="flusso:campagna-calendario", voce="persistenza", copre=["PATCH /campaigns/{campaign_id}/schedule/{sid}"])
async def test_promemoria_dopo_modifica_della_serata(client, test_session_factory, monkeypatch):
    f = test_session_factory
    install_fake_telegram(monkeypatch)
    monkeypatch.setenv("SEND_CAMPAIGN_MESSAGES", "1")
    camp, _cid = await _enrolled(client, f)
    act(GM_ID)
    url = f"/campaigns/{camp['id']}/schedule"
    sid = (await client.post(url, json={"starts_at": _iso_utc(timedelta(hours=20))})).json()["id"]
    now = datetime.utcnow()
    assert await campaign_reminders._remind_once(now, f) == 1
    assert (await client.patch(f"{url}/{sid}", json={"note": "nuova nota"})).status_code == 200
    assert await campaign_reminders._remind_once(now + timedelta(minutes=5), f) == 0  # la nota non riarma
    assert (await client.patch(f"{url}/{sid}", json={"starts_at": _iso_utc(timedelta(hours=26))})).status_code == 200
    assert await campaign_reminders._remind_once(now + timedelta(minutes=10), f) == 0  # fuori dalle 24 ore
    assert await campaign_reminders._remind_once(now + timedelta(hours=3), f) == 1  # spostata: il promemoria del giorno torna
    assert (await client.patch(f"{url}/{sid}", json={"starts_at": _iso_utc(timedelta(hours=30))})).status_code == 200
    assert await campaign_reminders._remind_once(now + timedelta(hours=3, minutes=5), f) == 0
    assert await campaign_reminders._remind_once(now + timedelta(hours=29, minutes=30), f) == 1  # l'ora: dopo due spostamenti


@pytest.mark.caccia(id="CB-876", fonte="invariante: una serata cancellata non manda più promemoria", zona="flusso:campagna-calendario",
                    voce="annullamento", copre=["DELETE /campaigns/{campaign_id}/schedule/{sid}"])
async def test_serata_cancellata_non_ricorda_piu(client, test_session_factory, monkeypatch):
    f = test_session_factory
    cap = install_fake_telegram(monkeypatch)
    monkeypatch.setenv("SEND_CAMPAIGN_MESSAGES", "1")
    camp, _cid = await _enrolled(client, f)
    act(GM_ID)
    url = f"/campaigns/{camp['id']}/schedule"
    sid = (await client.post(url, json={"starts_at": _iso_utc(timedelta(hours=20))})).json()["id"]
    now = datetime.utcnow()
    assert await campaign_reminders._remind_once(now, f) == 1
    assert (await client.delete(f"{url}/{sid}")).status_code == 204
    cap.clear()
    assert await campaign_reminders._remind_once(now + timedelta(hours=19, minutes=30), f) == 0
    assert _messaggi(cap) == []
    assert (await client.get(url)).json() == []


@pytest.mark.caccia(id="CB-877", fonte="invariante: una richiesta ripetuta non spende due volte (il riepilogo parte una volta a persona)",
                    zona="flusso:campagna-calendario", voce="ripetizione",
                    copre=["POST /sessions/{session_id}/close", "POST /sessions/{session_id}/leave"])
async def test_chiusura_ripetuta_manda_il_riepilogo_una_volta(client, test_session_factory, monkeypatch):
    f = test_session_factory
    cap = install_fake_telegram(monkeypatch)
    monkeypatch.setenv("SEND_CAMPAIGN_MESSAGES", "1")
    camp, cid = await _enrolled(client, f)
    sid = await _apri_serata(client, camp["id"], [(PLAYER_ID, cid)])
    act(GM_ID)
    cap.clear()

    async def prova(coro):
        try:
            return (await coro).status_code
        except Exception:  # noqa: BLE001
            return 500
    esiti = await asyncio.gather(prova(client.post(f"/sessions/{sid}/close")), prova(client.post(f"/sessions/{sid}/close")),
                                 prova(client.post(f"/sessions/{sid}/leave")))
    assert esiti == [204, 204, 204]
    assert sorted(u for u, _t in _messaggi(cap)) == sorted([GM_ID, PLAYER_ID])
    assert (await client.get(f"/sessions/{sid}/recap")).json()["number"] == 1


@pytest.mark.caccia(id="CB-878", fonte="invariante: solo il master della serata condivide il riepilogo; prima della chiusura non c'è nulla da condividere",
                    zona="flusso:campagna-calendario", voce="permessi", copre=["POST /share/recap/{session_id}"])
async def test_condividere_il_riepilogo_solo_il_master(client, test_session_factory, monkeypatch):
    f = test_session_factory
    cap = install_fake_telegram(monkeypatch)
    camp, cid = await _enrolled(client, f)
    sid = await _apri_serata(client, camp["id"], [(PLAYER_ID, cid)])
    act(GM_ID)
    assert (await client.post(f"/share/recap/{sid}")).status_code == 404  # ancora aperta
    assert (await client.post(f"/sessions/{sid}/close")).status_code == 204
    act(8888)  # master di un'altra campagna
    await _new_campaign(client, "Altra")
    esiti = {}
    for uid in (PLAYER_ID, 8888, STRANGER_ID):
        act(uid)
        esiti[uid] = (await client.post(f"/share/recap/{sid}")).status_code
    assert esiti == {PLAYER_ID: 403, 8888: 403, STRANGER_ID: 403}
    assert not [c for c in cap if "savePreparedInlineMessage" in str(c["url"])]
    act(GM_ID)
    r = await client.post(f"/share/recap/{sid}")
    assert r.status_code == 200 and r.json() == {"prepared_message_id": "prep-1"}
    prep = [c for c in cap if "savePreparedInlineMessage" in str(c["url"])]
    assert len(prep) == 1 and prep[0]["json"]["user_id"] == GM_ID


@pytest.mark.caccia(id="CB-879", fonte="invariante: il ruolo è per campagna, non per utente (master qui, giocatore là)",
                    zona="flusso:campagna-calendario", voce="interazione",
                    copre=["GET /campaigns", "GET /campaigns/{campaign_id}", "PATCH /campaigns/{campaign_id}", "POST /campaigns/{campaign_id}/schedule"])
async def test_master_di_una_campagna_e_giocatore_di_un_altra(client, test_session_factory):
    f = test_session_factory
    act(PLAYER_ID)
    a = await _new_campaign(client, "Mia")
    act(GM_ID)
    b = await _new_campaign(client, "Altrui")
    cid = await _char(f, PLAYER_ID)
    act(PLAYER_ID)
    assert (await client.post("/campaigns/enroll", json={"code": b["invite_code"], "character_id": cid})).status_code == 200
    assert {c["name"]: c["is_gm"] for c in (await client.get("/campaigns")).json()} == {"Mia": True, "Altrui": False}
    assert (await client.get(f"/campaigns/{a['id']}")).json()["invite_code"] == a["invite_code"]
    det_b = (await client.get(f"/campaigns/{b['id']}")).json()
    assert det_b["is_gm"] is False and det_b["invite_code"] is None
    base = f"/campaigns/{b['id']}"
    assert (await client.patch(base, json={"name": "X"})).status_code == 403
    assert (await client.post(f"{base}/invite-code")).status_code == 403
    assert (await client.post(f"{base}/schedule", json={"starts_at": _iso_utc(timedelta(days=2))})).status_code == 403
    assert (await client.delete(base)).status_code == 403
    assert (await client.patch(f"/campaigns/{a['id']}", json={"name": "Mia 2"})).status_code == 200
    act(GM_ID)
    assert (await client.get(f"/campaigns/{a['id']}")).status_code == 404  # il master di B non vede la A di lui
    assert (await client.get(f"/campaigns/{b['id']}")).json()["name"] == "Altrui"


@pytest.mark.xfail(strict=True, reason="CB-880 il riepilogo attribuisce i regali per utente: vince l'ultimo PG")
@pytest.mark.caccia(id="CB-880", fonte="invariante: il riepilogo dice a quale PG è andato l'oggetto, anche se il giocatore cambia PG a serata in corso",
                    zona="flusso:campagna-calendario", voce="interazione",
                    copre=["POST /sessions/{session_id}/gm/grant_item", "GET /sessions/{session_id}/recap"])
async def test_regalo_del_master_resta_al_pg_che_lo_ha_ricevuto(client, test_session_factory):
    f = test_session_factory
    camp, a = await _enrolled(client, f)
    b = await _char(f, PLAYER_ID, "Secondo")
    act(PLAYER_ID)
    assert (await client.post("/campaigns/enroll", json={"code": camp["invite_code"], "character_id": b})).status_code == 200
    sid = await _apri_serata(client, camp["id"], [(PLAYER_ID, a)])
    act(GM_ID)
    r = await client.post(f"/sessions/{sid}/gm/grant_item", json={"recipient_user_ids": [PLAYER_ID], "item": {"name": "Pozione", "quantity": 1}})
    assert r.status_code == 201 and r.json()["results"][0]["character_id"] == a
    act(PLAYER_ID)
    assert (await client.post(f"/sessions/{sid}/leave")).status_code == 204
    assert (await client.post(f"/campaigns/{camp['id']}/session/join", json={"character_id": b})).status_code == 200
    act(GM_ID)
    r = await client.post(f"/sessions/{sid}/gm/grant_item", json={"recipient_user_ids": [PLAYER_ID], "item": {"name": "Corda", "quantity": 2}})
    assert r.json()["results"][0]["character_id"] == b
    await client.post(f"/sessions/{sid}/close")
    rec = (await client.get(f"/sessions/{sid}/recap")).json()
    assert [(g["item"], g["to"]) for g in rec["items"]["gm_grants"]] == [("Pozione", "Eroe"), ("Corda", "Secondo")]


@pytest.mark.xfail(strict=True, reason="CB-881 dopo leave il banner propone il PG della serata precedente")
@pytest.mark.caccia(id="CB-881", fonte="invariante: dopo essere usciti dalla serata il banner propone il PG con cui si stava giocando",
                    zona="flusso:campagna-calendario", voce="persistenza", copre=["GET /campaigns/active-for-me", "GET /campaigns/{campaign_id}"])
async def test_rientro_propone_il_pg_appena_lasciato(client, test_session_factory):
    f = test_session_factory
    camp, a = await _enrolled(client, f)
    b = await _char(f, PLAYER_ID, "Secondo")
    act(PLAYER_ID)
    assert (await client.post("/campaigns/enroll", json={"code": camp["invite_code"], "character_id": b})).status_code == 200
    s1 = await _apri_serata(client, camp["id"], [(PLAYER_ID, b)])
    act(GM_ID)
    await client.post(f"/sessions/{s1}/close")
    s2 = await _apri_serata(client, camp["id"], [(PLAYER_ID, a)])
    act(PLAYER_ID)
    assert (await client.post(f"/sessions/{s2}/leave")).status_code == 204
    banner = (await client.get("/campaigns/active-for-me")).json()
    assert [x["my_last_character_id"] for x in banner] == [a]
    assert (await client.get(f"/campaigns/{camp['id']}")).json()["my_last_character_id"] == a


@pytest.mark.caccia(id="CB-882", fonte="invariante: la nota della serata è ≤200 caratteri (non byte), vuota o solo spazi = nessuna nota, omessa = invariata",
                    zona="flusso:campagna-calendario", voce="limiti",
                    copre=["POST /campaigns/{campaign_id}/schedule", "PATCH /campaigns/{campaign_id}/schedule/{sid}"])
async def test_nota_della_serata_con_accenti_ed_emoji(client):
    act(GM_ID)
    camp = await _new_campaign(client)
    url = f"/campaigns/{camp['id']}/schedule"
    quando = _iso_utc(timedelta(days=2))
    for nota in ("è" * 200, "🎲" * 200):
        r = await client.post(url, json={"starts_at": quando, "note": nota})
        assert r.status_code == 201 and r.json()["note"] == nota
    for nota in ("è" * 201, "🎲" * 201):
        assert (await client.post(url, json={"starts_at": quando, "note": nota})).status_code == 422
    riga = (await client.post(url, json={"starts_at": quando, "note": "  Da Marco  "})).json()
    assert riga["note"] == "Da Marco"
    r = await client.patch(f"{url}/{riga['id']}", json={"starts_at": _iso_utc(timedelta(days=3))})  # nota omessa: resta
    assert r.status_code == 200 and r.json()["note"] == "Da Marco"
    r = await client.patch(f"{url}/{riga['id']}", json={"note": "   "})
    assert r.status_code == 200 and r.json()["note"] is None


@pytest.mark.caccia(id="CB-883", fonte="Telegram Bot API (MarkdownV2): ogni carattere riservato nel testo va preceduto da una barra; messaggio ≤4096 caratteri",
                    zona="flusso:campagna-calendario", voce="limiti", copre=["POST /share/recap/{session_id}"])
def test_testo_del_riepilogo_con_nomi_pieni_di_simboli():
    nome = "Ser_Aria*(il-Grande)[x]~`>#+=|{}.!\\"
    pg = {"character_id": 1, "name": nome, "player_name": nome, "class_summary": nome, "level": 3,
          "dice": {"rolls": 4, "nat20": 1, "nat1": 1, "highest": 17}, "damage_taken": 5, "healed": 2, "downed": 1,
          "death_saves": {"successes": 1, "failures": 2}, "spells_cast": 2, "slots_used": {"1": 2}, "rests": {"short": 1, "long": 1},
          "conditions": ["prone"], "condition_levels": {}, "healing_given": 1}
    rec = {"campaign_name": nome, "number": 3, "duration_seconds": 3700, "started_at": "2026-11-20T19:00:00",
           "characters": [pg], "combat": {"encounters": 1, "rounds": 3, "monsters": [nome]},
           "items": {"gm_grants": [{"to": nome, "item": nome, "quantity": 2}], "trades": [{"from": nome, "to": nome, "summary": nome}],
                     "stash": [{"kind": "stash_put", "who": nome, "summary": nome}]},
           "lore": [{"id": 1, "title": nome}], "places": [{"map_id": 1, "marker_id": None, "title": nome}],
           "highlights": [{"key": "healer", "character_id": 1, "name": nome, "value": 4}]}
    for lang in ("it", "en"):
        testo = format_recap_text(rec, lang)
        nudo = re.sub(r"\\.", "", testo, flags=re.S)
        assert not re.search(r"[_\[\]()~`>#+\-=|{}.!\\]", nudo), (lang, nudo)
        assert nudo.count("*") % 2 == 0 and len(testo) <= 4096
    molti = {**rec, "characters": [{**pg, "character_id": i, "name": f"PG {i} " + "x" * 80} for i in range(60)]}
    lungo = format_recap_text(molti, "it")
    assert len(lungo) <= 4096 and lungo.endswith("…")


@pytest.mark.caccia(id="CB-884", fonte="invariante: i PF curati sono quelli davvero recuperati, non il valore chiesto",
                    zona="flusso:campagna-calendario", voce="regola", copre=["PATCH /characters/{char_id}/hp", "GET /sessions/{session_id}/recap"])
async def test_riepilogo_conta_i_pf_curati_davvero(client, test_session_factory):
    camp, cid = await _enrolled(client, test_session_factory)
    sid = await _apri_serata(client, camp["id"], [(PLAYER_ID, cid)])
    act(PLAYER_ID)
    await _hp(client, cid, ("set_max", 20), ("set_current", 20), ("heal", 5))  # a PF pieni: nulla da curare
    await _hp(client, cid, ("damage", 6), ("heal", 40))  # 14 → 20: sei PF
    act(GM_ID)
    await client.post(f"/sessions/{sid}/close")
    c = (await client.get(f"/sessions/{sid}/recap")).json()["characters"][0]
    assert (c["healed"], c["damage_taken"]) == (6, 6)


@pytest.mark.caccia(id="CB-885", fonte="invariante: chi esce dalla campagna e rientra a serata aperta resta un solo PG nel riepilogo, con i dati dall'inizio",
                    zona="flusso:campagna-calendario", voce="annullamento",
                    copre=["DELETE /campaigns/{campaign_id}/members/{character_id}", "POST /campaigns/enroll", "GET /sessions/{session_id}/recap"])
async def test_pg_tolto_e_reiscritto_a_serata_aperta(client, test_session_factory):
    camp, cid = await _enrolled(client, test_session_factory)
    sid = await _apri_serata(client, camp["id"], [(PLAYER_ID, cid)])
    act(PLAYER_ID)
    await _hp(client, cid, ("set_max", 20), ("set_current", 20), ("damage", 7))
    act(GM_ID)
    assert (await client.delete(f"/campaigns/{camp['id']}/members/{cid}")).status_code == 204
    act(PLAYER_ID)
    assert (await client.post("/campaigns/enroll", json={"code": camp["invite_code"], "character_id": cid})).status_code == 200
    assert (await client.post(f"/campaigns/{camp['id']}/session/join", json={"character_id": cid})).status_code == 200
    await _hp(client, cid, ("damage", 3))
    act(GM_ID)
    await client.post(f"/sessions/{sid}/close")
    rec = (await client.get(f"/sessions/{sid}/recap")).json()
    assert [(c["character_id"], c["damage_taken"]) for c in rec["characters"]] == [(cid, 10)]


@pytest.mark.caccia(id="CB-886", fonte="invariante: togliere un PG dalla campagna toglie anche l'accesso a ciò che è della campagna, riepilogo compreso",
                    zona="flusso:campagna-calendario", voce="permessi",
                    copre=["DELETE /campaigns/{campaign_id}/members/{character_id}", "GET /sessions/{session_id}/recap", "GET /campaigns/{campaign_id}/schedule"])
async def test_ex_membro_mai_seduto_perde_l_accesso(client, test_session_factory):
    f = test_session_factory
    camp, cid = await _enrolled(client, f)
    altro = await _char(f, 7777, "Bardo")
    act(7777)
    assert (await client.post("/campaigns/enroll", json={"code": camp["invite_code"], "character_id": altro})).status_code == 200
    sid = await _apri_serata(client, camp["id"], [(7777, altro)])
    act(GM_ID)
    await client.post(f"/sessions/{sid}/close")
    act(PLAYER_ID)
    assert (await client.get(f"/sessions/{sid}/recap")).status_code == 200  # iscritto
    act(GM_ID)
    assert (await client.delete(f"/campaigns/{camp['id']}/members/{cid}")).status_code == 204
    act(PLAYER_ID)
    assert (await client.get(f"/sessions/{sid}/recap")).status_code == 403
    assert (await client.get(f"/campaigns/{camp['id']}")).status_code == 404
    assert (await client.get(f"/campaigns/{camp['id']}/schedule")).status_code == 404
    assert (await client.get("/campaigns")).json() == []


@pytest.mark.caccia(id="CB-887", fonte="invariante: il banner «entra in serata» propone per ogni campagna il PG usato in quella, non uno di un'altra",
                    zona="flusso:campagna-calendario", voce="interazione", copre=["GET /campaigns/active-for-me"])
async def test_banner_con_due_campagne_propone_il_pg_giusto_per_ciascuna(client, test_session_factory):
    f = test_session_factory
    camp_b, x = await _enrolled(client, f)  # master GM_ID
    act(8888)
    camp_c = await _new_campaign(client, "Seconda")
    y = await _char(f, PLAYER_ID, "Yara")
    act(PLAYER_ID)
    assert (await client.post("/campaigns/enroll", json={"code": camp_c["invite_code"], "character_id": y})).status_code == 200
    z = await _char(f, PLAYER_ID, "Zed")
    assert (await client.post("/campaigns/enroll", json={"code": camp_b["invite_code"], "character_id": z})).status_code == 200
    sb = await _apri_serata(client, camp_b["id"], [(PLAYER_ID, z)])
    act(GM_ID)
    await client.post(f"/sessions/{sb}/close")
    act(8888)
    sc = (await client.post("/sessions", json={"campaign_id": camp_c["id"]})).json()["id"]
    act(PLAYER_ID)
    assert (await client.post(f"/campaigns/{camp_c['id']}/session/join", json={"character_id": y})).status_code == 200
    act(8888)
    await client.post(f"/sessions/{sc}/close")
    sb2 = await _apri_serata(client, camp_b["id"], [])
    act(8888)
    sc2 = (await client.post("/sessions", json={"campaign_id": camp_c["id"]})).json()["id"]
    act(PLAYER_ID)
    banner = {b["campaign_id"]: (b["session_id"], b["my_last_character_id"]) for b in (await client.get("/campaigns/active-for-me")).json()}
    assert banner == {camp_b["id"]: (sb2, z), camp_c["id"]: (sc2, y)}


@pytest.mark.xfail(strict=True, reason="CB-894 D-014: due serate allo stesso istante vengono create entrambe")
@pytest.mark.caccia(id="CB-894", fonte="decisione D-014 (tests/caccia/decisioni.md): due serate programmate allo stesso istante sono rifiutate con 409",
                    zona="flusso:campagna-calendario", voce="ripetizione",
                    copre=["POST /campaigns/{campaign_id}/schedule", "DELETE /campaigns/{campaign_id}/schedule/{sid}"])
async def test_serata_allo_stesso_istante_una_sola(client):
    act(GM_ID)
    camp = await _new_campaign(client)
    url = f"/campaigns/{camp['id']}/schedule"
    t1, t2 = _iso_utc(timedelta(days=3)), _iso_utc(timedelta(days=4))
    prima = await client.post(url, json={"starts_at": t1})
    assert prima.status_code == 201
    assert (await client.post(url, json={"starts_at": t1})).status_code == 409
    assert (await client.post(url, json={"starts_at": t2})).status_code == 201

    async def prova(t):
        try:
            return (await client.post(url, json={"starts_at": t})).status_code
        except Exception:  # noqa: BLE001
            return 500
    t3 = _iso_utc(timedelta(days=5))
    assert sorted(await asyncio.gather(*[prova(t3) for _ in range(4)])) == [201, 409, 409, 409]
    assert len((await client.get(url)).json()) == 3
    assert (await client.delete(f"{url}/{prima.json()['id']}")).status_code == 204
    assert (await client.post(url, json={"starts_at": t1})).status_code == 201
