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


# ---------------------------------------------------------------------------
# Giro successivo: concentrazione da oggetto, turni in uno scontro, morte, bersagli in serata
# ---------------------------------------------------------------------------
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, seed_session  # noqa: E402
from tests.integration.rules.test_2014_bard_inspiration import _seat  # noqa: E402
from tests.integration.test_magic_items import _item  # noqa: E402


async def _bacchetta(client, cid, nome="Raggio Fantasma", durata="Concentration, up to 1 minute", cariche=5) -> int:
    incantesimo = {"name": nome, "level": 2, "charges_cost": 1, "is_concentration": True, "duration": durata}
    return await _item(client, cid, name="Bacchetta", charges={"current": cariche, "max": cariche}, granted_spells=[incantesimo])


async def _usa_oggetto(client, cid, iid):
    r = await client.post(f"/characters/{cid}/items/{iid}/cast", json={"spell_index": 0})
    assert r.status_code == 200, r.text
    return r.json()


async def _pg_con_bacchetta(client, dadi, edizione="2014"):
    cid = await _pg(client, edizione)
    iid = await _bacchetta(client, cid)
    dadi(3)
    c = await _usa_oggetto(client, cid, iid)
    return cid, iid, c


@pytest.mark.caccia(id="CB-1173", fonte="comportamento dichiarato in CLAUDE.md: POST /items/{item_id}/cast consuma cariche e avvia la concentrazione", zona="flusso:concentrazione",
                    voce="normale", copre=["POST /characters/{char_id}/items/{item_id}/cast"])
async def test_incantesimo_di_oggetto_avvia_concentrazione_e_spende_una_carica(client, dadi):
    cid, iid, c = await _pg_con_bacchetta(client, dadi)
    assert c["concentrating_spell_id"] is None
    assert c["settings"]["concentration_item_spell"] == {"item_id": iid, "name": "Raggio Fantasma"}
    assert c["settings"]["concentration_rounds_left"] == 10
    item = next(i for i in (await client.get(f"/characters/{cid}/items")).json() if i["id"] == iid)
    assert item["item_metadata"]["charges"]["current"] == 4


@pytest.mark.caccia(id="CB-1174", fonte="2014 · Concentrazione · pag. 203", zona="flusso:concentrazione", voce="regola",
                    copre=["PATCH /characters/{char_id}/hp"])
async def test_danno_con_concentrazione_da_oggetto_chiede_il_ts_e_la_perde(client, dadi):
    cid, _, _ = await _pg_con_bacchetta(client, dadi)
    dadi(1)
    r = (await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 24})).json()
    assert r["concentration_save"]["dc"] == 12 and r["concentration_save"]["lost_concentration"] is True
    s = await _stato(client, cid)
    assert [k for k in (s["settings"] or {}) if k.startswith("concentration")] == []


@pytest.mark.caccia(id="CB-1175", fonte="2014 · Concentrazione · pag. 203", zona="flusso:concentrazione", voce="regola",
                    copre=["PATCH /characters/{char_id}/hp"])
@pytest.mark.parametrize("edizione", ["2014", "2024"])
async def test_a_zero_pf_finisce_anche_la_concentrazione_da_oggetto(client, dadi, edizione):
    cid, _, _ = await _pg_con_bacchetta(client, dadi, edizione)
    r = (await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 99})).json()
    assert r["current_hit_points"] == 0
    assert [k for k in (r["settings"] or {}) if k.startswith("concentration")] == []


@pytest.mark.caccia(id="CB-1176", fonte="2014 · Concentrazione · pag. 203; 2024 · pag. 363", zona="flusso:concentrazione", voce="regola",
                    copre=["PATCH /characters/{char_id}/conditions"])
@pytest.mark.parametrize("condizione", ["incapacitated", "stunned", "paralyzed"])
async def test_incapacitato_chiude_la_concentrazione_da_oggetto(client, dadi, condizione):
    cid, _, _ = await _pg_con_bacchetta(client, dadi)
    r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": {condizione: True}})
    assert r.status_code == 200, r.text
    s = await _stato(client, cid)
    assert [k for k in (s["settings"] or {}) if k.startswith("concentration")] == []


@pytest.mark.caccia(id="CB-1177", fonte="comportamento dichiarato in CLAUDE.md: D8, il riposo breve mantiene la concentrazione, il lungo la chiude", zona="flusso:concentrazione",
                    voce="persistenza", copre=["POST /characters/{char_id}/rest"])
async def test_riposo_e_concentrazione_da_oggetto(client, dadi):
    cid, iid, _ = await _pg_con_bacchetta(client, dadi)
    assert (await client.post(f"/characters/{cid}/rest", json={"rest_type": "short"})).status_code == 200
    assert (await _stato(client, cid))["settings"]["concentration_item_spell"]["item_id"] == iid
    assert (await client.post(f"/characters/{cid}/rest", json={"rest_type": "long"})).status_code == 200
    s = await _stato(client, cid)
    assert [k for k in (s["settings"] or {}) if k.startswith("concentration")] == []


