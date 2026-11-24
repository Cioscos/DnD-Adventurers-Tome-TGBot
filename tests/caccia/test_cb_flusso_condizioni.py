"""Controlli della zona flusso:condizioni (pagina /char/:id/conditions)."""
import pytest

from api.services.condition_effects import SaveSpec, upsert_effect
from core.db.models import PendingSave

_ED = ["2014", "2024"]


async def _pg(client, edizione="2014", classe="fighter") -> int:
    cid = (await client.post("/characters", json={"name": "P"})).json()["id"]
    await client.post(f"/characters/{cid}/classes", json={"class_name": classe, "level": 5, "hit_die": 10})
    await client.patch(f"/characters/{cid}", json={"rules_edition": edizione})
    return cid


async def _cond(client, cid, conditions, **extra):
    return await client.patch(f"/characters/{cid}/conditions", json={"conditions": conditions, **extra})


async def _scheda(client, cid) -> dict:
    return (await client.get(f"/characters/{cid}")).json()


async def _effetto(factory, cid, slug, dc, ability="strength", pending_save=False) -> int:
    """Una condizione con CD scritta come la scrive il GM: effetto sulla scheda e, se serve, il TS ripetuto aperto."""
    async with factory() as s:
        eff = await upsert_effect(s, ("character", cid), slug, save=SaveSpec(ability, dc, "end"))
        ps = None
        if pending_save:
            ps = PendingSave(effect_id=eff.id, character_id=cid, ability=ability, dc=dc, status="pending",
                             created_at="2026-11-24T10:00:00")
            s.add(ps)
        await s.commit()
        return ps.id if ps else eff.id


@pytest.mark.caccia(id="CB-537", fonte="invariante: la scheda risponde con i campi che la pagina legge", zona="flusso:condizioni",
                    voce="contratto", copre=["PATCH /characters/{char_id}/conditions", "POST /characters/{char_id}/rounds/tick",
                                            "route:/char/:id/conditions"])
async def test_contratto_condizioni_e_durate(client):
    cid = await _pg(client)
    vuota = (await _cond(client, cid, {"blinded": True})).json()
    assert vuota["condition_effects"] == [] and vuota["pending_saves"] == [] and vuota["conditions"] == {"blinded": True}
    j = (await _cond(client, cid, {"blinded": True, "poisoned": True}, durations={"poisoned": 3})).json()
    [eff] = j["condition_effects"]
    for campo in ("slug", "expiry_anchor", "expiry_edge", "expiry_count", "save_ability", "save_dc", "save_edge",
                  "source_name", "ends_with_concentration", "applied_by_gm", "source_note"):
        assert campo in eff, campo
    assert (eff["slug"], eff["expiry_count"]) == ("poisoned", 3)
    t = (await client.post(f"/characters/{cid}/rounds/tick")).json()
    assert t["expired_effects"] == [] and t["condition_effects"][0]["expiry_count"] == 2


@pytest.mark.caccia(id="CB-538", fonte="2014 · Indebolimento · pag. 291 (sei livelli); 2024 · Esaurimento · pag. 366", zona="flusso:condizioni",
                    voce="limiti", copre=["PATCH /characters/{char_id}/conditions", "carta:2014/general.md#Indebolimento / Exhaustion (riquadro, pag. 291)", "carta:2024/general.md#Exhaustion [Condition] (Esaurimento) (pag. 366)"])
@pytest.mark.parametrize("livello", [7, -1, 2.5, "3", 99])
async def test_indebolimento_fuori_da_zero_sei_rifiutato(client, livello):
    cid = await _pg(client)
    await _cond(client, cid, {"exhaustion": 2})
    r = await _cond(client, cid, {"exhaustion": livello})
    assert r.status_code in (400, 422), (livello, r.status_code, r.text)
    assert (await _scheda(client, cid))["conditions"] == {"exhaustion": 2}


@pytest.mark.caccia(id="CB-539", fonte="invariante: una condizione è accesa o spenta, non vale 5 o una stringa", zona="flusso:condizioni",
                    voce="limiti", copre=["PATCH /characters/{char_id}/conditions"])
@pytest.mark.parametrize("valore", [5, "x"])
async def test_condizione_con_valore_non_booleano_rifiutata(client, valore):
    cid = await _pg(client)
    r = await _cond(client, cid, {"blinded": valore})
    assert r.status_code in (400, 422), (valore, r.status_code, r.text)
    assert (await _scheda(client, cid))["conditions"] == {}


async def _calmare(client, ed):
    cid = await _pg(client, ed, "cleric")
    classe = (await _scheda(client, cid))["classes"][0]["id"]
    sid = (await client.post(f"/characters/{cid}/spells", json={
        "name": "calm-emotions", "level": 2, "srd_index": "calm-emotions", "is_prepared": True, "is_concentration": True,
        "class_id": classe})).json()["id"]
    await _cond(client, cid, {"charmed": True, "blinded": True})
    r = await client.post(f"/characters/{cid}/spells/{sid}/use", json={"slot_level": 2, "removal": {"targets": ["self"]}})
    assert r.status_code == 200, r.text
    assert (await _scheda(client, cid))["conditions"] == {"charmed": False, "blinded": True}
    return cid


@pytest.mark.caccia(id="CB-540", fonte="2014 · Calmare Emozioni · pag. 218; 2024 · pag. 249", zona="flusso:condizioni", voce="interazione",
                    copre=["PATCH /characters/{char_id}/conditions", "PATCH /characters/{char_id}/concentration",
                           "carta:2014/spells.md#Calmare Emozioni"])
@pytest.mark.parametrize("ed", _ED)
async def test_calmare_emozioni_sopravvive_a_un_tocco_su_altra_condizione(client, ed):
    cid = await _calmare(client, ed)
    mappa = (await _scheda(client, cid))["conditions"]  # la pagina rimanda tutta la mappa a ogni tocco
    await _cond(client, cid, {**mappa, "prone": True})
    await client.patch(f"/characters/{cid}/concentration", json={"spell_id": None})
    assert (await _scheda(client, cid))["conditions"].get("charmed") is True


@pytest.mark.caccia(id="CB-541", fonte="2014 · Calmare Emozioni · pag. 218; 2024 · pag. 249", zona="flusso:condizioni", voce="annullamento",
                    copre=["PATCH /characters/{char_id}/concentration", "carta:2024/spells.md#Calmare Emozioni"])
@pytest.mark.parametrize("ed", _ED)
async def test_calmare_emozioni_finita_la_concentrazione_la_condizione_torna(client, ed):
    cid = await _calmare(client, ed)
    await client.patch(f"/characters/{cid}/concentration", json={"spell_id": None})
    assert (await _scheda(client, cid))["conditions"] == {"charmed": True, "blinded": True}


@pytest.mark.caccia(id="CB-542", fonte="invariante: dopo export e import lo stato della scheda è lo stesso, durate comprese", zona="flusso:condizioni",
                    voce="persistenza", copre=["GET /characters/{char_id}/export", "POST /characters/import", "POST /characters/{char_id}/duplicate"])
async def test_durata_della_condizione_resta_con_importazione_e_copia(client):
    cid = await _pg(client)
    await _cond(client, cid, {"blinded": True}, durations={"blinded": 2})
    prima = [(e["slug"], e["expiry_count"]) for e in (await _scheda(client, cid))["condition_effects"]]
    assert prima == [("blinded", 2)]
    importata = (await client.post("/characters/import", json=(await client.get(f"/characters/{cid}/export")).json())).json()
    copia = (await client.post(f"/characters/{cid}/duplicate")).json()
    for j in (importata, copia):
        assert j["conditions"] == {"blinded": True}
        assert [(e["slug"], e["expiry_count"]) for e in (await _scheda(client, j["id"]))["condition_effects"]] == prima


@pytest.mark.caccia(id="CB-543", fonte="2014 · Indebolimento · pag. 291", zona="flusso:condizioni", voce="regola",
                    copre=["PATCH /characters/{char_id}/conditions", "carta:2014/general.md#Indebolimento / Exhaustion (riquadro, pag. 291)"])
