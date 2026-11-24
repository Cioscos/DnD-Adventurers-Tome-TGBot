"""Controlli della zona flusso:concentrazione."""
import random

import pytest

from tests.integration.conftest import TEST_USER_ID


async def _pg(client, edizione="2014", classe="bard", livello=5) -> int:
    cid = (await client.post("/characters", json={"name": "Mago"})).json()["id"]
    await client.post(f"/characters/{cid}/classes", json={"class_name": classe, "level": livello, "hit_die": 8})
    await client.patch(f"/characters/{cid}", json={"rules_edition": edizione})
    return cid


async def _incantesimo(client, cid, nome="Benedizione", durata="Concentration, up to 1 minute", conc=True, livello=1) -> int:
    r = await client.post(f"/characters/{cid}/spells", json={
        "name": nome, "level": livello, "is_concentration": conc, "duration": durata, "is_prepared": True})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _slot(client, cid, livello=1, totale=4) -> None:
    # il livello di classe crea già gli slot: si aggiunge solo ciò che manca
    if not any(x["level"] == livello and x["total"] >= 1 for x in (await _stato(client, cid))["spell_slots"]):
        r = await client.post(f"/characters/{cid}/spell_slots", json={"level": livello, "total": totale})
        assert r.status_code == 201, r.text


async def _lancia(client, cid, sid, livello=1):
    r = await client.post(f"/characters/{cid}/spells/{sid}/use", json={"slot_level": livello})
    assert r.status_code == 200, r.text
    return r.json()


async def _stato(client, cid):
    return (await client.get(f"/characters/{cid}")).json()


@pytest.mark.caccia(id="CB-437", fonte="2014 · Concentrazione · pag. 203", zona="flusso:concentrazione", voce="limiti",
                    copre=["POST /characters/{char_id}/concentration/save"])
@pytest.mark.parametrize("danno,cd", [(0, 10), (1, 10), (20, 10), (21, 10), (22, 11), (59, 29), (60, 30), (61, 30), (62, 31), (200, 100)])
async def test_cd_concentrazione_2014(client, dadi, danno, cd):
    cid = await _pg(client, "2014")
    dadi(10)
    r = (await client.post(f"/characters/{cid}/concentration/save", json={"damage": danno})).json()
    assert r["dc"] == cd


@pytest.mark.caccia(id="CB-438", fonte="2024 · Concentrazione · pag. 363", zona="flusso:concentrazione", voce="edizioni",
                    copre=["POST /characters/{char_id}/concentration/save"])
@pytest.mark.parametrize("danno,cd", [(0, 10), (21, 10), (22, 11), (59, 29), (60, 30), (61, 30), (62, 30), (200, 30)])
async def test_cd_concentrazione_2024_massimo_30(client, dadi, danno, cd):
    cid = await _pg(client, "2024")
    dadi(10)
    r = (await client.post(f"/characters/{cid}/concentration/save", json={"damage": danno})).json()
    assert r["dc"] == cd


@pytest.mark.caccia(id="CB-439", fonte="invariante: un danno negativo non esiste", zona="flusso:concentrazione", voce="limiti",
                    copre=["POST /characters/{char_id}/concentration/save"])
async def test_tiro_concentrazione_danno_negativo_rifiutato(client, dadi):
    cid = await _pg(client)
    dadi(10)
    assert (await client.post(f"/characters/{cid}/concentration/save", json={"damage": -40})).status_code == 422


@pytest.mark.caccia(id="CB-440", fonte="2014 · Concentrazione · pag. 203", zona="flusso:concentrazione", voce="normale",
                    copre=["POST /characters/{char_id}/concentration/save", "POST /characters/{char_id}/spells/{spell_id}/use"])