@pytest.mark.caccia(id="CB-1178", fonte="comportamento dichiarato in CLAUDE.md: la durata è a round e scade con i tick", zona="flusso:concentrazione", voce="normale",
                    copre=["POST /characters/{char_id}/rounds/tick"])
async def test_la_concentrazione_da_oggetto_scade_al_decimo_round(client, dadi):
    cid, _, _ = await _pg_con_bacchetta(client, dadi)
    for _ in range(9):
        await client.post(f"/characters/{cid}/rounds/tick")
    assert (await _stato(client, cid))["settings"]["concentration_rounds_left"] == 1
    r = (await client.post(f"/characters/{cid}/rounds/tick")).json()
    assert "Concentrazione" in r["expired_effects"]
    assert [k for k in (r["settings"] or {}) if k.startswith("concentration")] == []


@pytest.mark.caccia(id="CB-1179", fonte="comportamento dichiarato nel codice: interrompere la concentrazione si scrive nella Cronologia", zona="flusso:concentrazione",
                    voce="annullamento", copre=["PATCH /characters/{char_id}/concentration", "GET /characters/{char_id}/history"])
async def test_interrompere_la_concentrazione_da_oggetto_si_scrive_nella_cronologia(client, dadi):
    cid, _, _ = await _pg_con_bacchetta(client, dadi)
    r = await client.patch(f"/characters/{cid}/concentration", json={"spell_id": None})
    assert r.status_code == 200
    assert [k for k in (r.json()["settings"] or {}) if k.startswith("concentration")] == []
    cron = (await client.get(f"/characters/{cid}/history")).json()
    voci = [h for h in (cron if isinstance(cron, list) else cron.get("items", [])) if h["event_type"] == "concentration"]
    assert len(voci) == 1


from core.rules.spell_effects import SPELL_STATE_PREFIX  # noqa: E402
from tests.integration._encounter_helpers import setup_full_encounter  # noqa: E402

BLESS = f"{SPELL_STATE_PREFIX}bless"


async def _benedizione(client, user, nome="Benedizione", durata="Concentration, up to 1 minute", livello_slot=1):
    """Un incantatore dell'utente con Benedizione (catalogo) e due slot di 1° livello: (personaggio, incantesimo)."""
    as_user(user)
    cid = (await client.post("/characters", json={"name": nome + str(user)})).json()["id"]
    for op, v in (("set_max", 40), ("set_current", 40)):
        await client.patch(f"/characters/{cid}/hp", json={"op": op, "value": v})
    r = await client.post(f"/characters/{cid}/spells", json={
        "name": "Bless", "srd_index": "bless", "level": 1, "is_concentration": True, "duration": durata, "is_prepared": True})
    assert r.status_code == 201, r.text
    assert (await client.post(f"/characters/{cid}/spell_slots", json={"level": 1, "total": 2})).status_code == 201
    return cid, r.json()["id"]


async def _benedici(client, user, cid, sid, bersagli):
    as_user(user)
    r = await client.post(f"/characters/{cid}/spells/{sid}/use", json={"slot_level": 1, "targets": bersagli})
    assert r.status_code == 200, r.text
    return r.json()


async def _stati(client, cid, user, chiave=BLESS):
    as_user(user)
    return [s for s in (await _stato(client, cid))["active_states"] or [] if s["key"] == chiave]


async def _serata_con_benedizione(client, fabbrica):
    sid, eroe = await seed_session(fabbrica)
    chierico, spell = await _benedizione(client, GM_ID)
    await _seat(fabbrica, chierico, GM_ID)
    await _benedici(client, GM_ID, chierico, spell, [eroe])
    assert len(await _stati(client, eroe, PLAYER_ID)) == 1
    as_user(GM_ID)
    return sid, eroe, chierico, spell


async def _ally_patch(client, c, s, d):
    await client.patch(f"/characters/{c}/concentration", json={"spell_id": None})


async def _ally_ts(client, c, s, d):
    d(1)
    await client.post(f"/characters/{c}/concentration/save", json={"damage": 10})


async def _ally_zero(client, c, s, d):
    await client.patch(f"/characters/{c}/hp", json={"op": "damage", "value": 99})


async def _ally_set_zero(client, c, s, d):
    await client.patch(f"/characters/{c}/hp", json={"op": "set_current", "value": 0})


async def _ally_incapacitato(client, c, s, d):
    await client.patch(f"/characters/{c}/conditions", json={"conditions": {"incapacitated": True}})


async def _ally_riposo(client, c, s, d):
    await client.post(f"/characters/{c}/rest", json={"rest_type": "long"})


async def _ally_tick(client, c, s, d):
    for _ in range(10):
        await client.post(f"/characters/{c}/rounds/tick")


async def _ally_elimina(client, c, s, d):
    await client.delete(f"/characters/{c}/spells/{s}")