@pytest.mark.parametrize("livello", [1, 2, 3, 4, 5, 6])
async def test_indebolimento_2014_tabella_dei_livelli(client, livello):
    cid = await _pg(client, "2014")
    base = (await _scheda(client, cid))
    j = (await _cond(client, cid, {"exhaustion": livello})).json()
    prova = (await client.post(f"/characters/{cid}/ability_checks/strength/roll", json={"die": 10})).json()
    ts = (await client.post(f"/characters/{cid}/saving_throws/wisdom/roll", json={"die": 10})).json()
    assert (prova["mode_applied"] == "disadvantage") is True  # livello 1: prove di caratteristica
    assert (ts["mode_applied"] == "disadvantage") is (livello >= 3)  # livello 3: tiri salvezza
    assert j["computed"]["speed"] == (0 if livello >= 5 else base["speed"] // 2 if livello >= 2 else base["speed"])
    assert j["computed"]["hp_max_effective"] == (base["hit_points"] // 2 if livello >= 4 else base["hit_points"])
    assert j["is_dead"] is (livello == 6)


@pytest.mark.caccia(id="CB-544", fonte="2024 · Esaurimento · pag. 366", zona="flusso:condizioni", voce="regola",
                    copre=["PATCH /characters/{char_id}/conditions", "carta:2024/general.md#Exhaustion [Condition] (Esaurimento) (pag. 366)"])
@pytest.mark.parametrize("livello", [1, 2, 3, 4, 5, 6])
async def test_esaurimento_2024_meno_due_e_meno_cinque_piedi_per_livello(client, livello):
    cid = await _pg(client, "2024")
    base = await _scheda(client, cid)
    j = (await _cond(client, cid, {"exhaustion": livello})).json()
    prova = (await client.post(f"/characters/{cid}/ability_checks/strength/roll", json={"die": 10})).json()
    ts = (await client.post(f"/characters/{cid}/saving_throws/strength/roll", json={"die": 10})).json()
    assert prova["total"] == 10 - 2 * livello and prova["mode_applied"] == "normal"
    assert ts["total"] == 10 + 3 - 2 * livello  # competenza +3 nel TS di Forza del guerriero
    assert j["computed"]["speed"] == max(0, base["speed"] - 5 * livello)
    assert j["computed"]["hp_max_effective"] == base["hit_points"]  # i PF massimi non cambiano
    assert j["is_dead"] is (livello == 6)


@pytest.mark.caccia(id="CB-545", fonte="2014 · Indebolimento · pag. 291; 2024 · Esaurimento · pag. 366", zona="flusso:condizioni", voce="edizioni",
                    copre=["POST /characters/{char_id}/rest", "carta:2014/general.md#Indebolimento / Exhaustion (riquadro, pag. 291)", "carta:2024/general.md#Exhaustion [Condition] (Esaurimento) (pag. 366)"])
@pytest.mark.parametrize("ed,mangiato,atteso", [("2014", True, 2), ("2014", False, 3), ("2024", True, 2), ("2024", False, 2)])
async def test_riposo_lungo_toglie_un_livello(client, ed, mangiato, atteso):
    cid = await _pg(client, ed)
    await _cond(client, cid, {"exhaustion": 3})
    r = await client.post(f"/characters/{cid}/rest", json={"rest_type": "long", "ate_and_drank": mangiato, "confirm_early": True})
    assert r.status_code == 200, r.text
    assert (await _scheda(client, cid))["conditions"]["exhaustion"] == atteso


@pytest.mark.caccia(id="CB-546", fonte="2014 · Paralizzato, Pietrificato, Privo di Sensi, Stordito · pag. 291-292; 2024 · pag. 363-371", zona="flusso:condizioni",
                    voce="regola", copre=["POST /characters/{char_id}/saving_throws/{ability}/roll", "carta:2014/general.md#Paralizzato / Paralyzed (pag. 291)"])
@pytest.mark.parametrize("ed", _ED)
@pytest.mark.parametrize("cond", ["paralyzed", "petrified", "stunned", "unconscious"])
async def test_forza_e_destrezza_falliscono_da_sole_le_altre_no(client, ed, cond):
    cid = await _pg(client, ed)
    await _cond(client, cid, {cond: True})
    for abilita, auto in (("strength", True), ("dexterity", True), ("constitution", False), ("wisdom", False)):
        r = (await client.post(f"/characters/{cid}/saving_throws/{abilita}/roll", json={"die": 20})).json()
        assert r["auto_fail"] is auto, (cond, abilita)


@pytest.mark.caccia(id="CB-547", fonte="2014 · Trattenuto · pag. 292; 2024 · Restrained · pag. 371", zona="flusso:condizioni", voce="regola",
                    copre=["POST /characters/{char_id}/saving_throws/{ability}/roll"])
@pytest.mark.parametrize("ed", _ED)
async def test_trattenuto_svantaggio_solo_ai_ts_di_destrezza(client, ed):
    cid = await _pg(client, ed)
    await _cond(client, cid, {"restrained": True})
    dex = (await client.post(f"/characters/{cid}/saving_throws/dexterity/roll", json={"die": 10})).json()
    forza = (await client.post(f"/characters/{cid}/saving_throws/strength/roll", json={"die": 10})).json()
    assert dex["mode_applied"] == "disadvantage" and forza["mode_applied"] == "normal"


@pytest.mark.caccia(id="CB-548", fonte="2014 · Concentrazione · pag. 203; 2024 · Concentration · pag. 363", zona="flusso:condizioni", voce="interazione",
                    copre=["PATCH /characters/{char_id}/conditions", "PATCH /characters/{char_id}/concentration"])
@pytest.mark.parametrize("ed", _ED)
@pytest.mark.parametrize("cond", ["incapacitated", "paralyzed", "stunned", "petrified", "unconscious"])
async def test_condizione_che_incapacita_rompe_la_concentrazione(client, ed, cond):
    cid = await _pg(client, ed)
    classe = (await _scheda(client, cid))["classes"][0]["id"]
    sid = (await client.post(f"/characters/{cid}/spells", json={"name": "Benedizione", "level": 1, "is_prepared": True,
                                                                "is_concentration": True, "class_id": classe})).json()["id"]
    await client.patch(f"/characters/{cid}/concentration", json={"spell_id": sid})
    assert (await _scheda(client, cid))["concentrating_spell_id"] == sid
    await _cond(client, cid, {cond: True})
    assert (await _scheda(client, cid))["concentrating_spell_id"] is None


@pytest.mark.caccia(id="CB-549", fonte="invariante: una richiesta ripetuta non scrive due volte", zona="flusso:condizioni", voce="ripetizione",
                    copre=["PATCH /characters/{char_id}/conditions"])
async def test_stessa_richiesta_due_volte_una_sola_riga_di_storico_e_un_effetto(client):
    cid = await _pg(client)
    for _ in range(2):
        await _cond(client, cid, {"blinded": True, "exhaustion": 2}, durations={"blinded": 3})
    j = await _scheda(client, cid)
    assert [(e["slug"], e["expiry_count"]) for e in j["condition_effects"]] == [("blinded", 3)]
    storico = [h["description"] for h in (await client.get(f"/characters/{cid}/history")).json() if "ondizione" in h["description"]]
    assert len(storico) == 1, storico


@pytest.mark.caccia(id="CB-550", fonte="invariante: spenta la condizione, la sua durata non resta orfana", zona="flusso:condizioni", voce="annullamento",
                    copre=["PATCH /characters/{char_id}/conditions"])
async def test_spenta_e_riaccesa_non_riprende_la_vecchia_durata(client):
    cid = await _pg(client)
    await _cond(client, cid, {"blinded": True}, durations={"blinded": 3})
    await _cond(client, cid, {"blinded": False})
    assert (await _scheda(client, cid))["condition_effects"] == []
    await _cond(client, cid, {"blinded": True})
    assert (await _scheda(client, cid))["condition_effects"] == []


@pytest.mark.caccia(id="CB-551", fonte="CLAUDE.md · Durations: le condizioni scadono dopo un numero di round", zona="flusso:condizioni", voce="normale",
                    copre=["POST /characters/{char_id}/rounds/tick"])
async def test_durata_di_due_round_scade_al_secondo_passaggio(client):
    cid = await _pg(client)
    await _cond(client, cid, {"blinded": True, "poisoned": True}, durations={"blinded": 2})
    primo = (await client.post(f"/characters/{cid}/rounds/tick")).json()
    assert primo["conditions"]["blinded"] is True and primo["expired_effects"] == []
    secondo = (await client.post(f"/characters/{cid}/rounds/tick")).json()
    assert secondo["conditions"] == {"blinded": False, "poisoned": True} and secondo["condition_effects"] == []
    assert len(secondo["expired_effects"]) == 1


@pytest.mark.caccia(id="CB-552", fonte="invariante: una durata zero o negativa non crea un effetto che scade subito o mai", zona="flusso:condizioni",
                    voce="limiti", copre=["PATCH /characters/{char_id}/conditions"])
@pytest.mark.parametrize("durata", [0, -3])
async def test_durata_zero_o_negativa_non_crea_effetti(client, durata):
    cid = await _pg(client)
    j = (await _cond(client, cid, {"blinded": True}, durations={"blinded": durata})).json()
    assert j["conditions"] == {"blinded": True} and j["condition_effects"] == []


@pytest.mark.caccia(id="CB-553", fonte="invariante: la scheda di un altro utente non si tocca", zona="flusso:condizioni", voce="permessi",
                    copre=["PATCH /characters/{char_id}/conditions", "POST /characters/{char_id}/rounds/tick",
                           "POST /characters/{char_id}/conditions/{slug}/escape"])
async def test_un_altro_utente_non_cambia_le_condizioni(client, come_utente):
    cid = await _pg(client)
    await _cond(client, cid, {"blinded": True}, durations={"blinded": 3})
    come_utente(9002)
    assert (await _cond(client, cid, {"blinded": False})).status_code in (403, 404)
    assert (await client.post(f"/characters/{cid}/rounds/tick")).status_code in (403, 404)
    assert (await client.post(f"/characters/{cid}/conditions/restrained/escape")).status_code in (403, 404)
    come_utente(1234)
    j = await _scheda(client, cid)
    assert j["conditions"] == {"blinded": True} and j["condition_effects"][0]["expiry_count"] == 3


@pytest.mark.caccia(id="CB-554", fonte="2024 · Grappling · pag. 367; invariante: la prova riesce se il totale raggiunge la CD", zona="flusso:condizioni",
                    voce="limiti", copre=["POST /characters/{char_id}/conditions/{slug}/escape"])
@pytest.mark.parametrize("ed", _ED)
async def test_liberarsi_riesce_con_totale_uguale_alla_cd(client, test_session_factory, ed):
    cid = await _pg(client, ed)
    await _cond(client, cid, {"restrained": True})
    await _effetto(test_session_factory, cid, "restrained", 14)
    manca = (await client.post(f"/characters/{cid}/conditions/restrained/escape", json={"die": 13})).json()
    assert manca["escaped"] is False and manca["roll"]["total"] == 13
    assert (await _scheda(client, cid))["conditions"]["restrained"] is True
    ok = (await client.post(f"/characters/{cid}/conditions/restrained/escape", json={"die": 14})).json()
    assert ok["escaped"] is True and ok["dc"] == 14
    j = await _scheda(client, cid)
    assert not j["conditions"].get("restrained") and j["condition_effects"] == []


@pytest.mark.caccia(id="CB-555", fonte="2014 · Incapacitato · pag. 291; 2024 · Grappling · pag. 367 (serve un'azione)", zona="flusso:condizioni",
                    voce="regola", copre=["POST /characters/{char_id}/conditions/{slug}/escape"])
async def test_incapacitato_non_puo_tentare_di_liberarsi(client, test_session_factory):
    cid = await _pg(client)
    await _cond(client, cid, {"grappled": True, "stunned": True})
    await _effetto(test_session_factory, cid, "grappled", 5)
    r = await client.post(f"/characters/{cid}/conditions/grappled/escape", json={"die": 20})
    assert r.status_code in (409, 422), r.text
    assert (await _scheda(client, cid))["conditions"]["grappled"] is True


@pytest.mark.caccia(id="CB-556", fonte="2014 · Paralizzato · pag. 291; invariante: il TS ripetuto riesce se il totale raggiunge la CD", zona="flusso:condizioni",
                    voce="limiti", copre=["POST /characters/{char_id}/pending-saves/{psid}/roll"])
async def test_ts_ripetuto_al_limite_della_cd(client, test_session_factory):
    cid = await _pg(client)
    await _cond(client, cid, {"frightened": True})
    ps = await _effetto(test_session_factory, cid, "frightened", 14, "strength", pending_save=True)
    r = (await client.post(f"/characters/{cid}/pending-saves/{ps}/roll", json={"die": 11})).json()  # 11 + 3 di competenza = 14
    assert r["roll"]["total"] == 14 and r["passed"] is True and r["condition_removed"] is True
    j = await _scheda(client, cid)
    assert not j["conditions"].get("frightened") and j["condition_effects"] == [] and j["pending_saves"] == []


@pytest.mark.caccia(id="CB-557", fonte="2014 · Paralizzato · pag. 291 (fallimento automatico)", zona="flusso:condizioni", voce="regola",
                    copre=["POST /characters/{char_id}/pending-saves/{psid}/roll"])
async def test_ts_ripetuto_di_forza_da_paralizzato_non_riesce_con_20(client, test_session_factory):
    cid = await _pg(client)
    await _cond(client, cid, {"paralyzed": True})
    ps = await _effetto(test_session_factory, cid, "paralyzed", 10, "strength", pending_save=True)
    r = (await client.post(f"/characters/{cid}/pending-saves/{ps}/roll", json={"die": 20})).json()
    assert r["passed"] is False
    assert (await _scheda(client, cid))["conditions"]["paralyzed"] is True


@pytest.mark.caccia(id="CB-558", fonte="2014 · Stordito · pag. 292; 2024 · Stunned · pag. 371", zona="flusso:condizioni", voce="edizioni",
                    copre=["PATCH /characters/{char_id}/conditions"])
@pytest.mark.parametrize("ed,cond,velocita", [("2014", "stunned", 0), ("2024", "stunned", 30), ("2014", "grappled", 0),
                                              ("2024", "grappled", 0), ("2014", "incapacitated", 30), ("2024", "paralyzed", 0)])
async def test_velocita_delle_condizioni_per_edizione(client, ed, cond, velocita):
    cid = await _pg(client, ed)
    j = (await _cond(client, cid, {cond: True})).json()
    assert j["computed"]["speed"] == velocita


@pytest.mark.caccia(id="CB-559", fonte="2024 · Incapacitated · pag. 369; Invisible · pag. 369", zona="flusso:condizioni", voce="edizioni",
                    copre=["POST /characters/{char_id}/dice/initiative"])
@pytest.mark.parametrize("ed,cond,modo", [("2014", "incapacitated", "normal"), ("2024", "incapacitated", "disadvantage"),
                                          ("2014", "invisible", "normal"), ("2024", "invisible", "advantage")])
async def test_iniziativa_con_condizioni_per_edizione(client, ed, cond, modo):
    cid = await _pg(client, ed)
    await _cond(client, cid, {cond: True})
    r = (await client.post(f"/characters/{cid}/dice/initiative", json={"die": 10})).json()
    assert r["mode_applied"] == modo


@pytest.mark.caccia(id="CB-560", fonte="2014 · Indebolimento livello 4 · pag. 291", zona="flusso:condizioni", voce="interazione",
                    copre=["PATCH /characters/{char_id}/conditions", "PATCH /characters/{char_id}/hp", "carta:2014/general.md#Indebolimento / Exhaustion (riquadro, pag. 291)"])
async def test_indebolimento_4_dimezza_i_pf_e_la_cura_non_li_supera(client):
    cid = await _pg(client, "2014")
    j = (await _cond(client, cid, {"exhaustion": 4})).json()
    massimo = j["hit_points"] // 2
    assert (j["current_hit_points"], j["computed"]["hp_max_effective"]) == (massimo, massimo)
    await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 5})
    r = (await client.patch(f"/characters/{cid}/hp", json={"op": "heal", "value": 99})).json()
    assert r["current_hit_points"] == massimo
    r = (await _cond(client, cid, {"exhaustion": 3})).json()
    assert r["computed"]["hp_max_effective"] == j["hit_points"]


