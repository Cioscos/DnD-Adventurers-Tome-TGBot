"""Controlli della zona flusso:dadi."""
import asyncio
from datetime import datetime, timedelta

import pytest

from api.services import telegram_notify
from api.services.dice_notation import roll_dice
from core.db.models import CharacterHistory


async def _pg(client, edizione: str = "2014") -> int:
    cid = (await client.post("/characters", json={"name": "Dadi"})).json()["id"]
    if edizione != "2014":
        await client.patch(f"/characters/{cid}", json={"rules_edition": edizione})
    return cid


def _tiro(*valori, kind="d6", **extra):
    return {"rolls": [{"kind": kind, "value": v} for v in valori], **extra}


async def _stats(client, cid) -> dict:
    return (await client.get(f"/characters/{cid}/dice/stats")).json()["stats"]


@pytest.mark.caccia(id="CB-737", fonte="invariante: il frontend legge ciò che l'API restituisce", zona="flusso:dadi", voce="contratto",
                    copre=["POST /characters/{char_id}/dice/result", "GET /characters/{char_id}/dice/history",
                           "GET /characters/{char_id}/dice/stats", "GET /characters/{char_id}/history",
                           "GET /characters/{char_id}/history/retention-preview", "route:/char/:id/dice"])
async def test_contratto_campi_di_dadi_e_cronologia(client):
    cid = await _pg(client)
    r = await client.post(f"/characters/{cid}/dice/result", json=_tiro(3, 5, label="Prova", source="skill", modifier=2))
    assert r.status_code == 200
    assert {"notation", "rolls", "total"} <= set(r.json())
    voce = (await client.get(f"/characters/{cid}/dice/history")).json()[0]
    assert {"notation", "rolls", "total", "timestamp", "source", "label"} <= set(voce)
    assert voce["timestamp"] and voce["source"] == "skill" and voce["label"] == "Prova"
    assert (await client.get(f"/characters/{cid}/dice/stats")).json() == {"stats": {"d6": {"3": 1, "5": 1}}}
    cron = (await client.get(f"/characters/{cid}/history")).json()
    assert cron and {"id", "timestamp", "event_type", "description"} <= set(cron[0])
    prev = (await client.get(f"/characters/{cid}/history/retention-preview")).json()
    assert {"total", "events_keep", "days_window", "would_purge_events", "would_purge_days"} <= set(prev)
    assert (await client.delete(f"/characters/{cid}/dice/history")).status_code == 204
    assert (await client.delete(f"/characters/{cid}/dice/stats")).status_code == 204
    assert (await client.delete(f"/characters/{cid}/history")).status_code == 204


@pytest.mark.caccia(id="CB-738", fonte="invariante: totale = somma dei dadi + modificatore", zona="flusso:dadi", voce="normale",
                    copre=["POST /characters/{char_id}/dice/result", "route:/char/:id/dice"])
async def test_totale_e_notazione_con_modificatore(client):
    cid = await _pg(client)
    r = (await client.post(f"/characters/{cid}/dice/result", json=_tiro(3, 5, modifier=2))).json()
    assert (r["notation"], r["rolls"], r["total"]) == ("2d6+2", [3, 5], 10)
    r = (await client.post(f"/characters/{cid}/dice/result", json=_tiro(7, kind="d20", modifier=-3))).json()
    assert (r["notation"], r["total"]) == ("d20-3", 4)
    assert [e["total"] for e in (await client.get(f"/characters/{cid}/dice/history")).json()] == [4, 10]


@pytest.mark.caccia(id="CB-739", fonte="invariante: una faccia esiste solo da 1 al numero di facce", zona="flusso:dadi", voce="limiti",
                    copre=["POST /characters/{char_id}/dice/result"])
async def test_facce_fuori_intervallo_rifiutate_e_non_registrate(client):
    cid = await _pg(client)
    for kind, facce in (("d4", 4), ("d6", 6), ("d8", 8), ("d10", 10), ("d12", 12), ("d20", 20)):
        for v in (0, facce + 1, -1):
            r = await client.post(f"/characters/{cid}/dice/result", json=_tiro(v, kind=kind))
            assert r.status_code == 400, (kind, v)
        for v in (1, facce):
            assert (await client.post(f"/characters/{cid}/dice/result", json=_tiro(v, kind=kind))).status_code == 200
    assert len((await client.get(f"/characters/{cid}/dice/history")).json()) == 12
    # un gruppo con una faccia sbagliata non registra nemmeno i dadi validi
    r = await client.post(f"/characters/{cid}/dice/result", json=_tiro(3, 9))
    assert r.status_code == 400
    assert len((await client.get(f"/characters/{cid}/dice/history")).json()) == 12
    assert "3" not in (await _stats(client, cid)).get("d6", {})