async def _ally_altro(client, c, s, d):
    await client.post(f"/characters/{c}/spell_slots", json={"level": 2, "total": 2})
    r = await client.post(f"/characters/{c}/spells", json={"name": "Altro", "level": 2, "is_concentration": True,
                                                            "duration": "Concentration, up to 1 minute", "is_prepared": True})
    await client.post(f"/characters/{c}/spells/{r.json()['id']}/use", json={"slot_level": 2, "confirm": ["one_slot_per_turn"]})


@pytest.mark.caccia(id="CB-1181", fonte="comportamento dichiarato in CLAUDE.md: gli stati spell:<chiave> sui bersagli finiscono con la concentrazione del lanciatore",
                    zona="flusso:concentrazione", voce="annullamento",
                    copre=["PATCH /characters/{char_id}/concentration", "POST /characters/{char_id}/concentration/save", "PATCH /characters/{char_id}/hp",
                           "PATCH /characters/{char_id}/conditions", "POST /characters/{char_id}/rest", "POST /characters/{char_id}/rounds/tick",
                           "DELETE /characters/{char_id}/spells/{spell_id}", "POST /characters/{char_id}/spells/{spell_id}/use"])
@pytest.mark.parametrize("chiudi", [_ally_patch, _ally_ts, _ally_zero, _ally_set_zero, _ally_incapacitato, _ally_riposo, _ally_tick, _ally_elimina, _ally_altro],
                         ids=lambda f: f.__name__)
async def test_effetto_sull_alleato_cade_quando_il_lanciatore_perde_la_concentrazione(client, test_session_factory, dadi, chiudi):
    _, eroe, chierico, spell = await _serata_con_benedizione(client, test_session_factory)
    await chiudi(client, chierico, spell, dadi)
    assert await _stati(client, eroe, PLAYER_ID) == []
    assert (await _stati(client, chierico, GM_ID, "spell_cast:bless")) == []


@pytest.mark.caccia(id="CB-1182", fonte="invariante: un annullamento rimette tutto com'era, anche l'effetto sull'alleato", zona="flusso:concentrazione", voce="annullamento",
                    copre=["PATCH /characters/{char_id}/hp", "POST /characters/{char_id}/hp/undo"])
async def test_annullare_il_danno_che_rompe_la_concentrazione_rimette_l_effetto_sull_alleato(client, test_session_factory, dadi):
    _, eroe, chierico, spell = await _serata_con_benedizione(client, test_session_factory)
    dadi(1)
    r = (await client.patch(f"/characters/{chierico}/hp", json={"op": "damage", "value": 24})).json()
    assert r["concentrating_spell_id"] is None
    assert await _stati(client, eroe, PLAYER_ID) == []
    as_user(GM_ID)
    u = await client.post(f"/characters/{chierico}/hp/undo", json={"op_id": r["hp_undo_id"]})
    assert u.status_code == 200, u.text
    assert (await _stato(client, chierico))["concentrating_spell_id"] == spell
    assert len(await _stati(client, eroe, PLAYER_ID)) == 1


@pytest.mark.caccia(id="CB-1183", fonte="comportamento dichiarato in CLAUDE.md: gli stati di un incantesimo finiscono con la concentrazione, anche se lanciato da un oggetto", zona="flusso:concentrazione",
                    voce="interazione", copre=["POST /characters/{char_id}/items/{item_id}/cast", "PATCH /characters/{char_id}/hp"])
async def test_incantesimo_di_oggetto_sull_alleato_cade_con_la_concentrazione(client, test_session_factory, dadi):
    sid, eroe = await seed_session(test_session_factory)
    as_user(GM_ID)
    cid = (await client.post("/characters", json={"name": "Portatore"})).json()["id"]
    for op, v in (("set_max", 40), ("set_current", 40)):
        await client.patch(f"/characters/{cid}/hp", json={"op": op, "value": v})
    await _seat(test_session_factory, cid, GM_ID)
    spell = {"name": "Bless", "srd_index": "bless", "level": 1, "charges_cost": 1, "is_concentration": True}
    as_user(GM_ID)
    iid = await _item(client, cid, name="Bastone", charges={"current": 3, "max": 3}, granted_spells=[spell])
    dadi(3)
    r = await client.post(f"/characters/{cid}/items/{iid}/cast", json={"spell_index": 0, "targets": [eroe]})
    assert r.status_code == 200, r.text
    assert len(await _stati(client, eroe, PLAYER_ID)) == 1
    as_user(GM_ID)
    dadi(1)
    await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 24})
    assert await _stati(client, eroe, PLAYER_ID) == []


@pytest.mark.caccia(id="CB-1184", fonte="2014 · Concentrazione · pag. 203", zona="flusso:concentrazione", voce="interazione",
                    copre=["POST /characters/{char_id}/spells/{spell_id}/use"])