async def test_ts_fallito_chiude_concentrazione_e_contatore(client, dadi):
    cid = await _pg(client)
    await _slot(client, cid)
    sid = await _incantesimo(client, cid)
    c = await _lancia(client, cid, sid)
    assert c["concentrating_spell_id"] == sid and c["settings"]["concentration_rounds_left"] == 10
    dadi(2)
    r = (await client.post(f"/characters/{cid}/concentration/save", json={"damage": 40})).json()
    assert (r["success"], r["lost_concentration"]) == (False, True)
    dopo = await _stato(client, cid)
    assert dopo["concentrating_spell_id"] is None
    assert "concentration_rounds_left" not in (dopo["settings"] or {})


@pytest.mark.caccia(id="CB-441", fonte="2014 · Concentrazione · pag. 203", zona="flusso:concentrazione", voce="limiti",
                    copre=["POST /characters/{char_id}/concentration/save"])
async def test_ts_riuscito_alla_soglia_mantiene(client, dadi):
    cid = await _pg(client)
    await _slot(client, cid)
    sid = await _incantesimo(client, cid)
    await _lancia(client, cid, sid)
    # CD 15 (danno 30): con CON 10 serve 15 esatto
    dadi(14)
    r = (await client.post(f"/characters/{cid}/concentration/save", json={"damage": 30})).json()
    assert (r["total"], r["dc"], r["success"]) == (14, 15, False)
    cid2 = await _pg(client)
    await _slot(client, cid2)
    sid2 = await _incantesimo(client, cid2)
    await _lancia(client, cid2, sid2)
    dadi(15)
    r2 = (await client.post(f"/characters/{cid2}/concentration/save", json={"damage": 30})).json()
    assert (r2["total"], r2["success"], r2["lost_concentration"]) == (15, True, False)
    assert (await _stato(client, cid2))["concentrating_spell_id"] == sid2


@pytest.mark.caccia(id="CB-442", fonte="invariante: l'incantesimo di un altro personaggio non è una concentrazione valida", zona="flusso:concentrazione",
                    voce="permessi", copre=["PATCH /characters/{char_id}/concentration"])
async def test_concentrazione_manuale_su_incantesimo_di_un_altro_personaggio(client):
    a = await _pg(client)
    b = await _pg(client)
    altrui = await _incantesimo(client, b)
    r = await client.patch(f"/characters/{a}/concentration", json={"spell_id": altrui})
    assert r.status_code in (400, 404, 422), r.status_code
    assert (await _stato(client, a))["concentrating_spell_id"] is None


@pytest.mark.caccia(id="CB-462", fonte="invariante: un incantesimo inesistente non è una concentrazione valida", zona="flusso:concentrazione",
                    voce="limiti", copre=["PATCH /characters/{char_id}/concentration"])
async def test_concentrazione_manuale_su_incantesimo_inesistente(client):
    a = await _pg(client)
    r = await client.patch(f"/characters/{a}/concentration", json={"spell_id": 987654})
    assert r.status_code in (400, 404, 422), r.status_code
    assert (await _stato(client, a))["concentrating_spell_id"] is None


@pytest.mark.caccia(id="CB-443", fonte="2014 · Concentrazione · pag. 203", zona="flusso:concentrazione", voce="interazione",
                    copre=["POST /characters/{char_id}/spells/{spell_id}/use"])
async def test_secondo_incantesimo_di_concentrazione_sostituisce_il_primo(client):
    cid = await _pg(client)
    await _slot(client, cid)
    a = await _incantesimo(client, cid, "Benedizione", "Concentration, up to 1 minute")
    b = await _incantesimo(client, cid, "Invisibilita", "Concentration, up to 1 hour", livello=2)
    await _slot(client, cid, 2, 2)
    await _lancia(client, cid, a)
    c = await _lancia(client, cid, b, 2)
    assert c["concentrating_spell_id"] == b
    assert c["settings"]["concentration_rounds_left"] == 600


@pytest.mark.caccia(id="CB-444", fonte="comportamento dichiarato: la durata dell'incantesimo scorre a round (1 minuto = 10 round)",
                    zona="flusso:concentrazione", voce="normale", copre=["POST /characters/{char_id}/rounds/tick"])