@pytest.mark.caccia(id="CB-740", fonte="invariante: lo storico dei dadi tiene gli ultimi 50 tiri, il più recente in cima", zona="flusso:dadi",
                    voce="limiti", copre=["GET /characters/{char_id}/dice/history"])
async def test_storico_dadi_ultimi_cinquanta(client):
    cid = await _pg(client)
    for i in range(1, 56):
        await client.post(f"/characters/{cid}/dice/result", json=_tiro(1 + i % 6, modifier=i))
    storico = (await client.get(f"/characters/{cid}/dice/history")).json()
    assert len(storico) == 50
    assert storico[0]["total"] == (1 + 55 % 6) + 55 and storico[-1]["total"] == (1 + 6 % 6) + 6


@pytest.mark.caccia(id="CB-741", fonte="2014 · Regole generali · Vantaggio e svantaggio · pag. 173", zona="flusso:dadi", voce="regola",
                    copre=["POST /characters/{char_id}/dice/result"])
async def test_vantaggio_e_svantaggio_sul_server(client):
    cid = await _pg(client)
    url = f"/characters/{cid}/dice/result"
    assert (await client.post(url, json=_tiro(5, 15, kind="d20", mode="advantage", modifier=3))).json()["total"] == 18
    assert (await client.post(url, json=_tiro(5, 15, kind="d20", mode="disadvantage", modifier=3))).json()["total"] == 8
    assert (await client.post(url, json=_tiro(15, 5, kind="d20", mode="disadvantage"))).json()["total"] == 5
    assert (await client.post(url, json=_tiro(5, kind="d20", mode="advantage"))).status_code == 422
    assert (await client.post(url, json=_tiro(5, 6, kind="d6", mode="advantage"))).status_code == 422
    assert len((await client.get(f"/characters/{cid}/dice/history")).json()) == 3


@pytest.mark.caccia(id="CB-742", fonte="2014 · Regole generali · Ispirazione · pag. 125; 2024 · Regole generali · Ispirazione Eroica · pag. 368",
                    zona="flusso:dadi", voce="edizioni", copre=["POST /characters/{char_id}/dice/result", "carta:2024/general.md#Heroic Inspiration (Ispirazione Eroica) (pag. 368)"])
async def test_ispirazione_rilancio_solo_2024_e_si_spende_una_volta(client):
    url = lambda c: f"/characters/{c}/dice/result"
    corpo = _tiro(12, kind="d20", with_inspiration=True)
    c14 = await _pg(client, "2014")
    await client.patch(f"/characters/{c14}/inspiration", json={"heroic_inspiration": True})
    assert (await client.post(url(c14), json=corpo)).status_code == 409
    assert (await client.get(f"/characters/{c14}")).json()["heroic_inspiration"] is True  # non spesa
    assert (await client.get(f"/characters/{c14}/dice/history")).json() == []
    c24 = await _pg(client, "2024")
    assert (await client.post(url(c24), json=corpo)).status_code == 409  # senza Ispirazione
    await client.patch(f"/characters/{c24}/inspiration", json={"heroic_inspiration": True})
    assert (await client.post(url(c24), json=corpo)).status_code == 200
    assert (await client.get(f"/characters/{c24}")).json()["heroic_inspiration"] is False
    assert (await client.post(url(c24), json=corpo)).status_code == 409
    assert len((await client.get(f"/characters/{c24}/dice/history")).json()) == 1


@pytest.mark.caccia(id="CB-743", fonte="invariante: una richiesta ripetuta non spende due volte", zona="flusso:dadi", voce="ripetizione",
                    copre=["POST /characters/{char_id}/dice/result"])
async def test_rilancio_ispirazione_due_richieste_insieme_ne_spende_una(client):
    cid = await _pg(client, "2024")
    await client.patch(f"/characters/{cid}/inspiration", json={"heroic_inspiration": True})
    corpo = _tiro(12, kind="d20", with_inspiration=True)
    esiti = await asyncio.gather(*[client.post(f"/characters/{cid}/dice/result", json=corpo) for _ in range(2)])
    assert sorted(r.status_code for r in esiti) == [200, 409]
    assert len((await client.get(f"/characters/{cid}/dice/history")).json()) == 1
    assert (await _stats(client, cid))["d20"] == {"12": 1}