@pytest.mark.caccia(id="CB-565", fonte="2024 · Privo di sensi · general.md pag. 377", zona="flusso:condizioni", voce="edizioni",
                    copre=["PATCH /characters/{char_id}/conditions"])
async def test_2024_privo_di_sensi_accende_anche_prono(client):
    cid = await _pg(client, "2024")
    j = (await _cond(client, cid, {"unconscious": True})).json()
    assert j["conditions"].get("unconscious") is True and j["conditions"].get("prone") is True
    j = (await _cond(client, cid, {"unconscious": False})).json()
    assert j["conditions"].get("prone") is True  # resta Prono quando la condizione finisce


@pytest.mark.caccia(id="CB-566", fonte="2014 · Privo di Sensi · pag. 292 (cade prono una volta)", zona="flusso:condizioni", voce="edizioni",
                    copre=["PATCH /characters/{char_id}/conditions"])
async def test_2014_privo_di_sensi_e_prono_restano_interruttori_separati(client):
    cid = await _pg(client, "2014")
    j = (await _cond(client, cid, {"unconscious": True})).json()
    assert j["conditions"] == {"unconscious": True}
    j = (await _cond(client, cid, {"unconscious": False, "prone": True})).json()
    assert j["conditions"] == {"unconscious": False, "prone": True}