async def test_durata_un_minuto_finisce_al_decimo_round(client):
    cid = await _pg(client)
    await _slot(client, cid)
    sid = await _incantesimo(client, cid)
    await _lancia(client, cid, sid)
    for _ in range(9):
        assert (await client.post(f"/characters/{cid}/rounds/tick")).status_code == 200
    s = await _stato(client, cid)
    assert s["concentrating_spell_id"] == sid and s["settings"]["concentration_rounds_left"] == 1
    r = (await client.post(f"/characters/{cid}/rounds/tick")).json()
    assert r["concentrating_spell_id"] is None
    assert "Concentrazione" in r["expired_effects"]


@pytest.mark.caccia(id="CB-445", fonte="2014 · Concentrazione · pag. 203", zona="flusso:concentrazione", voce="permessi",
                    copre=["PATCH /characters/{char_id}/concentration", "POST /characters/{char_id}/concentration/save"])
async def test_concentrazione_di_un_altro_utente_rifiutata(client, come_utente):
    cid = await _pg(client)
    await _slot(client, cid)
    sid = await _incantesimo(client, cid)
    await _lancia(client, cid, sid)
    come_utente(9002)
    assert (await client.patch(f"/characters/{cid}/concentration", json={"spell_id": None})).status_code in (403, 404)
    assert (await client.post(f"/characters/{cid}/concentration/save", json={"damage": 99})).status_code in (403, 404)
    come_utente(TEST_USER_ID)
    assert (await _stato(client, cid))["concentrating_spell_id"] == sid


@pytest.mark.caccia(id="CB-446", fonte="2014 · Concentrazione · pag. 203", zona="flusso:concentrazione", voce="annullamento",
                    copre=["DELETE /characters/{char_id}/spells/{spell_id}"])
async def test_eliminare_l_incantesimo_chiude_concentrazione_e_contatore(client):
    cid = await _pg(client)
    await _slot(client, cid)
    sid = await _incantesimo(client, cid)
    await _lancia(client, cid, sid)
    assert (await client.delete(f"/characters/{cid}/spells/{sid}")).status_code == 204
    s = await _stato(client, cid)
    assert s["concentrating_spell_id"] is None
    assert "concentration_rounds_left" not in (s["settings"] or {})


@pytest.mark.caccia(id="CB-447", fonte="2014 · Concentrazione · pag. 203", zona="flusso:concentrazione", voce="regola",
                    copre=["PATCH /characters/{char_id}/hp"])
async def test_danno_chiede_ts_con_cd_giusta_e_nessun_ts_senza_danno(client, dadi):
    cid = await _pg(client)
    await _slot(client, cid)
    sid = await _incantesimo(client, cid)
    await _lancia(client, cid, sid)
    dadi(12)
    r = (await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 24})).json()
    assert r["current_hit_points"] == 4
    assert r["concentration_save"]["dc"] == 12
    assert r["concentration_save"]["lost_concentration"] is False
    r0 = (await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 0}))
    if r0.status_code == 200:
        assert r0.json().get("concentration_save") is None


@pytest.mark.caccia(id="CB-448", fonte="2014 · Concentrazione · pag. 203", zona="flusso:concentrazione", voce="regola",
                    copre=["PATCH /characters/{char_id}/hp"])
@pytest.mark.parametrize("edizione", ["2014", "2024"])
async def test_a_zero_pf_la_concentrazione_finisce_senza_ts(client, edizione):
    cid = await _pg(client, edizione)
    await _slot(client, cid)
    sid = await _incantesimo(client, cid)
    await _lancia(client, cid, sid)
    r = (await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 99})).json()
    assert r["current_hit_points"] == 0
    assert r["concentrating_spell_id"] is None
    assert "concentration_rounds_left" not in (r["settings"] or {})
    cur = (await client.patch(f"/characters/{cid}/hp", json={"op": "heal", "value": 5})).json()
    assert cur["concentrating_spell_id"] is None