async def test_stesso_incantesimo_di_due_lanciatori_non_cade_per_uno_solo(client, test_session_factory, dadi):
    sid, eroe = await seed_session(test_session_factory)
    chierico, spell = await _benedizione(client, GM_ID)
    await _seat(test_session_factory, chierico, GM_ID)
    await _benedici(client, GM_ID, chierico, spell, [eroe])
    as_user(PLAYER_ID)  # l'eroe benedice sé stesso con la sua copia dell'incantesimo
    for op, v in (("set_max", 40), ("set_current", 40)):
        await client.patch(f"/characters/{eroe}/hp", json={"op": op, "value": v})
    r = await client.post(f"/characters/{eroe}/spells", json={"name": "Bless", "srd_index": "bless", "level": 1, "is_concentration": True,
                                                              "duration": "Concentration, up to 1 minute", "is_prepared": True})
    await client.post(f"/characters/{eroe}/spell_slots", json={"level": 1, "total": 2})
    await _benedici(client, PLAYER_ID, eroe, r.json()["id"], [eroe])
    as_user(GM_ID)
    await client.patch(f"/characters/{chierico}/concentration", json={"spell_id": None})
    assert len(await _stati(client, eroe, PLAYER_ID)) >= 1


async def _eroe_incantatore(client, eroe, durata="Concentration, up to 1 minute"):
    as_user(PLAYER_ID)
    for op, v in (("set_max", 40), ("set_current", 40)):
        await client.patch(f"/characters/{eroe}/hp", json={"op": op, "value": v})
    r = await client.post(f"/characters/{eroe}/spells", json={"name": "Benedizione", "level": 1, "is_concentration": True,
                                                              "duration": durata, "is_prepared": True})
    assert r.status_code == 201, r.text
    assert (await client.post(f"/characters/{eroe}/spell_slots", json={"level": 1, "total": 3})).status_code == 201
    return r.json()["id"]


async def _incontro_attivo(client, fabbrica):
    """Eroe primo in iniziativa, poi due goblin; l'incontro è avviato. Restituisce (sessione, eroe, incantesimo)."""
    sid, enc = await setup_full_encounter(client, fabbrica)
    eroe = next(c for c in enc["combatants"] if c["kind"] == "pc")["character_id"]
    spell = await _eroe_incantatore(client, eroe)
    as_user(GM_ID)
    r = await client.post(f"/sessions/{sid}/encounter/start", json={})
    assert r.status_code == 200, r.text
    return sid, eroe, spell


async def _avanti(client, sid, n=1):
    as_user(GM_ID)
    for _ in range(n):
        r = await client.post(f"/sessions/{sid}/encounter/next-turn")
        assert r.status_code == 200, r.text


async def _stato_eroe(client, eroe):
    as_user(PLAYER_ID)
    return await _stato(client, eroe)


async def _round_rimasti(client, eroe):
    return ((await _stato_eroe(client, eroe))["settings"] or {}).get("concentration_rounds_left")


@pytest.mark.caccia(id="CB-1185", fonte="comportamento dichiarato nel codice: in uno scontro i round di concentrazione scendono all'inizio del turno del lanciatore, non a ogni turno", zona="flusso:concentrazione",
                    voce="normale", copre=["POST /sessions/{session_id}/encounter/next-turn", "POST /characters/{char_id}/spells/{spell_id}/use"])
async def test_in_uno_scontro_il_contatore_scende_solo_al_turno_del_lanciatore(client, test_session_factory):
    sid, eroe, spell = await _incontro_attivo(client, test_session_factory)
    await _benedici(client, PLAYER_ID, eroe, spell, [])
    assert await _round_rimasti(client, eroe) == 10
    await _avanti(client, sid, 2)  # turni dei due goblin
    assert await _round_rimasti(client, eroe) == 10
    await _avanti(client, sid, 1)  # di nuovo il turno dell'eroe
    assert await _round_rimasti(client, eroe) == 9


@pytest.mark.caccia(id="CB-1186", fonte="comportamento dichiarato in CLAUDE.md: un minuto di concentrazione sono 10 round e l'effetto sugli alleati finisce con lei", zona="flusso:concentrazione",
                    voce="normale", copre=["POST /sessions/{session_id}/encounter/next-turn"])
async def test_in_uno_scontro_la_concentrazione_finisce_al_decimo_round(client, test_session_factory):
    sid, eroe, spell = await _incontro_attivo(client, test_session_factory)
    await _benedici(client, PLAYER_ID, eroe, spell, [eroe])
    assert len(await _stati(client, eroe, PLAYER_ID)) == 1
    await _avanti(client, sid, 3 * 9)  # nove giri completi
    assert await _round_rimasti(client, eroe) == 1
    assert (await _stato_eroe(client, eroe))["concentrating_spell_id"] == spell
    await _avanti(client, sid, 3)
    s = await _stato_eroe(client, eroe)
    assert s["concentrating_spell_id"] is None
    assert [k for k in (s["settings"] or {}) if k.startswith("concentration")] == []
    assert await _stati(client, eroe, PLAYER_ID) == []


@pytest.mark.caccia(id="CB-1187", fonte="comportamento dichiarato nel codice: durante uno scontro il tick manuale raddoppierebbe il conteggio, quindi è rifiutato", zona="flusso:concentrazione",
                    voce="ripetizione", copre=["POST /characters/{char_id}/rounds/tick"])
