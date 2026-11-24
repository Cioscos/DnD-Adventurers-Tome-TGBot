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
@pytest.mark.xfail(strict=True, reason="CB-542 export/import e duplicazione perdono le durate delle condizioni")
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