@pytest.mark.caccia(id="CB-449", fonte="2014 · Concentrazione · pag. 203; 2024 · pag. 363", zona="flusso:concentrazione", voce="regola",
                    copre=["PATCH /characters/{char_id}/conditions"])
@pytest.mark.parametrize("edizione", ["2014", "2024"])
@pytest.mark.parametrize("condizione", ["incapacitated", "paralyzed", "stunned", "unconscious", "petrified"])
async def test_incapacitato_chiude_la_concentrazione(client, edizione, condizione):
    cid = await _pg(client, edizione)
    await _slot(client, cid)
    sid = await _incantesimo(client, cid)
    await _lancia(client, cid, sid)
    r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": {condizione: True}})
    assert r.status_code == 200, r.text
    s = await _stato(client, cid)
    assert s["concentrating_spell_id"] is None
    assert "concentration_rounds_left" not in (s["settings"] or {})


@pytest.mark.caccia(id="CB-450", fonte="comportamento dichiarato in CLAUDE.md: D8, il riposo breve mantiene la concentrazione, il lungo la chiude",
                    zona="flusso:concentrazione", voce="persistenza", copre=["POST /characters/{char_id}/rest"])
async def test_riposo_breve_mantiene_contatore_il_lungo_chiude_tutto(client):
    cid = await _pg(client)
    await _slot(client, cid)
    sid = await _incantesimo(client, cid, durata="Concentration, up to 1 hour")
    await _lancia(client, cid, sid)
    corto = await client.post(f"/characters/{cid}/rest", json={"rest_type": "short"})
    assert corto.status_code == 200, corto.text
    s = await _stato(client, cid)
    assert s["concentrating_spell_id"] == sid and s["settings"]["concentration_rounds_left"] == 600
    lungo = await client.post(f"/characters/{cid}/rest", json={"rest_type": "long"})
    assert lungo.status_code == 200, lungo.text
    s = await _stato(client, cid)
    assert s["concentrating_spell_id"] is None
    assert "concentration_rounds_left" not in (s["settings"] or {})


@pytest.mark.caccia(id="CB-451", fonte="invariante: l'annullo di un danno rimette la concentrazione com'era, contatore compreso",
                    zona="flusso:concentrazione", voce="annullamento", copre=["POST /characters/{char_id}/hp/undo"])
async def test_annullo_del_danno_ripristina_concentrazione_e_round(client, dadi):
    cid = await _pg(client)
    await _slot(client, cid)
    sid = await _incantesimo(client, cid)
    await _lancia(client, cid, sid)
    await client.post(f"/characters/{cid}/rounds/tick")
    dadi(1)
    r = (await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 24})).json()
    assert r["concentrating_spell_id"] is None
    u = await client.post(f"/characters/{cid}/hp/undo", json={"op_id": r["hp_undo_id"]})
    assert u.status_code == 200, u.text
    s = await _stato(client, cid)
    assert s["current_hit_points"] == 28
    assert s["concentrating_spell_id"] == sid
    assert s["settings"]["concentration_rounds_left"] == 9


@pytest.mark.caccia(id="CB-452", fonte="invariante: export e import conservano la concentrazione in corso e i round che restano",
                    zona="flusso:concentrazione", voce="persistenza",
                    copre=["GET /characters/{char_id}/export", "POST /characters/import", "POST /characters/{char_id}/duplicate"])
async def test_export_import_conserva_round_di_concentrazione(client):
    cid = await _pg(client)
    await _slot(client, cid)
    sid = await _incantesimo(client, cid)
    await _lancia(client, cid, sid)
    await client.post(f"/characters/{cid}/rounds/tick")
    dati = (await client.get(f"/characters/{cid}/export")).json()
    nuovo = (await client.post("/characters/import", json=dati)).json()
    assert nuovo["concentrating_spell_id"] is not None
    assert nuovo["concentrating_spell_id"] != sid
    assert nuovo["settings"].get("concentration_rounds_left") == 9