@pytest.mark.caccia(id="CB-744", fonte="invariante: azzerare le statistiche riparte da zero", zona="flusso:dadi", voce="annullamento",
                    copre=["DELETE /characters/{char_id}/dice/stats", "DELETE /characters/{char_id}/dice/history",
                           "DELETE /characters/{char_id}/history", "route:/char/:id/dice/stats"])
async def test_azzeramenti_riportano_a_zero_e_si_riparte(client):
    cid = await _pg(client)
    await client.post(f"/characters/{cid}/dice/result", json=_tiro(4, 4))
    await client.delete(f"/characters/{cid}/dice/stats")
    assert await _stats(client, cid) == {}
    assert len((await client.get(f"/characters/{cid}/dice/history")).json()) == 1  # lo storico è un'altra cosa
    await client.post(f"/characters/{cid}/dice/result", json=_tiro(4))
    assert await _stats(client, cid) == {"d6": {"4": 1}}
    await client.delete(f"/characters/{cid}/dice/history")
    assert (await client.get(f"/characters/{cid}/dice/history")).json() == []
    assert (await client.get(f"/characters/{cid}/history")).json() != []
    await client.delete(f"/characters/{cid}/history")
    assert (await client.get(f"/characters/{cid}/history")).json() == []
    await client.post(f"/characters/{cid}/dice/result", json=_tiro(2))
    assert len((await client.get(f"/characters/{cid}/history")).json()) == 1


@pytest.mark.caccia(id="CB-745", fonte="CLAUDE.md: ogni endpoint verifica il proprietario", zona="flusso:dadi", voce="permessi",
                    copre=["POST /characters/{char_id}/dice/result", "POST /characters/{char_id}/dice/initiative",
                           "GET /characters/{char_id}/dice/history", "DELETE /characters/{char_id}/dice/history",
                           "GET /characters/{char_id}/dice/stats", "DELETE /characters/{char_id}/dice/stats",
                           "POST /characters/{char_id}/dice/post-to-chat", "GET /characters/{char_id}/history",
                           "GET /characters/{char_id}/history/retention-preview", "DELETE /characters/{char_id}/history"])
async def test_dadi_e_cronologia_di_un_altro_utente(client, come_utente, monkeypatch):
    inviati = []

    async def finto(*a, **k):
        inviati.append(a)
        return True
    monkeypatch.setattr(telegram_notify, "send_telegram_message", finto)
    monkeypatch.setattr(telegram_notify, "bot_token_configured", lambda: True)
    cid = await _pg(client)
    await client.post(f"/characters/{cid}/dice/result", json=_tiro(4))
    come_utente(9002)
    chat = {"notation": "d6", "rolls": [4], "total": 4}
    chiamate = [
        ("post", "dice/result", _tiro(2)), ("post", "dice/initiative", {}), ("get", "dice/history", None),
        ("delete", "dice/history", None), ("get", "dice/stats", None), ("delete", "dice/stats", None),
        ("post", "dice/post-to-chat", chat), ("get", "history", None), ("get", "history/retention-preview", None),
        ("delete", "history", None),
    ]
    for metodo, percorso, corpo in chiamate:
        for ident, atteso in ((cid, 403), (99999, 404)):
            r = await getattr(client, metodo)(f"/characters/{ident}/{percorso}", **({"json": corpo} if corpo is not None else {}))
            assert r.status_code == atteso, (metodo, percorso, ident, r.status_code)
    assert inviati == []
    come_utente(1234)
    assert len((await client.get(f"/characters/{cid}/dice/history")).json()) == 1
    assert await _stats(client, cid) == {"d6": {"4": 1}}
    assert len((await client.get(f"/characters/{cid}/history")).json()) == 1


@pytest.mark.caccia(id="CB-746", fonte="dice_stats.py: il totale della prova con il d20 è d20 + modificatori, non una somma di più dadi",
                    zona="flusso:dadi", voce="interazione", copre=["POST /characters/{char_id}/dice/result", "GET /sessions/{session_id}/recap"])
async def test_somma_di_piu_d20_manuali_non_e_un_totale_di_prova(client):
    cid = await _pg(client)
    await client.post(f"/characters/{cid}/dice/result", json=_tiro(18, 19, 20, kind="d20"))
    assert "d20_total" not in await _stats(client, cid)