async def test_tick_manuale_rifiutato_in_uno_scontro_e_il_contatore_non_cambia(client, test_session_factory):
    sid, eroe, spell = await _incontro_attivo(client, test_session_factory)
    await _benedici(client, PLAYER_ID, eroe, spell, [])
    as_user(PLAYER_ID)
    r = await client.post(f"/characters/{eroe}/rounds/tick")
    assert r.status_code == 409
    assert await _round_rimasti(client, eroe) == 10


@pytest.mark.caccia(id="CB-1188", fonte="invariante: il turno indietro rimette la concentrazione e l'effetto sull'alleato com'erano", zona="flusso:concentrazione",
                    voce="annullamento", copre=["POST /sessions/{session_id}/encounter/prev-turn", "POST /sessions/{session_id}/encounter/next-turn"])
async def test_turno_indietro_dopo_la_scadenza_rimette_concentrazione_ed_effetti(client, test_session_factory):
    sid, eroe, spell = await _incontro_attivo(client, test_session_factory)
    await _benedici(client, PLAYER_ID, eroe, spell, [eroe])
    await _avanti(client, sid, 3 * 9 + 2)  # ultimo goblin del nono giro
    assert await _round_rimasti(client, eroe) == 1
    await _avanti(client, sid, 1)  # scade
    assert (await _stato_eroe(client, eroe))["concentrating_spell_id"] is None
    as_user(GM_ID)
    r = await client.post(f"/sessions/{sid}/encounter/prev-turn")
    assert r.status_code == 200, r.text
    s = await _stato_eroe(client, eroe)
    assert s["concentrating_spell_id"] == spell and s["settings"]["concentration_rounds_left"] == 1
    assert len(await _stati(client, eroe, PLAYER_ID)) == 1


@pytest.mark.caccia(id="CB-1189", fonte="2014 · Concentrazione · pag. 203", zona="flusso:concentrazione", voce="regola",
                    copre=["POST /sessions/{session_id}/encounter/combatants/{combatant_id}/conditions"])
@pytest.mark.parametrize("condizione", ["stunned", "incapacitated"])
async def test_il_master_che_stordisce_un_pg_gli_fa_cadere_la_concentrazione(client, test_session_factory, condizione):
    sid, eroe, spell = await _incontro_attivo(client, test_session_factory)
    await _benedici(client, PLAYER_ID, eroe, spell, [eroe])
    as_user(GM_ID)
    live = (await client.post(f"/sessions/{sid}/encounter/sync-pcs")).json()
    pc = next(c for c in live["combatants"] if c["kind"] == "pc")
    r = await client.post(f"/sessions/{sid}/encounter/combatants/{pc['id']}/conditions", json={"slug": condizione, "value": True})
    assert r.status_code == 200, r.text
    s = await _stato_eroe(client, eroe)
    assert s["concentrating_spell_id"] is None
    assert await _stati(client, eroe, PLAYER_ID) == []


@pytest.mark.caccia(id="CB-1190", fonte="2014 · Concentrazione · pag. 203", zona="flusso:concentrazione", voce="regola",
                    copre=["PATCH /characters/{char_id}/conditions"])
@pytest.mark.parametrize("edizione", ["2014", "2024"])
async def test_la_morte_per_spossatezza_chiude_la_concentrazione(client, dadi, edizione):
    cid = await _pg(client, edizione)
    await _slot(client, cid)
    sid = await _incantesimo(client, cid)
    await _lancia(client, cid, sid)
    r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"exhaustion": 6}})
    assert r.status_code == 200, r.text
    s = await _stato(client, cid)
    assert s["is_dead"] is True
    assert s["concentrating_spell_id"] is None


@pytest.mark.caccia(id="CB-1191", fonte="2024 · Concentrazione · pag. 363", zona="flusso:concentrazione", voce="edizioni",
                    copre=["PATCH /characters/{char_id}/hp"])
async def test_2024_tramortito_a_zero_non_resta_concentrato(client, dadi):
    cid = await _pg(client, "2024")
    await _slot(client, cid)
    sid = await _incantesimo(client, cid)
    await _lancia(client, cid, sid)
    r = (await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 30, "knock_out": True})).json()
    assert r["current_hit_points"] == 1 and r["conditions"].get("unconscious") is True
    assert r["concentrating_spell_id"] is None


@pytest.mark.caccia(id="CB-1192", fonte="invariante: l'annullo di un danno rimette la concentrazione da oggetto com'era", zona="flusso:concentrazione", voce="annullamento",
                    copre=["POST /characters/{char_id}/hp/undo"])