# ---------------------------------------------------------------------------
# Giro successivo: durate in scontro, liberarsi, spossatezza sui tiri, condizioni tolte da incantesimi
# ---------------------------------------------------------------------------

async def _chierico(client, ed, livello=17) -> int:
    cid = await _pg(client, ed, "cleric")
    classe = (await _scheda(client, cid))["classes"][0]["id"]
    await client.patch(f"/characters/{cid}/classes/{classe}", json={"level": livello})
    return cid


async def _incantesimo(client, cid, nome, indice, livello) -> int:
    classe = (await _scheda(client, cid))["classes"][0]["id"]
    r = await client.post(f"/characters/{cid}/spells", json={"name": nome, "level": livello, "srd_index": indice,
                                                             "is_prepared": True, "class_id": classe})
    return r.json()["id"]


async def _usa(client, cid, sid, livello, **removal):
    return await client.post(f"/characters/{cid}/spells/{sid}/use", json={"slot_level": livello, "removal": {"targets": ["self"], **removal}})


async def _attacco(client, ed, condizioni) -> dict:
    """Un attacco senz'armi di un PG nuovo (il limite di attacchi per turno non ostacola la prova)."""
    cid = await _pg(client, ed)
    await _cond(client, cid, condizioni)
    r = await client.post(f"/characters/{cid}/attack/unarmed", json={"die": 10})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.caccia(id="CB-1273", fonte="2014 · Indebolimento · pag. 291 (livello 1 prove di caratteristica, livello 3 attacchi e TS)", zona="flusso:condizioni",
                    voce="regola", copre=["POST /characters/{char_id}/dice/initiative", "POST /characters/{char_id}/attack/unarmed",
                                          "carta:2014/general.md#Indebolimento / Exhaustion (riquadro, pag. 291)"])
@pytest.mark.parametrize("livello", [0, 1, 2, 3, 5])
async def test_indebolimento_2014_iniziativa_e_attacchi(client, livello):
    cid = await _pg(client, "2014")
    await _cond(client, cid, {"exhaustion": livello})
    ini = (await client.post(f"/characters/{cid}/dice/initiative", json={"die": 10})).json()  # l'iniziativa è una prova di Destrezza
    assert ini["mode_applied"] == ("disadvantage" if livello >= 1 else "normal")
    assert (await _attacco(client, "2014", {"exhaustion": livello}))["mode_applied"] == ("disadvantage" if livello >= 3 else "normal")


@pytest.mark.caccia(id="CB-1274", fonte="2024 · Esaurimento · pag. 366: -2 per livello a ogni Prova di d20", zona="flusso:condizioni", voce="regola",
                    copre=["POST /characters/{char_id}/dice/initiative", "POST /characters/{char_id}/attack/unarmed",
                           "carta:2024/general.md#Exhaustion [Condition] (Esaurimento) (pag. 366)"])
@pytest.mark.parametrize("livello", [1, 3, 5])
async def test_esaurimento_2024_toglie_due_per_livello_a_iniziativa_e_attacchi(client, livello):
    cid = await _pg(client, "2024")
    base = (await client.post(f"/characters/{cid}/dice/initiative", json={"die": 10})).json()["total"]
    await _cond(client, cid, {"exhaustion": livello})
    ini = (await client.post(f"/characters/{cid}/dice/initiative", json={"die": 10})).json()
    assert ini["total"] == base - 2 * livello and ini["mode_applied"] == "normal"
    sano = (await _attacco(client, "2024", {}))["to_hit_total"]
    assert (await _attacco(client, "2024", {"exhaustion": livello}))["to_hit_total"] == sano - 2 * livello


@pytest.mark.caccia(id="CB-1275", fonte="2014 · Avvelenato, Prono, Trattenuto, Accecato, Invisibile · pag. 290-292; 2024 · pag. 363-371", zona="flusso:condizioni",
                    voce="edizioni", copre=["POST /characters/{char_id}/attack/unarmed", "POST /characters/{char_id}/ability_checks/{ability}/roll"])
@pytest.mark.parametrize("ed", _ED)
@pytest.mark.parametrize("cond,attacco,prova", [("poisoned", "disadvantage", "disadvantage"), ("blinded", "disadvantage", "normal"),
                                                ("prone", "disadvantage", "normal"), ("restrained", "disadvantage", "normal"),
                                                ("invisible", "advantage", "normal"), ("charmed", "normal", "normal")])
async def test_condizioni_e_modo_di_attacchi_e_prove(client, ed, cond, attacco, prova):
    assert (await _attacco(client, ed, {cond: True}))["mode_applied"] == attacco
    cid = await _pg(client, ed)
    await _cond(client, cid, {cond: True})
    assert (await client.post(f"/characters/{cid}/ability_checks/strength/roll", json={"die": 10})).json()["mode_applied"] == prova


@pytest.mark.caccia(id="CB-1276", fonte="2014 · Incapacitato, Paralizzato, Pietrificato, Privo di Sensi · pag. 291-292; 2024 · Grappling · pag. 367", zona="flusso:condizioni",
                    voce="interazione", copre=["POST /characters/{char_id}/conditions/{slug}/escape"])
@pytest.mark.parametrize("ed", _ED)
@pytest.mark.parametrize("cond", ["paralyzed", "petrified", "unconscious", "incapacitated"])
async def test_liberarsi_serve_un_azione_chi_non_agisce_non_puo(client, test_session_factory, ed, cond):
    cid = await _pg(client, ed)
    await _cond(client, cid, {"restrained": True, cond: True})
    await _effetto(test_session_factory, cid, "restrained", 5)
    r = await client.post(f"/characters/{cid}/conditions/restrained/escape", json={"die": 20})
    assert r.status_code == 409, r.text
    assert (await _scheda(client, cid))["conditions"]["restrained"] is True


@pytest.mark.caccia(id="CB-1277", fonte="2024 · Grappling · pag. 367 (Atletica o Acrobazia); invariante: la prova scelta usa la sua caratteristica", zona="flusso:condizioni",
                    voce="normale", copre=["POST /characters/{char_id}/conditions/{slug}/escape", "PATCH /characters/{char_id}/ability_scores/{ability_name}"])
async def test_liberarsi_atletica_usa_forza_e_acrobazia_destrezza(client, test_session_factory):
    cid = await _pg(client, "2024")
    await client.patch(f"/characters/{cid}/ability_scores/strength", json={"value": 8})
    await client.patch(f"/characters/{cid}/ability_scores/dexterity", json={"value": 18})
    await _cond(client, cid, {"grappled": True})
    await _effetto(test_session_factory, cid, "grappled", 30)
    atl = (await client.post(f"/characters/{cid}/conditions/grappled/escape?skill=athletics", json={"die": 10})).json()
    acr = (await client.post(f"/characters/{cid}/conditions/grappled/escape?skill=acrobatics", json={"die": 10})).json()
    assert (atl["roll"]["total"], acr["roll"]["total"]) == (9, 14)