@pytest.mark.caccia(id="CB-747", fonte="invariante: la cronologia mostra il più recente in cima", zona="flusso:dadi", voce="normale",
                    copre=["GET /characters/{char_id}/history", "route:/char/:id/history"])
async def test_cronologia_piu_recente_in_cima_anche_nello_stesso_secondo(client, test_session_factory):
    cid = await _pg(client)
    await client.delete(f"/characters/{cid}/history")
    for v in (1, 2, 3, 4):
        await client.post(f"/characters/{cid}/dice/result", json=_tiro(v))
    righe = (await client.get(f"/characters/{cid}/history")).json()
    assert [r["description"].split(": ")[-1] for r in righe] == ["4", "3", "2", "1"]


@pytest.mark.caccia(id="CB-748", fonte="invariante: la cronologia tiene gli ultimi 200 eventi, il più recente in cima", zona="flusso:dadi",
                    voce="limiti", copre=["GET /characters/{char_id}/history", "GET /characters/{char_id}/history/retention-preview"])
async def test_cronologia_duecento_voci_e_anteprima_di_pulizia(client, test_session_factory):
    cid = await _pg(client)
    await client.delete(f"/characters/{cid}/history")
    adesso = datetime.utcnow()
    async with test_session_factory() as s:
        for i in range(205):
            s.add(CharacterHistory(character_id=cid, event_type="other", description=f"e{i}",
                                   timestamp=(adesso - timedelta(days=40) + timedelta(minutes=i)).isoformat(timespec="seconds")))
        await s.commit()
    righe = (await client.get(f"/characters/{cid}/history")).json()
    assert len(righe) == 200 and righe[0]["description"] == "e204" and righe[-1]["description"] == "e5"
    p = (await client.get(f"/characters/{cid}/history/retention-preview?events=205&days=30")).json()
    assert (p["total"], p["would_purge_events"], p["would_purge_days"]) == (205, 0, 205)
    p = (await client.get(f"/characters/{cid}/history/retention-preview?events=204&days=41")).json()
    assert (p["would_purge_events"], p["would_purge_days"]) == (1, 0)
    assert (await client.get(f"/characters/{cid}/history/retention-preview?events=0")).status_code == 422
    assert (await client.get(f"/characters/{cid}/history/retention-preview?days=3651")).status_code == 422


@pytest.mark.caccia(id="CB-749", fonte="invariante: il messaggio in chat «a + b = totale» deve tornare come somma", zona="flusso:dadi",
                    voce="normale", copre=["POST /characters/{char_id}/dice/post-to-chat", "POST /characters/{char_id}/dice/result"])
async def test_messaggio_in_chat_di_un_4d6_scarta_il_piu_basso(client, monkeypatch):
    testi = []

    async def finto(chat, testo, **k):
        testi.append(testo)
        return True
    monkeypatch.setattr(telegram_notify, "send_telegram_message", finto)
    monkeypatch.setattr(telegram_notify, "bot_token_configured", lambda: True)
    cid = await _pg(client)
    r = (await client.post(f"/characters/{cid}/dice/result", json=_tiro(3, 4, 5, 1, notation="4d6kh3", total=12))).json()
    assert (await client.post(f"/characters/{cid}/dice/post-to-chat", json=r)).status_code == 200
    import re
    numeri = [int(n) for n in re.findall(r"\d+", testi[0].split(":", 1)[1].split("=")[0])]
    assert sum(numeri) == 12, testi[0]


@pytest.mark.caccia(id="CB-750", fonte="invariante: la cronologia generale descrive il tiro in modo coerente col totale", zona="flusso:dadi",
                    voce="normale", copre=["POST /characters/{char_id}/dice/result", "GET /characters/{char_id}/history"])
async def test_cronologia_di_un_4d6_scarta_il_piu_basso(client):
    cid = await _pg(client)
    await client.delete(f"/characters/{cid}/history")
    await client.post(f"/characters/{cid}/dice/result", json=_tiro(3, 4, 5, 1, notation="4d6kh3", total=12))
    d = (await client.get(f"/characters/{cid}/history")).json()[0]["description"]
    import re
    elenco = re.search(r"\[([\d+]+)\]", d)
    assert elenco and sum(int(n) for n in elenco.group(1).split("+")) == 12, d