@pytest.mark.caccia(id="CB-453", fonte="invariante: una durata a round non può essere negativa", zona="flusso:concentrazione", voce="limiti",
                    copre=["PATCH /characters/{char_id}/concentration"])
async def test_durata_manuale_negativa_rifiutata(client):
    cid = await _pg(client)
    sid = await _incantesimo(client, cid)
    r = await client.patch(f"/characters/{cid}/concentration", json={"spell_id": sid, "rounds": -5})
    assert r.status_code == 422, r.status_code
    assert (await _stato(client, cid))["concentrating_spell_id"] is None


@pytest.mark.caccia(id="CB-454", fonte="2014 · Concentrazione · pag. 203", zona="flusso:concentrazione", voce="ripetizione",
                    copre=["PATCH /characters/{char_id}/concentration"])
async def test_chiudere_due_volte_la_concentrazione_registra_una_sola_volta(client):
    cid = await _pg(client)
    await _slot(client, cid)
    sid = await _incantesimo(client, cid)
    await _lancia(client, cid, sid)
    await client.patch(f"/characters/{cid}/concentration", json={"spell_id": None})
    await client.patch(f"/characters/{cid}/concentration", json={"spell_id": None})
    cron = (await client.get(f"/characters/{cid}/history")).json()
    voci = [h for h in (cron if isinstance(cron, list) else cron.get("items", [])) if h["event_type"] == "concentration"]
    assert len(voci) == 1


@pytest.mark.caccia(id="CB-455", fonte="2014 · Concentrazione · pag. 203", zona="flusso:concentrazione", voce="contratto",
                    copre=["PATCH /characters/{char_id}/concentration"])
async def test_concentrazione_manuale_corpo_del_frontend(client):
    cid = await _pg(client)
    sid = await _incantesimo(client, cid)
    r = await client.patch(f"/characters/{cid}/concentration", json={"spell_id": sid})
    assert r.status_code == 200 and r.json()["concentrating_spell_id"] == sid
    assert r.json()["settings"]["concentration_rounds_left"] == 10
    r2 = await client.patch(f"/characters/{cid}/concentration", json={"spell_id": None})
    assert r2.json()["concentrating_spell_id"] is None


def _chiavi(c):
    return sorted(s["key"] for s in (c.get("active_states") or []))


async def _sfocatura(client, cid, edizione="2014"):
    await _slot(client, cid, 2, 2)
    r = await client.post(f"/characters/{cid}/spells", json={
        "name": "Sfocatura", "level": 2, "is_concentration": True, "duration": "Concentration, up to 1 minute",
        "srd_index": "blur", "is_prepared": True})
    assert r.status_code == 201, r.text
    sid = r.json()["id"]
    c = await _lancia(client, cid, sid, 2)
    assert any(k.startswith("spell") for k in _chiavi(c)), _chiavi(c)
    return sid


async def _chiudi_patch(client, cid, sid, dadi):
    await client.patch(f"/characters/{cid}/concentration", json={"spell_id": None})


async def _chiudi_ts(client, cid, sid, dadi):
    dadi(1)
    await client.post(f"/characters/{cid}/concentration/save", json={"damage": 10})


async def _chiudi_tick(client, cid, sid, dadi):
    for _ in range(10):
        await client.post(f"/characters/{cid}/rounds/tick")


async def _chiudi_riposo(client, cid, sid, dadi):
    await client.post(f"/characters/{cid}/rest", json={"rest_type": "long"})


async def _chiudi_elimina(client, cid, sid, dadi):
    await client.delete(f"/characters/{cid}/spells/{sid}")


async def _chiudi_stordito(client, cid, sid, dadi):
    await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"stunned": True}})


async def _chiudi_zero_pf(client, cid, sid, dadi):
    await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 99})