async def test_annullo_del_danno_ripristina_la_concentrazione_da_oggetto(client, dadi):
    cid, iid, _ = await _pg_con_bacchetta(client, dadi)
    await client.post(f"/characters/{cid}/rounds/tick")
    dadi(1)
    r = (await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 24})).json()
    assert [k for k in (r["settings"] or {}) if k.startswith("concentration")] == []
    u = await client.post(f"/characters/{cid}/hp/undo", json={"op_id": r["hp_undo_id"]})
    assert u.status_code == 200, u.text
    s = await _stato(client, cid)
    assert s["settings"]["concentration_item_spell"] == {"item_id": iid, "name": "Raggio Fantasma"}
    assert s["settings"]["concentration_rounds_left"] == 9


@pytest.mark.caccia(id="CB-1193", fonte="2014 · Concentrazione · pag. 203", zona="flusso:concentrazione", voce="interazione",
                    copre=["POST /characters/{char_id}/items/{item_id}/cast"])
async def test_incantesimo_di_oggetto_sostituisce_la_concentrazione_di_un_incantesimo_e_i_suoi_effetti(client, test_session_factory, dadi):
    sid, eroe = await seed_session(test_session_factory)
    chierico, spell = await _benedizione(client, GM_ID)
    await _seat(test_session_factory, chierico, GM_ID)
    await _benedici(client, GM_ID, chierico, spell, [eroe])
    as_user(GM_ID)
    iid = await _bacchetta(client, chierico)
    dadi(3)
    c = await _usa_oggetto(client, chierico, iid)
    assert c["concentrating_spell_id"] is None and c["settings"]["concentration_item_spell"]["item_id"] == iid
    assert await _stati(client, eroe, PLAYER_ID) == []


@pytest.mark.caccia(id="CB-1194", fonte="invariante: un lancio rifiutato per cariche finite non spende né cambia nulla", zona="flusso:concentrazione", voce="limiti",
                    copre=["POST /characters/{char_id}/items/{item_id}/cast"])
async def test_oggetto_senza_cariche_non_toglie_la_concentrazione_in_corso(client, dadi):
    cid = await _pg(client)
    await _slot(client, cid)
    sid = await _incantesimo(client, cid)
    await _lancia(client, cid, sid)
    iid = await _bacchetta(client, cid, cariche=1)
    dadi(3)
    await _usa_oggetto(client, cid, iid)  # l'ultima carica
    await _lancia(client, cid, sid)  # la concentrazione torna all'incantesimo della lista
    r = await client.post(f"/characters/{cid}/items/{iid}/cast", json={"spell_index": 0})
    assert r.status_code == 409, r.text
    s = await _stato(client, cid)
    assert s["concentrating_spell_id"] == sid and "concentration_item_spell" not in s["settings"]


@pytest.mark.caccia(id="CB-1195", fonte="2014 · Concentrazione · pag. 203", zona="flusso:concentrazione", voce="ripetizione",
                    copre=["POST /characters/{char_id}/items/{item_id}/cast"])
async def test_rilancio_dall_oggetto_riparte_dalla_durata_e_spende_una_carica_per_lancio(client, dadi):
    cid, iid, _ = await _pg_con_bacchetta(client, dadi)
    for _ in range(4):
        await client.post(f"/characters/{cid}/rounds/tick")
    dadi(3)
    c = await _usa_oggetto(client, cid, iid)
    assert c["settings"]["concentration_rounds_left"] == 10
    item = next(i for i in (await client.get(f"/characters/{cid}/items")).json() if i["id"] == iid)
    assert item["item_metadata"]["charges"]["current"] == 3


@pytest.mark.caccia(id="CB-1196", fonte="invariante: i dati di un altro utente non si toccano", zona="flusso:concentrazione", voce="permessi",
                    copre=["POST /characters/{char_id}/items/{item_id}/cast"])
async def test_lancio_da_oggetto_di_un_altro_utente_rifiutato(client, dadi, come_utente):
    cid = await _pg(client)
    iid = await _bacchetta(client, cid)
    come_utente(9002)
    r = await client.post(f"/characters/{cid}/items/{iid}/cast", json={"spell_index": 0})
    assert r.status_code in (403, 404)
    come_utente(TEST_USER_ID)
    s = await _stato(client, cid)
    assert "concentration_item_spell" not in (s["settings"] or {})
    item = next(i for i in (await client.get(f"/characters/{cid}/items")).json() if i["id"] == iid)
    assert item["item_metadata"]["charges"]["current"] == 5


@pytest.mark.caccia(id="CB-1197", fonte="2014 · Concentrazione · pag. 203", zona="flusso:concentrazione", voce="limiti",
                    copre=["POST /characters/{char_id}/concentration/save"])
@pytest.mark.parametrize("danno,cd", [(1, 10), (2, 10), (3, 10), (23, 11), (2000000, 1000000)])
async def test_cd_con_danni_piccoli_e_enormi(client, dadi, danno, cd):
    cid = await _pg(client)
    dadi(10)
    r = await client.post(f"/characters/{cid}/concentration/save", json={"damage": danno})
    assert r.status_code == 200, r.text
    assert r.json()["dc"] == cd


@pytest.mark.caccia(id="CB-1198", fonte="2014 · Concentrazione · pag. 203", zona="flusso:concentrazione", voce="regola",
                    copre=["PATCH /characters/{char_id}/hp"])