@pytest.mark.caccia(id="CB-1278", fonte="invariante: senza CD non c'è prova da tentare; una condizione non liberabile è rifiutata senza toccare nulla", zona="flusso:condizioni",
                    voce="contratto", copre=["POST /characters/{char_id}/conditions/{slug}/escape"])
async def test_liberarsi_senza_cd_o_da_condizione_non_liberabile(client):
    cid = await _pg(client)
    await _cond(client, cid, {"grappled": True, "blinded": True})
    senza = await client.post(f"/characters/{cid}/conditions/grappled/escape", json={"die": 20})
    assert senza.status_code == 409 and senza.json()["detail"] == {"code": "no_escape_dc"}
    altra = await client.post(f"/characters/{cid}/conditions/blinded/escape", json={"die": 20})
    assert altra.status_code == 422 and altra.json()["detail"] == {"code": "not_escapable"}
    assert (await _scheda(client, cid))["conditions"] == {"grappled": True, "blinded": True}


@pytest.mark.caccia(id="CB-1279", fonte="invariante: una richiesta ripetuta non scrive due volte", zona="flusso:condizioni", voce="ripetizione",
                    copre=["POST /characters/{char_id}/conditions/{slug}/escape"])
async def test_liberarsi_due_volte_dopo_il_successo_la_seconda_e_rifiutata(client, test_session_factory):
    cid = await _pg(client)
    await _cond(client, cid, {"restrained": True})
    await _effetto(test_session_factory, cid, "restrained", 5)
    assert (await client.post(f"/characters/{cid}/conditions/restrained/escape", json={"die": 20})).json()["escaped"] is True
    assert (await client.post(f"/characters/{cid}/conditions/restrained/escape", json={"die": 20})).status_code == 409
    righe = [h for h in (await client.get(f"/characters/{cid}/history")).json() if "Liberarsi" in h["description"]]
    assert len(righe) == 1, righe


async def _in_scontro(client, fabbrica):
    """Il PG di PLAYER_ID al suo turno, nel round 1, e il suo id scheda."""
    from sqlalchemy import select
    from core.db.models import Character
    from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, setup_full_encounter
    sid, _ = await setup_full_encounter(client, fabbrica)
    async with fabbrica() as s:
        cid = (await s.execute(select(Character.id).where(Character.user_id == PLAYER_ID))).scalar_one()
    as_user(GM_ID)
    await client.post(f"/sessions/{sid}/encounter/start", json={})
    as_user(PLAYER_ID)
    return sid, cid


@pytest.mark.caccia(id="CB-1280", fonte="2024 · Grappling · pag. 367 (serve un'azione); CLAUDE.md · in combattimento l'azione si spende prima del tiro", zona="flusso:condizioni",
                    voce="limiti", copre=["POST /characters/{char_id}/conditions/{slug}/escape"])
async def test_liberarsi_in_scontro_il_tentativo_fallito_costa_l_azione(client, test_session_factory):
    sid, cid = await _in_scontro(client, test_session_factory)
    await _cond(client, cid, {"restrained": True})
    await _effetto(test_session_factory, cid, "restrained", 30)
    prima = await client.post(f"/characters/{cid}/conditions/restrained/escape", json={"die": 2})
    assert prima.status_code == 200 and prima.json()["escaped"] is False
    seconda = await client.post(f"/characters/{cid}/conditions/restrained/escape", json={"die": 20})
    assert seconda.status_code == 409 and seconda.json()["detail"] == {"code": "turn_slot_used"}
    assert (await _scheda(client, cid))["conditions"]["restrained"] is True


@pytest.mark.caccia(id="CB-1281", fonte="invariante: in scontro i turni guidano le durate, un tick manuale le conterebbe due volte", zona="flusso:condizioni",
                    voce="interazione", copre=["POST /characters/{char_id}/rounds/tick"])
async def test_tick_manuale_in_scontro_rifiutato_e_non_tocca_le_durate(client, test_session_factory):
    sid, cid = await _in_scontro(client, test_session_factory)
    await _cond(client, cid, {"blinded": True}, durations={"blinded": 2})
    r = await client.post(f"/characters/{cid}/rounds/tick")
    assert r.status_code == 409 and r.json()["detail"] == {"code": "in_encounter"}
    assert [e["expiry_count"] for e in (await _scheda(client, cid))["condition_effects"]] == [2]


@pytest.mark.caccia(id="CB-1282", fonte="CLAUDE.md · Durations: scadono dopo un numero di round, in scontro scalati ai turni", zona="flusso:condizioni",
                    voce="normale", copre=["PATCH /characters/{char_id}/conditions", "POST /sessions/{session_id}/encounter/next-turn"])
async def test_durata_di_due_round_in_scontro_dura_due_giri_di_turni(client, test_session_factory):
    from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user
    sid, cid = await _in_scontro(client, test_session_factory)
    await _cond(client, cid, {"blinded": True}, durations={"blinded": 2})
    visti = []
    for _ in range(6):  # un PG e due mostri: 3 turni per round
        as_user(GM_ID)
        n = (await client.post(f"/sessions/{sid}/encounter/next-turn")).json()
        as_user(PLAYER_ID)
        visti.append((n["round"], (await _scheda(client, cid))["conditions"].get("blinded")))
    assert visti == [(1, True), (1, True), (2, True), (2, True), (2, True), (3, False)]


@pytest.mark.caccia(id="CB-1283", fonte="CLAUDE.md · Durations: le condizioni scadono dopo un numero di round", zona="flusso:condizioni", voce="limiti",
                    copre=["POST /characters/{char_id}/rounds/tick"])
async def test_tick_durata_di_un_round_scade_subito_le_altre_scalano(client):
    cid = await _pg(client)
    await _cond(client, cid, {"blinded": True, "poisoned": True, "deafened": True}, durations={"blinded": 1, "poisoned": 3})
    j = (await client.post(f"/characters/{cid}/rounds/tick")).json()
    assert j["conditions"] == {"blinded": False, "poisoned": True, "deafened": True}
    assert [(e["slug"], e["expiry_count"]) for e in j["condition_effects"]] == [("poisoned", 2)]
    assert j["expired_effects"] == ["Accecato"]
    assert any(h["description"] == "Durata scaduta: Accecato" for h in (await client.get(f"/characters/{cid}/history")).json())


@pytest.mark.caccia(id="CB-1284", fonte="2014 · Indebolimento · pag. 291: i livelli non hanno durata; invariante: nessun effetto orfano", zona="flusso:condizioni",
                    voce="limiti", copre=["PATCH /characters/{char_id}/conditions", "POST /characters/{char_id}/rounds/tick"])
async def test_durata_sull_indebolimento_non_crea_effetti_e_il_tick_non_lo_scala(client):
    cid = await _pg(client)
    j = (await _cond(client, cid, {"exhaustion": 2}, durations={"exhaustion": 1})).json()
    assert j["condition_effects"] == []
    t = (await client.post(f"/characters/{cid}/rounds/tick")).json()
    assert t["conditions"]["exhaustion"] == 2 and t["expired_effects"] == []


@pytest.mark.caccia(id="CB-1285", fonte="2014 · Ristorare Inferiore · pag. 271; 2024 · pag. 291", zona="flusso:condizioni", voce="annullamento",
                    copre=["POST /characters/{char_id}/spells/{spell_id}/use", "carta:2024/spells.md#Ristorare Inferiore"])
@pytest.mark.parametrize("ed", _ED)
async def test_ristorare_inferiore_scelta_non_ammessa_non_spende_lo_slot(client, ed):
    cid = await _chierico(client, ed, 5)
    sid = await _incantesimo(client, cid, "Ristorare Inferiore", "lesser-restoration", 2)
    await _cond(client, cid, {"charmed": True, "blinded": True})
    for scelta in (["charmed"], ["blinded", "charmed"], []):
        r = await _usa(client, cid, sid, 2, conditions=scelta)
        assert r.status_code == 422, (scelta, r.text)
    j = await _scheda(client, cid)
    assert j["conditions"] == {"charmed": True, "blinded": True} and all(s["used"] == 0 for s in j["spell_slots"])