@pytest.mark.caccia(id="CB-751", fonte="invariante: l'iniziativa tirata dalla pagina dadi compare nello storico, nelle statistiche e nel feed",
                    zona="flusso:dadi", voce="interazione", copre=["POST /characters/{char_id}/dice/initiative", "route:/char/:id/dice"])
async def test_iniziativa_con_dadi_fissati_in_storico_e_statistiche(client):
    cid = await _pg(client)
    await client.patch(f"/characters/{cid}/ability_scores/dexterity", json={"value": 14})
    r = await client.post(f"/characters/{cid}/dice/initiative", json={"dice": [4, 17], "mode": "advantage", "label": "Iniziativa"})
    assert r.status_code == 200
    j = r.json()
    assert (j["die"], j["bonus"], j["total"]) == (17, 2, 19)
    voce = (await client.get(f"/characters/{cid}/dice/history")).json()[0]
    assert (voce["rolls"], voce["total"], voce["source"], voce["label"]) == ([4, 17], 19, "init", "Iniziativa")
    st = await _stats(client, cid)
    assert st["d20"] == {"4": 1, "17": 1}
    r = await client.post(f"/characters/{cid}/dice/initiative", json={"die": 1})
    assert r.status_code == 200 and r.json()["total"] == 3 and r.json()["is_fumble"] is True
    assert (await client.post(f"/characters/{cid}/dice/initiative", json={"die": 21})).status_code == 422
    assert (await client.post(f"/characters/{cid}/dice/initiative", json={"dice": [3], "mode": "advantage"})).status_code == 422


@pytest.mark.caccia(id="CB-752", fonte="invariante: la risposta restituisce il modificatore inviato", zona="flusso:dadi", voce="contratto",
                    copre=["POST /characters/{char_id}/dice/result"])
async def test_risposta_del_tiro_riporta_il_modificatore(client):
    cid = await _pg(client)
    r = (await client.post(f"/characters/{cid}/dice/result", json=_tiro(3, modifier=4))).json()
    assert r["total"] == 7 and r["modifier"] == 4


@pytest.mark.caccia(id="CB-753", fonte="invariante: l'etichetta di un tiro lungo al limite è accettata e oltre il limite rifiutata", zona="flusso:dadi",
                    voce="limiti", copre=["POST /characters/{char_id}/dice/result"])
async def test_etichetta_notazione_e_numero_di_dadi_al_limite(client):
    cid = await _pg(client)
    url = f"/characters/{cid}/dice/result"
    assert (await client.post(url, json=_tiro(2, label="è" * 120, notation="n" * 80))).status_code == 200
    assert (await client.post(url, json=_tiro(2, label="è" * 121))).status_code == 422
    assert (await client.post(url, json=_tiro(2, notation="n" * 81))).status_code == 422
    assert (await client.post(url, json=_tiro(*([6] * 200)))).json()["total"] == 1200
    assert (await client.post(url, json=_tiro(*([6] * 201)))).status_code == 422
    assert (await client.post(url, json={"rolls": []})).status_code == 422
    assert (await client.get(f"/characters/{cid}/dice/history")).json()[1]["label"] == "è" * 120


@pytest.mark.caccia(id="CB-754", fonte="invariante: 2d6+2 tira due dadi a sei facce e somma 2", zona="flusso:dadi", voce="normale",
                    copre=[])
async def test_notazione_dei_dadi_del_server(dadi):
    dadi(3, 5)
    assert roll_dice("2d6+2") == ([3, 5], 2)
    dadi(8)
    assert roll_dice(" 1D8-3 ") == ([8], -3)
    assert roll_dice("d8") == ([0], 0)
    assert roll_dice("1d0") == ([0], 0)


@pytest.mark.caccia(id="CB-757", fonte="invariante: ciò che è registrato resta finché non lo si azzera", zona="flusso:dadi", voce="persistenza",
                    copre=["POST /characters/{char_id}/dice/result", "GET /characters/{char_id}/dice/history", "GET /characters/{char_id}/dice/stats",
                           "GET /characters/{char_id}/history", "POST /characters/{char_id}/rest", "PATCH /characters/{char_id}"])