async def _chiudi_altro_incantesimo(client, cid, sid, dadi):
    await _slot(client, cid, 3, 2)
    altro = await _incantesimo(client, cid, "Invisibilita maggiore", "Concentration, up to 1 minute", livello=3)
    r = await client.post(f"/characters/{cid}/spells/{altro}/use", json={"slot_level": 3, "confirm": ["one_slot_per_turn"]})
    assert r.status_code == 200, r.text[:200]


@pytest.mark.caccia(id="CB-456", fonte="comportamento dichiarato in CLAUDE.md: gli stati spell:<chiave> finiscono con la durata, con la concentrazione del lanciatore o all'annullo",
                    zona="flusso:concentrazione", voce="annullamento",
                    copre=["PATCH /characters/{char_id}/concentration", "POST /characters/{char_id}/concentration/save",
                           "POST /characters/{char_id}/rounds/tick", "POST /characters/{char_id}/rest", "DELETE /characters/{char_id}/spells/{spell_id}",
                           "PATCH /characters/{char_id}/conditions", "PATCH /characters/{char_id}/hp"])
@pytest.mark.parametrize("edizione", ["2014", "2024"])
@pytest.mark.parametrize("chiudi", [_chiudi_patch, _chiudi_ts, _chiudi_tick, _chiudi_riposo, _chiudi_elimina, _chiudi_stordito,
                                    _chiudi_zero_pf, _chiudi_altro_incantesimo], ids=lambda f: f.__name__)
async def test_effetto_dell_incantesimo_finisce_con_la_concentrazione(client, dadi, edizione, chiudi):
    cid = await _pg(client, edizione)
    sid = await _sfocatura(client, cid)
    await chiudi(client, cid, sid, dadi)
    s = await _stato(client, cid)
    restano = [k for k in _chiavi(s) if k.startswith("spell:") or k == "spell_cast:blur"]
    assert restano == [], restano


@pytest.mark.caccia(id="CB-458", fonte="2014 · Concentrazione · pag. 203", zona="flusso:concentrazione", voce="regola",
                    copre=["PATCH /characters/{char_id}/hp"])
async def test_cd_concentrazione_usa_il_danno_dopo_la_resistenza(client, dadi):
    cid = await _pg(client)
    await client.patch(f"/characters/{cid}", json={"damage_modifiers": {"resistances": ["fire"]}})
    await _slot(client, cid)
    sid = await _incantesimo(client, cid)
    await _lancia(client, cid, sid)
    dadi(12)
    r = (await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 44, "damage_type": "fire"})).json()
    assert r["current_hit_points"] == 6
    assert r["concentration_save"]["dc"] == 11


@pytest.mark.caccia(id="CB-459", fonte="2014 · Concentrazione · pag. 203", zona="flusso:concentrazione", voce="regola",
                    copre=["PATCH /characters/{char_id}/hp"])
async def test_immune_non_chiede_ts_di_concentrazione(client):
    cid = await _pg(client)
    await client.patch(f"/characters/{cid}", json={"damage_modifiers": {"immunities": ["fire"]}})
    await _slot(client, cid)
    sid = await _incantesimo(client, cid)
    await _lancia(client, cid, sid)
    r = (await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 44, "damage_type": "fire"})).json()
    assert r["current_hit_points"] == 28
    assert r["concentration_save"] is None
    assert r["concentrating_spell_id"] == sid


@pytest.mark.caccia(id="CB-460", fonte="2014 · Concentrazione · pag. 203", zona="flusso:concentrazione", voce="ripetizione",
                    copre=["POST /characters/{char_id}/spells/{spell_id}/use"])
async def test_rilancio_dello_stesso_incantesimo_riparte_dalla_durata(client):
    cid = await _pg(client)
    await _slot(client, cid)
    sid = await _incantesimo(client, cid)
    await _lancia(client, cid, sid)
    for _ in range(4):
        await client.post(f"/characters/{cid}/rounds/tick")
    c = await _lancia(client, cid, sid)
    assert c["concentrating_spell_id"] == sid
    assert c["settings"]["concentration_rounds_left"] == 10