@pytest.mark.caccia(id="CB-1286", fonte="2014 · Ristorare Superiore · pag. 271 (un livello di indebolimento); 2024 · Esaurimento · pag. 366", zona="flusso:condizioni",
                    voce="interazione", copre=["POST /characters/{char_id}/spells/{spell_id}/use", "carta:2014/spells.md#Ristorare Superiore"])
@pytest.mark.parametrize("ed,da,velocita", [("2014", 5, 15), ("2014", 2, 30), ("2024", 3, 15), ("2024", 1, 30)])
async def test_ristorare_superiore_toglie_un_livello_e_ricalcola_velocita_e_pf(client, ed, da, velocita):
    cid = await _chierico(client, ed)
    sid = await _incantesimo(client, cid, "Ristorare Superiore", "greater-restoration", 5)
    base = await _scheda(client, cid)
    await _cond(client, cid, {"exhaustion": da})
    r = await _usa(client, cid, sid, 5, conditions=["exhaustion"])
    assert r.status_code == 200, r.text
    j = await _scheda(client, cid)
    assert j["conditions"]["exhaustion"] == da - 1
    assert j["computed"]["speed"] == (base["speed"] if (ed, da - 1) in (("2014", 1), ("2024", 0)) else velocita if ed == "2014" else base["speed"] - 5 * (da - 1))
    assert j["computed"]["hp_max_effective"] == (base["hit_points"] // 2 if (ed, da - 1) == ("2014", 4) else base["hit_points"])


@pytest.mark.caccia(id="CB-1287", fonte="2014 · Guarigione · pag. 240 (cecità, sordità, malattie); 2024 · Guarigione · pag. 284 (Accecato, Assordato, Avvelenato)", zona="flusso:condizioni",
                    voce="edizioni", copre=["POST /characters/{char_id}/spells/{spell_id}/use", "carta:2024/spells.md#Guarigione"])
@pytest.mark.parametrize("ed,avvelenato", [("2014", True), ("2024", False)])
async def test_guarigione_toglie_avvelenato_solo_nel_2024(client, ed, avvelenato):
    cid = await _chierico(client, ed)
    sid = await _incantesimo(client, cid, "Guarigione", "heal", 6)
    await _cond(client, cid, {"blinded": True, "deafened": True, "poisoned": True, "charmed": True})
    r = await _usa(client, cid, sid, 6)
    assert r.status_code == 200, r.text
    assert (await _scheda(client, cid))["conditions"] == {"blinded": False, "deafened": False, "poisoned": avvelenato, "charmed": True}


@pytest.mark.caccia(id="CB-1288", fonte="2014 · Riposo lungo · pag. 186; Indebolimento livello 4 · pag. 291", zona="flusso:condizioni", voce="persistenza",
                    copre=["POST /characters/{char_id}/rest"])
async def test_riposo_lungo_con_indebolimento_5_i_pf_non_superano_il_massimo_dimezzato(client):
    cid = await _pg(client, "2014")
    await _cond(client, cid, {"exhaustion": 5})
    await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 3})
    r = await client.post(f"/characters/{cid}/rest", json={"rest_type": "long", "ate_and_drank": True, "confirm_early": True})
    assert r.status_code == 200, r.text
    j = await _scheda(client, cid)
    assert j["conditions"]["exhaustion"] == 4
    assert j["current_hit_points"] <= j["computed"]["hp_max_effective"] == j["hit_points"] // 2


@pytest.mark.caccia(id="CB-1289", fonte="2014 · Riposo breve · pag. 186; 2024 · pag. 376: solo il riposo lungo toglie un livello", zona="flusso:condizioni",
                    voce="persistenza", copre=["POST /characters/{char_id}/rest"])
@pytest.mark.parametrize("ed", _ED)
async def test_riposo_breve_non_tocca_indebolimento_condizioni_e_durate(client, ed):
    cid = await _pg(client, ed)
    await _cond(client, cid, {"exhaustion": 2, "blinded": True}, durations={"blinded": 4})
    r = await client.post(f"/characters/{cid}/rest", json={"rest_type": "short"})
    assert r.status_code == 200, r.text
    j = await _scheda(client, cid)
    assert j["conditions"]["exhaustion"] == 2 and j["conditions"]["blinded"] is True
    assert [e["expiry_count"] for e in j["condition_effects"]] == [4]


@pytest.mark.caccia(id="CB-1290", fonte="invariante: dopo export e import la CD per liberarsi resta quella dell'effetto", zona="flusso:condizioni",
                    voce="persistenza", copre=["GET /characters/{char_id}/export", "POST /characters/import", "POST /characters/{char_id}/conditions/{slug}/escape"])
async def test_cd_per_liberarsi_resta_dopo_importazione_e_copia(client, test_session_factory):
    cid = await _pg(client)
    await _cond(client, cid, {"restrained": True, "exhaustion": 3})
    await _effetto(test_session_factory, cid, "restrained", 17)
    importata = (await client.post("/characters/import", json=(await client.get(f"/characters/{cid}/export")).json())).json()
    copia = (await client.post(f"/characters/{cid}/duplicate")).json()
    for j in (importata, copia):
        assert j["conditions"].get("exhaustion") == 3
        r = await client.post(f"/characters/{j['id']}/conditions/restrained/escape", json={"die": 20})
        assert r.status_code == 200 and r.json()["dc"] == 17, r.text


@pytest.mark.caccia(id="CB-1291", fonte="invariante: il TS ripetuto di un altro utente non si tira né si chiude", zona="flusso:condizioni", voce="permessi",
                    copre=["POST /characters/{char_id}/pending-saves/{psid}/roll", "POST /characters/{char_id}/pending-saves/{psid}/dismiss"])
async def test_ts_ripetuto_altrui_non_si_tira_ne_si_chiude(client, test_session_factory, come_utente):
    altro = await _pg(client)
    await _cond(client, altro, {"frightened": True})
    ps = await _effetto(test_session_factory, altro, "frightened", 14, "strength", pending_save=True)
    come_utente(9002)
    mio = (await client.post("/characters", json={"name": "Mio"})).json()["id"]
    for cid in (altro, mio):  # la scheda altrui, e la propria con l'id del TS altrui
        assert (await client.post(f"/characters/{cid}/pending-saves/{ps}/roll", json={"die": 20})).status_code in (403, 404)
        assert (await client.post(f"/characters/{cid}/pending-saves/{ps}/dismiss")).status_code in (403, 404)
    come_utente(1234)
    j = await _scheda(client, altro)
    assert j["conditions"] == {"frightened": True} and [p["status"] for p in j["pending_saves"]] == ["pending"]


@pytest.mark.caccia(id="CB-1292", fonte="invariante: una richiesta ripetuta non scrive due volte", zona="flusso:condizioni", voce="ripetizione",
                    copre=["POST /characters/{char_id}/pending-saves/{psid}/roll"])
async def test_ts_ripetuto_riuscito_la_seconda_richiesta_e_rifiutata_con_una_riga_di_storico(client, test_session_factory):
    cid = await _pg(client)
    await _cond(client, cid, {"frightened": True})
    ps = await _effetto(test_session_factory, cid, "frightened", 5, "strength", pending_save=True)
    assert (await client.post(f"/characters/{cid}/pending-saves/{ps}/roll", json={"die": 20})).json()["passed"] is True
    assert (await client.post(f"/characters/{cid}/pending-saves/{ps}/roll", json={"die": 20})).status_code in (404, 409)
    righe = [h for h in (await client.get(f"/characters/{cid}/history")).json() if h["description"].startswith("TS ")]
    assert len(righe) == 1, righe


@pytest.mark.caccia(id="CB-1293", fonte="invariante: due richieste insieme non spendono due volte", zona="flusso:condizioni", voce="ripetizione",
                    copre=["POST /characters/{char_id}/pending-saves/{psid}/roll"])