async def test_storico_statistiche_e_cronologia_restano_dopo_riposo_e_modifica(client):
    cid = await _pg(client)
    await client.patch(f"/characters/{cid}", json={"hit_points": 10, "current_hit_points": 10})
    for corpo in (_tiro(3, 5, modifier=2), _tiro(17, kind="d20"), _tiro(1, kind="d4", label="x", source="spell")):
        assert (await client.post(f"/characters/{cid}/dice/result", json=corpo)).status_code == 200

    async def foto():
        return [(await client.get(f"/characters/{cid}/{p}")).json() for p in ("dice/history", "dice/stats", "history")]
    prima = await foto()
    assert prima == await foto()
    assert len(prima[0]) == 3 and len(prima[2]) >= 3
    assert (await client.post(f"/characters/{cid}/rest", json={"rest_type": "long"})).status_code == 200
    r = await client.patch(f"/characters/{cid}", json={"name": "Altro nome"})
    assert r.status_code == 200
    dopo = await foto()
    assert dopo[0] == prima[0] and dopo[1] == prima[1]
    assert all(e in dopo[2] for e in prima[2])  # il riposo può aggiungere voci, non toglierne


@pytest.mark.caccia(id="CB-758", fonte="decisione D-004", zona="flusso:dadi", voce="interazione",
                    copre=["POST /characters/{char_id}/dice/result", "GET /characters/{char_id}/dice/stats", "route:/char/:id/dice/stats"])
async def test_d100_non_conta_nelle_statistiche_del_d10(client):
    cid = await _pg(client)
    corpo = _tiro(4, 7, kind="d10", notation="1d100", total=37, modifier=0)
    assert (await client.post(f"/characters/{cid}/dice/result", json=corpo)).status_code == 200
    assert "d10" not in await _stats(client, cid)


@pytest.mark.caccia(id="CB-765", fonte="invariante: la pulizia della cronologia tiene gli eventi più recenti", zona="flusso:dadi", voce="limiti",
                    copre=["POST /characters/{char_id}/dice/result"])
async def test_la_pulizia_tiene_gli_ultimi_anche_nello_stesso_secondo(client, test_session_factory):
    from core.db.models import Character
    from api.routers._helpers import prune_history

    cid = await _pg(client)
    await client.delete(f"/characters/{cid}/history")
    async with test_session_factory() as s:
        for i in range(8):
            s.add(CharacterHistory(character_id=cid, event_type="other", description=f"e{i}", timestamp="2026-11-24T10:00:00"))
            await s.flush()
        char = await s.get(Character, cid)
        char.settings = {**(char.settings or {}), "history_retention_mode": "events", "history_retention_events": 3}
        await prune_history(s, char)
        await s.commit()
    righe = (await client.get(f"/characters/{cid}/history")).json()
    assert [r["description"] for r in righe] == ["e7", "e6", "e5"]


@pytest.mark.caccia(id="CB-1473", fonte="invariante: due richieste insieme registrano entrambi i tiri", zona="flusso:dadi", voce="ripetizione",
                    copre=["POST /characters/{char_id}/dice/result", "GET /characters/{char_id}/dice/history", "GET /characters/{char_id}/dice/stats"])
async def test_due_tiri_diversi_insieme_restano_entrambi(client):
    cid = await _pg(client)
    esiti = await asyncio.gather(*[client.post(f"/characters/{cid}/dice/result", json=_tiro(v)) for v in (2, 5)])
    assert [r.status_code for r in esiti] == [200, 200]
    assert sorted(e["total"] for e in (await client.get(f"/characters/{cid}/dice/history")).json()) == [2, 5]
    assert await _stats(client, cid) == {"d6": {"2": 1, "5": 1}}


@pytest.mark.caccia(id="CB-1475", fonte="invariante: la pulizia della cronologia per numero di eventi vale anche per i tiri dei dadi", zona="flusso:dadi",
                    voce="limiti", copre=["POST /characters/{char_id}/dice/result", "POST /characters/{char_id}/dice/initiative", "GET /characters/{char_id}/history"])
async def test_tiri_di_dadi_rispettano_la_pulizia_per_eventi(client, test_session_factory):
    from core.db.models import Character
    cid = await _pg(client)
    async with test_session_factory() as s:
        char = await s.get(Character, cid)
        char.settings = {**(char.settings or {}), "history_retention_mode": "events", "history_retention_events": 3}
        await s.commit()
    for v in (1, 2, 3, 4):
        await client.post(f"/characters/{cid}/dice/result", json=_tiro(v))
    for v in (5, 6):
        await client.post(f"/characters/{cid}/dice/initiative", json={"die": v})
    assert len((await client.get(f"/characters/{cid}/history")).json()) <= 3