@pytest.mark.caccia(id="CB-461", fonte="invariante: a concentrazione finita non restano impostazioni della concentrazione", zona="flusso:concentrazione",
                    voce="persistenza", copre=["POST /characters/{char_id}/rounds/tick"])
async def test_scadenza_della_durata_pulisce_il_livello_del_lancio(client):
    cid = await _pg(client)
    await _slot(client, cid)
    sid = await _incantesimo(client, cid)
    c = await _lancia(client, cid, sid)
    assert c["settings"]["concentration_level"] == 1
    for _ in range(10):
        await client.post(f"/characters/{cid}/rounds/tick")
    s = await _stato(client, cid)
    assert s["concentrating_spell_id"] is None
    assert [k for k in (s["settings"] or {}) if k.startswith("concentration")] == []


async def _concentrato_al_terzo(client) -> int:
    cid = await _pg(client)
    for op, v in (("set_max", 60), ("set_current", 60)):
        await client.patch(f"/characters/{cid}/hp", json={"op": op, "value": v})
    await _slot(client, cid, 3, 2)
    c = await _lancia(client, cid, await _incantesimo(client, cid), livello=3)
    assert c["settings"]["concentration_level"] == 3
    return cid


@pytest.mark.caccia(id="CB-759", fonte="invariante: un annullamento rimette tutto com'era", zona="flusso:concentrazione", voce="annullamento",
                    copre=["POST /characters/{char_id}/hp/undo"])
async def test_annullare_il_danno_rimette_il_livello_del_lancio(client, dadi):
    cid = await _concentrato_al_terzo(client)
    dadi(1)
    c = (await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 5})).json()
    assert c["concentrating_spell_id"] is None
    r = await client.post(f"/characters/{cid}/hp/undo", json={"op_id": c["hp_undo_id"]})
    assert r.status_code == 200, r.text
    s = await _stato(client, cid)
    assert s["concentrating_spell_id"] is not None
    assert s["settings"].get("concentration_level") == 3


@pytest.mark.caccia(id="CB-760", fonte="invariante: un tiro salvezza ritirato con successo rimette la concentrazione com'era", zona="flusso:concentrazione",
                    voce="annullamento", copre=["POST /characters/{char_id}/concentration/save"])
async def test_il_ritiro_riuscito_rimette_il_livello_del_lancio(client, test_session_factory):
    from api.routers._helpers import _lose_concentration, retouch_concentration
    from api.services.character_load import get_owned_full

    cid = await _concentrato_al_terzo(client)
    async with test_session_factory() as s:
        char = await get_owned_full(cid, TEST_USER_ID, s)
        snapshot = await _lose_concentration(s, char)
        assert "concentration_level" not in char.settings
        tiro = {"die": 15, "bonus": 0, "total": 15, "mode": "normal", "dice": [15], "notes": [], "auto_fail": False}
        await retouch_concentration(s, char, {"dc": 10, "lost": True, "snapshot": snapshot}, tiro)
        assert char.settings.get("concentration_level") == 3


@pytest.mark.caccia(id="CB-770", fonte="invariante: le impostazioni scritte dal server non si cambiano né si perdono salvando le preferenze", zona="flusso:concentrazione",
                    voce="persistenza", copre=["PATCH /characters/{char_id}"])
async def test_salvare_le_impostazioni_non_tocca_il_livello_del_lancio(client):
    cid = await _concentrato_al_terzo(client)
    for settings in ({"quick_actions": []}, {"concentration_level": 9}):  # lettura vecchia, valore inventato
        assert (await client.patch(f"/characters/{cid}", json={"settings": settings})).status_code == 200
        assert (await _stato(client, cid))["settings"]["concentration_level"] == 3