async def test_danno_assorbito_dai_pf_temporanei_chiede_comunque_il_ts_con_il_danno_intero(client, dadi):
    cid = await _pg(client)
    await _slot(client, cid)
    sid = await _incantesimo(client, cid)
    await _lancia(client, cid, sid)
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_temp", "value": 20})
    dadi(15)
    r = (await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 14})).json()
    assert r["current_hit_points"] == 28 and r["temp_hp"] == 6
    assert r["concentration_save"]["dc"] == 10


@pytest.mark.caccia(id="CB-1508", fonte="invariante (come CB-1203): la concentrazione da oggetto si vede come le altre", zona="flusso:concentrazione", voce="interazione",
                    copre=["GET /sessions/{session_id}/live"])
async def test_la_serata_mostra_la_concentrazione_da_oggetto(client, test_session_factory, dadi):
    sid, _eroe = await seed_session(test_session_factory)
    as_user(GM_ID)
    cid, _iid, _c = await _pg_con_bacchetta(client, dadi)
    await _seat(test_session_factory, cid, GM_ID)
    vivi = (await client.get(f"/sessions/{sid}/live")).json()["live_characters"]
    [foto] = [c for c in vivi if c["id"] == cid]
    assert (foto["is_concentrating"], foto["concentration_spell"]) == (True, "Raggio Fantasma")


@pytest.mark.caccia(id="CB-1517", fonte="invariante (come CB-1179): interrompere la concentrazione si scrive in Cronologia", zona="flusso:concentrazione", voce="annullamento",
                    copre=["DELETE /characters/{char_id}/active-states/{key}"])
async def test_termina_sull_orologio_si_scrive_in_cronologia(client):
    from core.rules.spell_effects import SPELL_CLOCK_PREFIX
    from tests.integration._encounter_helpers import PLAYER_ID as P
    cid, sid = await _benedizione(client, P)
    await _benedici(client, P, cid, sid, [cid])
    r = await client.delete(f"/characters/{cid}/active-states/{SPELL_CLOCK_PREFIX}bless")
    assert r.status_code == 200, r.text
    voci = (await client.get(f"/characters/{cid}/history")).json()
    assert any(v["event_type"] == "concentration" and "interrotta" in v["description"] for v in voci)


@pytest.mark.caccia(id="CB-1538", fonte="invariante: un valore nullo dove non può esserlo si rifiuta, non rompe il server", zona="flusso:concentrazione", voce="contratto",
                    copre=["PATCH /characters/{char_id}/spells/{spell_id}"])
@pytest.mark.parametrize("campo", ["name", "level", "is_concentration", "is_ritual", "is_pinned", "is_prepared"])
async def test_incantesimo_con_un_campo_obbligatorio_nullo_rifiutato(client, campo):
    cid = await _pg(client)
    sid = await _incantesimo(client, cid)
    assert (await client.patch(f"/characters/{cid}/spells/{sid}", json={campo: None})).status_code == 422


@pytest.mark.caccia(id="CB-1534", fonte="2014 · Concentrazione · pag. 203; 2024 · Glossario, Concentrazione: gli effetti finiscono con la concentrazione, anche se l'incantesimo viene da un oggetto",
                    zona="flusso:concentrazione", voce="interazione",
                    copre=["POST /sessions/{session_id}/encounter/combatants/{combatant_id}/conditions", "PATCH /characters/{char_id}/concentration"])
async def test_condizione_legata_alla_concentrazione_da_oggetto(client, test_session_factory, dadi):
    from sqlalchemy import select
    from core.db.models import Character, ConditionEffect
    sid, enc = await setup_full_encounter(client, test_session_factory)
    async with test_session_factory() as s:
        cid = (await s.execute(select(Character.id).where(Character.user_id == PLAYER_ID))).scalar_one()
    as_user(GM_ID)
    await client.post(f"/sessions/{sid}/encounter/start", json={})
    pc = next(c["id"] for c in enc["combatants"] if c["kind"] == "pc")
    mostro = next(c["id"] for c in enc["combatants"] if c["kind"] == "monster")
    as_user(PLAYER_ID)
    iid = await _bacchetta(client, cid)
    luce = await _incantesimo(client, cid, "Luce", conc=False, livello=0)
    dadi(3)
    await _usa_oggetto(client, cid, iid)
    as_user(GM_ID)
    r = await client.post(f"/sessions/{sid}/encounter/combatants/{mostro}/conditions",
                          json={"slug": "charmed", "source_combatant_id": pc, "ends_with_concentration": True})
    assert r.status_code == 200, r.text

    async def accese() -> int:
        async with test_session_factory() as s:
            return len((await s.execute(select(ConditionEffect.id).where(ConditionEffect.combatant_id == mostro))).all())
    as_user(PLAYER_ID)
    assert (await client.post(f"/characters/{cid}/spells/{luce}/use", json={"slot_level": 0})).status_code == 200
    assert await accese() == 1  # un altro lancio non tocca la concentrazione
    await client.patch(f"/characters/{cid}/concentration", json={"spell_id": None})
    assert await accese() == 0