@pytest.mark.caccia(id="CB-1477", fonte="invariante: una richiesta rifiutata non registra nulla", zona="flusso:dadi", voce="limiti",
                    copre=["POST /characters/{char_id}/dice/result"])
async def test_vantaggio_con_tre_d20_rifiutato_senza_registrare(client):
    cid = await _pg(client)
    r = await client.post(f"/characters/{cid}/dice/result", json=_tiro(5, 9, 15, kind="d20", mode="advantage"))
    assert r.status_code == 422
    assert (await client.get(f"/characters/{cid}/dice/history")).json() == []
    assert await _stats(client, cid) == {}


@pytest.mark.caccia(id="CB-1478", fonte="invariante: i dadi d20 letti fuori da 1-20 si rifiutano e non si registrano", zona="flusso:dadi", voce="limiti",
                    copre=["POST /characters/{char_id}/dice/initiative"])
async def test_iniziativa_con_facce_fuori_intervallo_non_registra(client):
    cid = await _pg(client)
    for corpo in ({"dice": [0, 10], "mode": "advantage"}, {"dice": [10, 21], "mode": "disadvantage"}, {"dice": [-3], "mode": "normal"}):
        assert (await client.post(f"/characters/{cid}/dice/initiative", json=corpo)).status_code == 422, corpo
    assert (await client.get(f"/characters/{cid}/dice/history")).json() == []
    assert await _stats(client, cid) == {}


@pytest.mark.caccia(id="CB-1479", fonte="dice_stats.py: il totale della prova con il d20 alimenta il riepilogo della serata", zona="flusso:dadi", voce="interazione",
                    copre=["POST /characters/{char_id}/dice/initiative", "GET /characters/{char_id}/dice/stats"])
async def test_iniziativa_registra_il_totale_della_prova(client):
    cid = await _pg(client)
    await client.patch(f"/characters/{cid}/ability_scores/dexterity", json={"value": 14})
    r = await client.post(f"/characters/{cid}/dice/initiative", json={"dice": [4, 17], "mode": "advantage"})
    assert r.json()["total"] == 19
    assert (await _stats(client, cid))["d20_total"] == {"19": 1}
    cron = (await client.get(f"/characters/{cid}/history")).json()[0]
    assert cron["event_type"] == "dice_roll" and cron["description"].endswith("19")


@pytest.mark.caccia(id="CB-1480", fonte="decisione D-003", zona="flusso:dadi", voce="persistenza",
                    copre=["POST /characters/{char_id}/duplicate", "GET /characters/{char_id}/dice/history", "GET /characters/{char_id}/dice/stats"])
async def test_duplicato_riparte_senza_tiri_e_statistiche(client):
    cid = await _pg(client)
    await client.post(f"/characters/{cid}/dice/result", json=_tiro(3, 4))
    r = await client.post(f"/characters/{cid}/duplicate")
    assert r.status_code in (200, 201), r.text
    nuovo = r.json()["id"]
    assert (await client.get(f"/characters/{nuovo}/dice/history")).json() == []
    assert await _stats(client, nuovo) == {}
    assert all(e["event_type"] != "dice_roll" for e in (await client.get(f"/characters/{nuovo}/history")).json())
    assert len((await client.get(f"/characters/{cid}/dice/history")).json()) == 1


@pytest.mark.caccia(id="CB-1481", fonte="invariante: il messaggio in chat va al proprio utente e un invio fallito non risponde ok", zona="flusso:dadi", voce="normale",
                    copre=["POST /characters/{char_id}/dice/post-to-chat"])
async def test_post_to_chat_destinatario_ed_errore_di_invio(client, monkeypatch):
    inviati, esito = [], [True]

    async def finto(chat, testo, **k):
        inviati.append((chat, testo))
        return esito[0]
    monkeypatch.setattr(telegram_notify, "send_telegram_message", finto)
    monkeypatch.setattr(telegram_notify, "bot_token_configured", lambda: True)
    cid = await _pg(client)
    corpo = {"notation": "2d6+2", "rolls": [3, 5], "total": 10}
    assert (await client.post(f"/characters/{cid}/dice/post-to-chat", json=corpo)).json() == {"ok": True}
    assert inviati[0][0] == 1234 and "10" in inviati[0][1]
    esito[0] = False
    assert (await client.post(f"/characters/{cid}/dice/post-to-chat", json=corpo)).status_code >= 400