async def test_ts_ripetuto_due_richieste_insieme_ne_riesce_una_sola(client, test_session_factory):
    import asyncio
    cid = await _pg(client)
    await _cond(client, cid, {"frightened": True})
    ps = await _effetto(test_session_factory, cid, "frightened", 5, "strength", pending_save=True)
    rs = await asyncio.gather(*[client.post(f"/characters/{cid}/pending-saves/{ps}/roll", json={"die": 20}) for _ in range(2)])
    assert sorted(r.status_code for r in rs)[0] == 200 and sorted(r.status_code for r in rs)[1] in (404, 409), [r.text for r in rs]
    righe = [h for h in (await client.get(f"/characters/{cid}/history")).json() if h["description"].startswith("TS ")]
    assert len(righe) == 1, righe


@pytest.mark.caccia(id="CB-1294", fonte="invariante: la pagina legge questi campi dalle risposte di liberarsi e del TS ripetuto", zona="flusso:condizioni",
                    voce="contratto", copre=["POST /characters/{char_id}/conditions/{slug}/escape", "POST /characters/{char_id}/pending-saves/{psid}/roll"])
async def test_contratto_risposte_di_liberarsi_e_del_ts_ripetuto(client, test_session_factory):
    cid = await _pg(client)
    await _cond(client, cid, {"restrained": True, "frightened": True})
    await _effetto(test_session_factory, cid, "restrained", 12)
    ps = await _effetto(test_session_factory, cid, "frightened", 12, "strength", pending_save=True)
    e = (await client.post(f"/characters/{cid}/conditions/restrained/escape", json={"die": 5})).json()
    assert {"roll", "dc", "escaped"} <= set(e)
    for campo in ("total", "die", "dice", "notes", "auto_fail"):
        assert campo in e["roll"], campo
    p = (await client.post(f"/characters/{cid}/pending-saves/{ps}/roll", json={"die": 5})).json()
    assert {"save", "passed", "condition_removed", "roll"} <= set(p)
    assert {"id", "ability", "dc", "status"} <= set(p["save"]) and p["passed"] is False and p["condition_removed"] is False
    j = await _scheda(client, cid)
    assert [(x["slug"], x["status"]) for x in j["pending_saves"]] == [("frightened", "failed")]


@pytest.mark.caccia(id="CB-1295", fonte="2014 · Punti ferita a 0 · pag. 197; 2024 · pag. 364", zona="flusso:condizioni", voce="interazione",
                    copre=["PATCH /characters/{char_id}/hp", "PATCH /characters/{char_id}/conditions"])