@pytest.mark.caccia(id="CB-1545", fonte="invariante (come CB-451): l'annullo del danno rimette ciò che la concentrazione teneva", zona="flusso:concentrazione", voce="annullamento",
                    copre=["POST /characters/{char_id}/hp/undo"])
@pytest.mark.parametrize("op,valore,tolto", [("set_current", 0, False), ("damage", 200, False), ("damage", 1, False), ("damage", 200, True)])
async def test_annullo_pf_ridà_la_condizione_legata_alla_concentrazione(client, test_session_factory, dadi, op, valore, tolto):
    from sqlalchemy import select
    from core.db.models import Character, ConditionEffect
    sid, enc = await setup_full_encounter(client, test_session_factory)
    async with test_session_factory() as s:
        cid = (await s.execute(select(Character.id).where(Character.user_id == PLAYER_ID))).scalar_one()
        (await s.get(Character, cid)).hit_points = (await s.get(Character, cid)).current_hit_points = 30
        await s.commit()
    as_user(GM_ID)
    await client.post(f"/sessions/{sid}/encounter/start", json={})
    pc = next(c["id"] for c in enc["combatants"] if c["kind"] == "pc")
    mostro = next(c["id"] for c in enc["combatants"] if c["kind"] == "monster")
    as_user(PLAYER_ID)
    bene = await _incantesimo(client, cid)
    await client.patch(f"/characters/{cid}/concentration", json={"spell_id": bene})
    as_user(GM_ID)
    assert (await client.post(f"/sessions/{sid}/encounter/combatants/{mostro}/conditions",
                              json={"slug": "charmed", "source_combatant_id": pc, "ends_with_concentration": True})).status_code == 200

    async def accese() -> int:
        async with test_session_factory() as s:
            return len((await s.execute(select(ConditionEffect.id).where(ConditionEffect.combatant_id == mostro))).all())
    as_user(PLAYER_ID)
    dadi(1)  # il TS di concentrazione fallisce
    r = (await client.patch(f"/characters/{cid}/hp", json={"op": op, "value": valore})).json()
    assert await accese() == 0
    if tolto:  # la fonte non è più nell'incontro: l'effetto torna senza di lei
        as_user(GM_ID)
        assert (await client.delete(f"/sessions/{sid}/encounter/combatants/{pc}")).status_code in (200, 204)
        as_user(PLAYER_ID)
    assert (await client.post(f"/characters/{cid}/hp/undo", json={"op_id": r["hp_undo_id"]})).status_code == 200
    assert await accese() == 1


@pytest.mark.caccia(id="CB-1547", fonte="invariante (come CB-1538): un valore nullo dove non può esserlo si rifiuta, non rompe il server", zona="flusso:concentrazione", voce="contratto",
                    copre=["PATCH /characters/{char_id}", "PATCH /characters/{char_id}/classes/{class_id}", "PATCH /characters/{char_id}/items/{item_id}",
                           "PATCH /characters/{char_id}/currency", "PATCH /characters/{char_id}/abilities/{ability_id}"])
async def test_campi_obbligatori_nulli_rifiutati_ovunque(client):
    cid = await _pg(client)
    base = f"/characters/{cid}"
    classe = (await _stato(client, cid))["classes"][0]["id"]
    oggetto = (await client.post(f"{base}/items", json={"name": "Corda", "item_type": "gear"})).json()["id"]
    await client.post(f"{base}/abilities", json={"name": "Dono"})
    dono = next(a["id"] for a in (await _stato(client, cid))["abilities"] if a["name"] == "Dono")
    casi = [(base, ("name", "speed", "spell_slots_mode", "rules_edition")), (f"{base}/classes/{classe}", ("level", "hit_dice_used")),
            (f"{base}/items/{oggetto}", ("name", "weight", "quantity", "item_type", "is_equipped")),
            (f"{base}/currency", ("copper", "silver", "electrum", "gold", "platinum")),
            (f"{base}/abilities/{dono}", ("name", "is_passive", "is_active", "restoration_type"))]
    for url, campi in casi:
        for campo in campi:
            r = await client.patch(url, json={campo: None})
            assert r.status_code == 422, (url, campo, r.status_code)


@pytest.mark.caccia(id="CB-1549", fonte="invariante: una scheda senza PF massimi non è a 0 PF, la concentrazione resta", zona="flusso:concentrazione", voce="limiti",
                    copre=["PATCH /characters/{char_id}/hp"])
async def test_set_current_zero_senza_pf_massimi_non_chiude_la_concentrazione(client):
    cid = (await client.post("/characters", json={"name": "Vuoto"})).json()["id"]
    sid = await _incantesimo(client, cid)
    await client.patch(f"/characters/{cid}/concentration", json={"spell_id": sid})
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 0})
    assert r.status_code == 200 and r.json()["concentrating_spell_id"] == sid