@pytest.mark.caccia(id="CB-1482", fonte="invariante: azzerare le statistiche toglie anche i totali delle prove", zona="flusso:dadi", voce="annullamento",
                    copre=["DELETE /characters/{char_id}/dice/stats", "POST /characters/{char_id}/dice/initiative"])
async def test_azzerare_le_statistiche_toglie_anche_il_totale_della_prova(client):
    cid = await _pg(client)
    await client.post(f"/characters/{cid}/dice/initiative", json={"die": 12})
    assert (await _stats(client, cid))["d20_total"]
    await client.delete(f"/characters/{cid}/dice/stats")
    assert await _stats(client, cid) == {}
    assert len((await client.get(f"/characters/{cid}/dice/history")).json()) == 1


@pytest.mark.caccia(id="CB-1491", fonte="2014 · Talenti · Allerta · +5 all'iniziativa", zona="flusso:dadi", voce="edizioni",
                    copre=["POST /characters/{char_id}/dice/initiative", "carta:2014/feats.md#Allerta / Alert (pag. 165)"])
async def test_iniziativa_2014_con_allerta_somma_cinque(client):
    from tests.integration.test_level_choices import _take, _to_level_4
    from tests.integration.rules.test_2014_bard import _full
    body = await _to_level_4(client)
    prima = (await client.post(f"/characters/{body['id']}/dice/initiative", json={"die": 10})).json()
    await _take(client, body, "alert")
    dopo = (await client.post(f"/characters/{body['id']}/dice/initiative", json={"die": 10})).json()
    assert dopo["bonus"] == prima["bonus"] + 5 and dopo["total"] == prima["total"] + 5
    assert dopo["bonus"] == (await _full(client, body["id"]))["initiative_bonus"]


@pytest.mark.caccia(id="CB-1492", fonte="2024 · Talenti · Allerta · bonus di competenza all'iniziativa", zona="flusso:dadi", voce="edizioni",
                    copre=["POST /characters/{char_id}/dice/initiative", "carta:2024/feats.md#Allerta / Alert (pag. 200) - Origine"])
async def test_iniziativa_2024_con_allerta_somma_la_competenza(client, test_session_factory):
    from tests.integration.rules.test_feats_origin_2024 import _give, _hero
    cid = await _hero(client, 5)
    prima = (await client.post(f"/characters/{cid}/dice/initiative", json={"die": 10})).json()
    await _give(test_session_factory, client, cid, "2024_alert")
    dopo = (await client.post(f"/characters/{cid}/dice/initiative", json={"die": 10})).json()
    assert dopo["bonus"] == prima["bonus"] + 3 and dopo["total"] == prima["total"] + 3


@pytest.mark.caccia(id="CB-1493", fonte="CLAUDE.md: ogni endpoint verifica il proprietario; un'ispirazione non si spende da altri", zona="flusso:dadi",
                    voce="permessi", copre=["POST /characters/{char_id}/dice/result", "PATCH /characters/{char_id}/inspiration"])
async def test_altro_utente_non_spende_l_ispirazione_altrui(client, come_utente):
    cid = await _pg(client, "2024")
    await client.patch(f"/characters/{cid}/inspiration", json={"heroic_inspiration": True})
    come_utente(9002)
    r = await client.post(f"/characters/{cid}/dice/result", json=_tiro(12, kind="d20", with_inspiration=True))
    assert r.status_code == 403
    come_utente(1234)
    assert (await client.get(f"/characters/{cid}")).json()["heroic_inspiration"] is True
    assert (await client.get(f"/characters/{cid}/dice/history")).json() == []
    assert await _stats(client, cid) == {}


@pytest.mark.caccia(id="CB-1507", fonte="invariante (Impostazioni: ultimi N eventi)", zona="flusso:dadi", voce="limiti", copre=["GET /characters/{char_id}/history"])
async def test_la_pulizia_della_cronologia_vale_anche_per_i_pf(client):
    pg = (await client.post("/characters", json={"name": "S", "initial_class": {"class_name": "fighter", "level": 5}})).json()
    cid = pg["id"]
    await client.patch(f"/characters/{cid}", json={"settings": {**pg["settings"], "history_retention_mode": "events", "history_retention_events": 2}})
    for n in range(1, 6):
        assert (await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": n})).status_code == 200
    voci = (await client.get(f"/characters/{cid}/history")).json()
    assert len(voci["entries"] if isinstance(voci, dict) else voci) == 2