@pytest.mark.parametrize("ed", _ED)
async def test_a_zero_pf_privo_di_sensi_e_tornato_sopra_zero_si_sveglia(client, ed):
    cid = await _pg(client, ed)
    await _cond(client, cid, {"poisoned": True})
    pf = (await _scheda(client, cid))["current_hit_points"]
    j = (await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": pf})).json()
    assert j["current_hit_points"] == 0 and j["conditions"].get("unconscious") is True and j["conditions"].get("poisoned") is True
    j = (await client.patch(f"/characters/{cid}/hp", json={"op": "heal", "value": 1})).json()
    assert j["current_hit_points"] == 1 and not j["conditions"].get("unconscious") and j["conditions"].get("poisoned") is True


async def _gm_su_pg(client, fabbrica):
    """Sessione attiva con un incontro avviato: ritorna (session_id, id scheda del PG, id del combattente del PG, id di un mostro)."""
    from sqlalchemy import select
    from core.db.models import Character
    from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, setup_full_encounter
    sid, enc = await setup_full_encounter(client, fabbrica)
    async with fabbrica() as s:
        cid = (await s.execute(select(Character.id).where(Character.user_id == PLAYER_ID))).scalar_one()
    as_user(GM_ID)
    await client.post(f"/sessions/{sid}/encounter/start", json={})
    pc = next(c for c in enc["combatants"] if c["kind"] == "pc")
    mostro = next(c for c in enc["combatants"] if c["kind"] == "monster")
    return sid, cid, pc["id"], mostro["id"]


async def _come_giocatore(client, cid) -> dict:
    from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user
    as_user(PLAYER_ID)
    try:
        return await _scheda(client, cid)
    finally:
        as_user(GM_ID)


@pytest.mark.caccia(id="CB-1296", fonte="2014 · Indebolimento · pag. 291 (sei livelli); 2024 · Esaurimento · pag. 366", zona="flusso:condizioni", voce="limiti",
                    copre=["POST /sessions/{session_id}/encounter/combatants/{combatant_id}/conditions",
                           "carta:2014/general.md#Indebolimento / Exhaustion (riquadro, pag. 291)"])
@pytest.mark.parametrize("valore", [7,
                                    -1,
                                    True])
async def test_il_master_non_puo_dare_a_un_pg_un_livello_di_indebolimento_fuori_da_uno_sei(client, test_session_factory, valore):
    sid, cid, pc, _ = await _gm_su_pg(client, test_session_factory)
    r = await client.post(f"/sessions/{sid}/encounter/combatants/{pc}/conditions", json={"slug": "exhaustion", "value": valore})
    assert r.status_code in (400, 422), (valore, r.status_code, r.text)
    j = await _come_giocatore(client, cid)
    assert j["conditions"].get("exhaustion", 0) == 0 and j["is_dead"] is False


@pytest.mark.caccia(id="CB-1297", fonte="invariante: una condizione è accesa o spenta, non vale 5 (la stessa regola del giocatore)", zona="flusso:condizioni", voce="contratto",
                    copre=["POST /sessions/{session_id}/encounter/combatants/{combatant_id}/conditions"])
async def test_il_master_non_scrive_un_numero_come_valore_di_una_condizione(client, test_session_factory):
    sid, cid, pc, _ = await _gm_su_pg(client, test_session_factory)
    r = await client.post(f"/sessions/{sid}/encounter/combatants/{pc}/conditions", json={"slug": "blinded", "value": 5})
    assert r.status_code in (400, 422), r.text
    assert (await _come_giocatore(client, cid))["conditions"].get("blinded") in (None, False)


@pytest.mark.caccia(id="CB-1298", fonte="2014 · Calmare Emozioni · pag. 218; 2024 · pag. 249; invariante: dopo export, import e copia nulla va perso", zona="flusso:condizioni",
                    voce="persistenza", copre=["GET /characters/{char_id}/export", "POST /characters/import", "POST /characters/{char_id}/duplicate",
                                              "PATCH /characters/{char_id}/concentration", "carta:2014/spells.md#Calmare Emozioni"])
@pytest.mark.parametrize("ed", _ED)
@pytest.mark.parametrize("via", ["importa", "copia"])
async def test_calmare_emozioni_su_copia_o_importata_finita_la_concentrazione_la_condizione_torna(client, ed, via):
    cid = await _calmare(client, ed)
    if via == "importa":
        nuova = (await client.post("/characters/import", json=(await client.get(f"/characters/{cid}/export")).json())).json()
    else:
        nuova = (await client.post(f"/characters/{cid}/duplicate")).json()
    await client.patch(f"/characters/{nuova['id']}/concentration", json={"spell_id": None})
    assert (await _scheda(client, nuova["id"]))["conditions"].get("charmed") is True


@pytest.mark.caccia(id="CB-1305", fonte="decisione D-016 (tests/caccia/decisioni.md): durate dal giocatore al massimo 9999 round, oltre 422", zona="flusso:condizioni",
                    voce="limiti", copre=["PATCH /characters/{char_id}/conditions"])
async def test_durata_enorme_e_rifiutata_con_422_non_con_un_errore_del_server(client):
    cid = await _pg(client)
    try:
        r = await _cond(client, cid, {"blinded": True}, durations={"blinded": 10**30})
    except Exception as err:  # l'errore del server arriva come eccezione dal client di prova
        pytest.fail(f"errore del server invece di 422: {err!r}")
    assert r.status_code == 422, r.text


@pytest.mark.caccia(id="CB-1306", fonte="decisione D-016 (tests/caccia/decisioni.md): massimo 9999 round", zona="flusso:condizioni", voce="limiti",
                    copre=["PATCH /characters/{char_id}/conditions"])
async def test_durata_9999_ammessa_10000_rifiutata(client):
    cid = await _pg(client)
    ok = await _cond(client, cid, {"blinded": True}, durations={"blinded": 9999})
    assert ok.status_code == 200 and [e["expiry_count"] for e in ok.json()["condition_effects"]] == [9999]
    cid2 = await _pg(client)
    r = await _cond(client, cid2, {"blinded": True}, durations={"blinded": 10000})
    assert r.status_code == 422, r.text


@pytest.mark.caccia(id="CB-1307", fonte="decisione D-017 (tests/caccia/decisioni.md): una durata non cancella CD e fonte di un effetto non del master", zona="flusso:condizioni",
                    voce="interazione", copre=["PATCH /characters/{char_id}/conditions"])
async def test_durata_su_condizione_attiva_non_cancella_cd_e_fonte(client, test_session_factory):
    cid = await _pg(client)
    await _cond(client, cid, {"restrained": True})
    async with test_session_factory() as s:
        await upsert_effect(s, ("character", cid), "restrained", save=SaveSpec("strength", 15, "end"), source_note="Ragnatela")
        await s.commit()
    await _cond(client, cid, {"restrained": True}, durations={"restrained": 3})
    [e] = [x for x in (await _scheda(client, cid))["condition_effects"] if x["slug"] == "restrained"]
    assert (e["save_dc"], e["source_note"]) == (15, "Ragnatela")


@pytest.mark.caccia(id="CB-1500", fonte="decisione D-017 (tests/caccia/decisioni.md): protetta la condizione già attiva", zona="flusso:condizioni",
                    voce="interazione", copre=["PATCH /characters/{char_id}/conditions"])
async def test_una_condizione_riaccesa_prende_la_durata_nuova_e_non_la_cd_vecchia(client, test_session_factory):
    cid = await _pg(client)
    async with test_session_factory() as s:  # condizione spenta con l'effetto rimasto, come dopo Protezione dai Veleni
        await upsert_effect(s, ("character", cid), "poisoned", save=SaveSpec("constitution", 15, "end"), source_note="Ragno")
        await s.commit()
    await _cond(client, cid, {"poisoned": True}, durations={"poisoned": 4})
    [e] = [x for x in (await _scheda(client, cid))["condition_effects"] if x["slug"] == "poisoned"]
    assert (e["save_dc"], e["source_note"]) == (None, None)


@pytest.mark.caccia(id="CB-1501", fonte="2014 · Indebolimento · pag. 291 (livelli, non acceso o spento)", zona="flusso:condizioni",
                    voce="contratto", copre=["POST /characters/import"])
async def test_un_file_con_esaurimento_sospeso_non_diventa_acceso(client):
    cid = await _pg(client)
    dati = (await client.get(f"/characters/{cid}/export")).json()
    dati["character"]["settings"] = {**(dati["character"].get("settings") or {}), "conditions_suspended_on": {"exhaustion": 1}}
    dati["character"]["conditions"] = {"exhaustion": False}
    r = await client.post("/characters/import", json=dati)
    assert r.status_code == 201, r.text
    assert (await _scheda(client, r.json()["id"]))["conditions"].get("exhaustion") is not True


@pytest.mark.caccia(id="CB-1513", fonte="invariante (come CB-1296 e CB-1297): anche su un mostro una condizione è accesa o spenta", zona="flusso:condizioni", voce="contratto",
                    copre=["PATCH /sessions/{session_id}/encounter/combatants/{combatant_id}"])
@pytest.mark.parametrize("condizioni", [{"blinded": 5}, {"exhaustion": 99}, {"exhaustion": "x"}, {"exhaustion": True}])
async def test_il_master_non_scrive_valori_non_validi_su_un_mostro(client, test_session_factory, condizioni):
    sid, _cid, _pc, mostro = await _gm_su_pg(client, test_session_factory)
    url = f"/sessions/{sid}/encounter/combatants/{mostro}"
    assert (await client.patch(url, json={"conditions": condizioni})).status_code == 422
    assert (await client.patch(url, json={"conditions": {"blinded": True, "exhaustion": 2}})).status_code == 200


@pytest.mark.caccia(id="CB-1514", fonte="invariante: un effetto di condizione esiste solo finché la condizione è attiva", zona="flusso:condizioni", voce="annullamento",
                    copre=["PATCH /characters/{char_id}/conditions"])
async def test_spenta_da_un_altra_via_la_condizione_non_lascia_l_effetto(client, test_session_factory):
    from core.db.models import Character
    cid = await _pg(client)
    await _cond(client, cid, {"poisoned": True})
    async with test_session_factory() as s:
        await upsert_effect(s, ("character", cid), "poisoned", save=SaveSpec("constitution", 15, "end"), source_note="Ragno")
        await s.commit()
    async with test_session_factory() as s:  # come Protezione dai Veleni, che scrive la mappa
        char = await s.get(Character, cid)
        char.conditions = {**char.conditions, "poisoned": False}
        await s.commit()
    assert (await _scheda(client, cid))["condition_effects"] == []


@pytest.mark.caccia(id="CB-1515", fonte="2014 · Calmare Emozioni · pag. 218; 2024 · pag. 249 (la condizione è sospesa, poi torna)", zona="flusso:condizioni", voce="persistenza",
                    copre=["PATCH /characters/{char_id}/concentration", "POST /characters/{char_id}/duplicate"])
@pytest.mark.parametrize("ed", _ED)
@pytest.mark.parametrize("copia", [False, True])
async def test_calmare_emozioni_la_condizione_torna_con_cd_durata_e_fonte(client, test_session_factory, ed, copia):
    cid = await _pg(client, ed, "cleric")
    classe = (await _scheda(client, cid))["classes"][0]["id"]
    sid = (await client.post(f"/characters/{cid}/spells", json={
        "name": "calm-emotions", "level": 2, "srd_index": "calm-emotions", "is_prepared": True, "is_concentration": True, "class_id": classe})).json()["id"]
    await _cond(client, cid, {"charmed": True})
    async with test_session_factory() as s:
        await upsert_effect(s, ("character", cid), "charmed", save=SaveSpec("wisdom", 14, "end"), source_note="Driade")
        await s.commit()
    r = await client.post(f"/characters/{cid}/spells/{sid}/use", json={"slot_level": 2, "removal": {"targets": ["self"]}})
    assert r.status_code == 200, r.text
    assert (await _scheda(client, cid))["condition_effects"] == []
    chi = cid
    if copia:
        chi = (await client.post(f"/characters/{cid}/duplicate")).json()["id"]
    else:
        await client.patch(f"/characters/{cid}/concentration", json={"spell_id": None})
    j = await _scheda(client, chi)
    assert j["conditions"]["charmed"] is True
    [e] = j["condition_effects"]
    assert (e["save_dc"], e["source_note"]) == (14, "Driade")


@pytest.mark.caccia(id="CB-1516", fonte="decisione D-016 (tests/caccia/decisioni.md): massimo 9999 round", zona="flusso:condizioni", voce="limiti",
                    copre=["PATCH /characters/{char_id}/concentration", "POST /characters/import"])
async def test_anche_concentrazione_e_file_si_fermano_a_9999_round(client):
    cid = await _pg(client)
    sid = (await client.post(f"/characters/{cid}/spells", json={"name": "Scudo", "level": 1, "is_concentration": True})).json()["id"]
    for n, atteso in ((9999, 200), (10000, 422)):
        assert (await client.patch(f"/characters/{cid}/concentration", json={"spell_id": sid, "rounds": n})).status_code == atteso
    await _cond(client, cid, {"blinded": True}, durations={"blinded": 3})
    dati = (await client.get(f"/characters/{cid}/export")).json()
    dati["condition_effects"][0]["expiry_count"] = 50000
    nuovo = (await client.post("/characters/import", json=dati)).json()
    assert nuovo["condition_effects"][0]["expiry_count"] == 9999


@pytest.mark.caccia(id="CB-1522", fonte="decisione D-017 (tests/caccia/decisioni.md): protetta la condizione già attiva", zona="flusso:condizioni", voce="interazione",
                    copre=["PATCH /characters/{char_id}/conditions"])
async def test_riaccesa_senza_durata_non_riprende_l_effetto_rimasto(client, test_session_factory):
    cid = await _pg(client)
    async with test_session_factory() as s:
        await upsert_effect(s, ("character", cid), "poisoned", save=SaveSpec("constitution", 15, "end"), source_note="Ragno")
        await s.commit()
    await _cond(client, cid, {"poisoned": True})
    assert (await _scheda(client, cid))["condition_effects"] == []
