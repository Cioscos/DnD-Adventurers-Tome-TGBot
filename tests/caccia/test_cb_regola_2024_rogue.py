"""Controlli della zona regola:2024/rogue."""
import asyncio

import pytest

from tests.integration.rules.test_2014_rogue_thief import _reflexes_encounter

SNEAK, UNCANNY, RELIABLE = "rogue.sneak_attack", "rogue.uncanny_dodge", "rogue.reliable_talent"
POISON, ENVENOM, KNACK = "rogue.poison", "rogue.envenom_weapons", "rogue.psi_bolstered_knack"
PSI, THIEF, LUCK = "rogue.psionic_power", "rogue.spell_thief", "rogue.stroke_of_luck"
SOTTOCLASSI = {"thief": "Furfante", "assassin": "Assassino", "arcane_trickster": "Mistificatore Arcano",
               "soulknife": "Coltello dell'Anima"}


async def _ladro(client, livello, sottoclasse=None, **punteggi):
    body = {"name": "Ladro", "rules_edition": "2024",
            "initial_class": {"class_name": "rogue", "level": livello, "subclass": SOTTOCLASSI.get(sottoclasse)}}
    r = await client.post("/characters", json=body)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    for ab, v in punteggi.items():
        r = await client.patch(f"/characters/{cid}/ability_scores/{ab}", json={"value": v})
        assert r.status_code == 200, r.text
    return cid


async def _scheda(client, cid):
    return (await client.get(f"/characters/{cid}")).json()


async def _riga(client, cid, chiave):
    return next((a for a in (await _scheda(client, cid))["abilities"] if a["feature_key"] == chiave), None)


async def _opzioni(client, cid, tiro, **query):
    r = await client.get(f"/characters/{cid}/roll-options", params={"roll": tiro, **query})
    assert r.status_code == 200, r.text
    return [o["key"] for o in r.json()]


async def _turno(client, cid):
    return (await client.get(f"/characters/{cid}/turn-state")).json()["turn"]


async def _pf_pieni(client, cid, pf=60):
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": pf})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": pf})


async def _stocco(client, cid):
    r = await client.post(f"/characters/{cid}/items", json={"name": "Stocco", "item_type": "weapon", "item_metadata": {
        "damage_dice": "1d8", "weapon_type": "melee", "properties": ["finesse"], "damage_type": "dmg_piercing"}})
    assert r.status_code == 201, r.text
    iid = max(i["id"] for i in r.json()["items"])
    r = await client.patch(f"/characters/{cid}/items/{iid}", json={"is_equipped": True, "equipment_slot": "main_hand"})
    assert r.status_code == 200, r.text
    return iid


async def _colpo_e_danno(client, cid, wid, *opzioni):
    colpo = await client.post(f"/characters/{cid}/items/{wid}/attack", json={
        "die": 10, "mode": "advantage", "dice": [10, 12], "defer_damage": True, "confirm_extra_attack": True})
    assert colpo.status_code == 200, colpo.text
    return await client.post(f"/characters/{cid}/attack/{colpo.json()['attack_id']}/damage", json={"options": list(opzioni)})


# --- Rossi -------------------------------------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-2561", fonte="2024 · Ladro · Furfante, Riflessi del Furfante · pag. 137 (nessuna eccezione per la sorpresa); 2014 · Ladro · Furfante, Riflessi da Furfante · pag. 79 (non se sorpreso)",
                    zona="regola:2024/rogue", voce="edizioni",
                    copre=["carta:2024/classes/rogue.md#Riflessi del Furfante / Thief's Reflexes (Furfante 17, pag. 137)",
                           "carta:2014/classes/rogue.md#Riflessi da Furfante / Thief's Reflexes (Furfante 17, pag. 79)",
                           "PATCH /sessions/{session_id}/encounter/combatants/{combatant_id}", "POST /sessions/{session_id}/encounter/start"])
@pytest.mark.parametrize("edizione, secondo_turno", [("2014", False), pytest.param("2024", True, marks=pytest.mark.xfail(strict=True, reason="CB-2561: difforme dal manuale, confermato"))])
async def test_riflessi_del_furfante_colto_di_sorpresa_per_edizione(client, test_session_factory, edizione, secondo_turno):
    _sid, _cid, live = await _reflexes_encounter(client, test_session_factory, surprised=True, edition=edizione)
    assert any("Riflessi" in c["name"] for c in live["combatants"]) is secondo_turno


@pytest.mark.caccia(id="CB-2562", fonte="2024 · Ladro · Coltello dell'Anima, Conoscenza Potenziata da Psi · pag. 135 (abilità o strumento competente)",
                    zona="regola:2024/rogue", voce="regola",
                    copre=["carta:2024/classes/rogue.md#Conoscenza Potenziata da Psi / Psi-Bolstered Knack (Coltello dell'Anima 3, pag. 135)",
                           "POST /characters/{char_id}/tool_checks/{tool}/roll", "POST /characters/{char_id}/last-roll/options"])
@pytest.mark.xfail(strict=True, reason="CB-2562: difforme dal manuale, confermato")
async def test_conoscenza_potenziata_da_psi_vale_per_la_prova_con_strumento(client, dadi):
    cid = await _ladro(client, 3, "soulknife", dexterity=14)  # arnesi da scasso dalla classe
    prova = await client.post(f"/characters/{cid}/tool_checks/thieves_tools/roll", json={"ability": "dexterity", "die": 3})
    assert prova.status_code == 200, prova.text
    dadi(4)
    r = await client.post(f"/characters/{cid}/last-roll/options", json={"options": [KNACK]})
    assert r.status_code == 200, r.text[:200]
    assert r.json()["total"] == prova.json()["total"] + 4


@pytest.mark.caccia(id="CB-2563", fonte="2024 · Ladro · Dote Affidabile · pag. 131; Furfante, Usare Dispositivi Magici · pag. 137 (prova di Intelligenza (Arcano))",
                    zona="regola:2024/rogue", voce="interazione",
                    copre=["carta:2024/classes/rogue.md#Dote Affidabile / Reliable Talent (Ladro 7, pag. 131)",
                           "carta:2024/classes/rogue.md#Usare Dispositivi Magici / Use Magic Device (Furfante 13, pag. 137)",
                           "PATCH /characters/{char_id}/skills", "POST /characters/{char_id}/items/{item_id}/scroll"])
async def test_la_prova_di_arcano_della_pergamena_rispetta_dote_affidabile(client, dadi):
    cid = await _ladro(client, 13, "thief")  # Intelligenza 10, competenza +5
    assert (await client.patch(f"/characters/{cid}/skills", json={"skills": {"arcana": True}})).status_code == 200
    r = await client.post(f"/characters/{cid}/items", json={
        "name": "Pergamena", "item_type": "consumable", "quantity": 1, "item_metadata": {"subtype": "scroll"}})
    assert r.status_code == 201, r.text
    iid = max(i["id"] for i in r.json()["items"])
    prova = await client.post(f"/characters/{cid}/skills/arcana/roll", json={"die": 3})
    assert prova.json()["total"] == 10 + 5  # la prova di Arcano normale: 3 diventa 10, competenza +5
    dadi(3)  # il d20 vale 10 con Dote Affidabile: 10 + 5 contro CD 13
    r = await client.post(f"/characters/{cid}/items/{iid}/scroll", json={"spell_level": 3})
    assert r.status_code == 200, r.text[:200]
    assert r.json()["homebrew_notifications"][0]["severity"] == "success"


@pytest.mark.caccia(id="CB-2564", fonte="2024 · Ladro · Schivata Prodigiosa · pag. 131 (attaccante che si vede); Condizioni, Accecato",
                    zona="regola:2024/rogue", voce="regola",
                    copre=["carta:2024/classes/rogue.md#Schivata Prodigiosa / Uncanny Dodge (Ladro 5, pag. 131)",
                           "PATCH /characters/{char_id}/hp", "GET /characters/{char_id}/roll-options"])
@pytest.mark.xfail(strict=True, reason="CB-2564: difforme dal manuale, confermato")
async def test_schivata_prodigiosa_non_si_usa_da_accecato(client):
    cid = await _ladro(client, 5)
    await _pf_pieni(client, cid)
    r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"blinded": True}})
    assert r.status_code == 200, r.text
    assert UNCANNY not in await _opzioni(client, cid, "damage_taken")
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 20, "options": [UNCANNY]})
    assert r.status_code == 409, r.text[:200]
    assert (await _scheda(client, cid))["current_hit_points"] == 60


@pytest.mark.caccia(id="CB-2565", fonte="2024 · Ladro · Assassino, Armi Velenose · pag. 134 (2d6 danni da veleno)",
                    zona="regola:2024/rogue", voce="regola",
                    copre=["carta:2024/classes/rogue.md#Armi Velenose / Envenom Weapons (Assassino 13, pag. 134)",
                           "POST /characters/{char_id}/items/{item_id}/attack", "POST /characters/{char_id}/attack/{attack_id}/damage"])
@pytest.mark.xfail(strict=True, reason="CB-2565: difforme dal manuale, confermato")
async def test_armi_velenose_i_2d6_sono_danni_da_veleno(client):
    cid = await _ladro(client, 13, "assassin", dexterity=16)
    r = await _colpo_e_danno(client, cid, await _stocco(client, cid), SNEAK, POISON, ENVENOM)
    assert r.status_code == 200, r.text[:200]
    esito = r.json()["option_result"]
    assert len(esito["extra_rolls"]) == 7 - 1 + 2
    assert esito["extra_types"][-2:] == ["poison", "poison"]


# --- Verdi -------------------------------------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-2566", fonte="2024 · Ladro · Attacco Furtivo · pag. 129 (tabella del Ladro)", zona="regola:2024/rogue", voce="limiti",
                    copre=["carta:2024/classes/rogue.md#Attacco Furtivo / Sneak Attack (Ladro 1, pag. 129)",
                           "POST /characters/{char_id}/items/{item_id}/attack", "POST /characters/{char_id}/attack/{attack_id}/damage"])
@pytest.mark.parametrize("livello, dadi_furtivo", [(1, 1), (2, 1), (3, 2), (4, 2), (18, 9), (19, 10), (20, 10)])
async def test_attacco_furtivo_2024_dadi_ai_livelli_di_soglia(client, livello, dadi_furtivo):
    cid = await _ladro(client, livello)
    r = await _colpo_e_danno(client, cid, await _stocco(client, cid), SNEAK)
    assert r.status_code == 200, r.text[:200]
    assert len(r.json()["option_result"]["extra_rolls"]) == dadi_furtivo


@pytest.mark.caccia(id="CB-2567", fonte="2024 · Ladro · Mistificatore Arcano, Incantesimi · pag. 132 (tabella preparati e slot)", zona="regola:2024/rogue",
                    voce="limiti", copre=["carta:2024/classes/rogue.md#Incantesimi / Spellcasting (Mistificatore Arcano 3, pag. 132)",
                                          "GET /characters/{char_id}"])
@pytest.mark.parametrize("livello, trucchetti, preparati, slot", [
    (3, 3, 3, {1: 2}), (4, 3, 4, {1: 3}), (6, 3, 4, {1: 3}), (7, 3, 5, {1: 4, 2: 2}), (9, 3, 6, {1: 4, 2: 2}),
    (10, 4, 7, {1: 4, 2: 3}), (12, 4, 8, {1: 4, 2: 3}), (13, 4, 9, {1: 4, 2: 3, 3: 2}), (15, 4, 10, {1: 4, 2: 3, 3: 2}),
    (16, 4, 11, {1: 4, 2: 3, 3: 3}), (18, 4, 11, {1: 4, 2: 3, 3: 3}), (19, 4, 12, {1: 4, 2: 3, 3: 3, 4: 1}),
    (20, 4, 13, {1: 4, 2: 3, 3: 3, 4: 1}),
])
async def test_mistificatore_2024_preparati_trucchetti_e_slot_ai_livelli_di_soglia(client, livello, trucchetti, preparati, slot):
    scheda = await _scheda(client, await _ladro(client, livello, "arcane_trickster", intelligence=14))
    limiti = scheda["spellcasting"]["limits"][0]
    assert (limiti["cantrips_limit"], limiti["prepared_limit"], limiti["known_limit"]) == (trucchetti, preparati, None)
    assert {s["level"]: s["total"] for s in scheda["spell_slots"] if s["total"]} == slot
    assert limiti["school_names"] is None  # nel 2024 nessun vincolo di scuola


@pytest.mark.caccia(id="CB-2568", fonte="2024 · Ladro · Colpo Astuto · pag. 130; Colpi Subdoli · pag. 131 (costi in dadi)", zona="regola:2024/rogue",
                    voce="regola", copre=["carta:2024/classes/rogue.md#Colpo Astuto / Cunning Strike (Ladro 5, pag. 130)",
                                          "carta:2024/classes/rogue.md#Sgambetto / Trip (Colpo Astuto, Ladro 5, pag. 130)",
                                          "carta:2024/classes/rogue.md#Ritirata / Withdraw (Colpo Astuto, Ladro 5, pag. 131)",
                                          "carta:2024/classes/rogue.md#Stordimento / Daze (Colpo Astuto, Ladro 14, pag. 131)",
                                          "carta:2024/classes/rogue.md#Oscurare / Obscure (Colpo Astuto, Ladro 14, pag. 131)",
                                          "carta:2024/classes/rogue.md#Mettere K.O. / Knock Out (Colpo Astuto, Ladro 14, pag. 131)",
                                          "POST /characters/{char_id}/attack/{attack_id}/damage"])
@pytest.mark.parametrize("opzione, costo", [("rogue.trip", 1), ("rogue.withdraw", 1), ("rogue.daze", 2), ("rogue.obscure", 3),
                                            ("rogue.knock_out", 6)])
async def test_colpo_astuto_toglie_il_costo_dai_dadi_del_furtivo(client, opzione, costo):
    cid = await _ladro(client, 14, dexterity=16)  # 7d6
    r = await _colpo_e_danno(client, cid, await _stocco(client, cid), SNEAK, opzione)
    assert r.status_code == 200, r.text[:200]
    assert len(r.json()["option_result"]["extra_rolls"]) == 7 - costo


@pytest.mark.caccia(id="CB-2569", fonte="2024 · Ladro · Coltello dell'Anima, Potere Psionico · pag. 135 (tabella dei dadi)", zona="regola:2024/rogue",
                    voce="limiti", copre=["carta:2024/classes/rogue.md#Potere Psionico / Psionic Power (Coltello dell'Anima 3, pag. 135)",
                                          "GET /characters/{char_id}"])
@pytest.mark.parametrize("livello, dadi_psi", [(2, None), (3, 4), (4, 4), (5, 6), (8, 6), (9, 8), (12, 8), (13, 10), (16, 10), (17, 12), (20, 12)])
async def test_dadi_energia_psionica_ai_livelli_di_soglia(client, livello, dadi_psi):
    riga = await _riga(client, await _ladro(client, livello, "soulknife"), PSI)
    assert (riga or {}).get("max_uses") == dadi_psi


@pytest.mark.caccia(id="CB-2570", fonte="2024 · Ladro · Dote Affidabile · pag. 131 (dal 7° livello, abilità o strumento)", zona="regola:2024/rogue",
                    voce="limiti", copre=["carta:2024/classes/rogue.md#Dote Affidabile / Reliable Talent (Ladro 7, pag. 131)",
                                          "POST /characters/{char_id}/skills/{skill_name}/roll", "POST /characters/{char_id}/tool_checks/{tool}/roll"])
@pytest.mark.parametrize("livello, d20", [(6, 3), (7, 10), (20, 10)])
async def test_dote_affidabile_dal_7_livello_su_abilita_e_strumenti(client, livello, d20):
    cid = await _ladro(client, livello)
    assert (await client.patch(f"/characters/{cid}/skills", json={"skills": {"stealth": True}})).status_code == 200
    abilita = await client.post(f"/characters/{cid}/skills/stealth/roll", json={"die": 3})
    strumento = await client.post(f"/characters/{cid}/tool_checks/thieves_tools/roll", json={"ability": "dexterity", "die": 3})
    assert (abilita.json()["die"], strumento.json()["die"]) == (d20, d20)


@pytest.mark.caccia(id="CB-2571", fonte="2024 · Ladro · Mistificatore Arcano, Ladro di Incantesimi · pag. 133 (uso perso solo col furto riuscito)",
                    zona="regola:2024/rogue", voce="regola",
                    copre=["carta:2024/classes/rogue.md#Ladro di Incantesimi / Spell Thief (Mistificatore Arcano 17, pag. 133)",
                           "POST /characters/{char_id}/features/{feature_key}/use", "POST /characters/{char_id}/rest"])
async def test_ladro_di_incantesimi_2024_spende_l_uso_solo_col_furto_riuscito(client):
    cid = await _ladro(client, 17, "arcane_trickster", intelligence=16)
    r = await client.post(f"/characters/{cid}/features/{THIEF}/use", json={"params": {"stolen": False}})
    assert r.status_code == 200, r.text
    assert (await _riga(client, cid, THIEF))["uses"] == 1 and (await _turno(client, cid))["reaction_used"] is True
    await client.post(f"/characters/{cid}/turn/new")
    r = await client.post(f"/characters/{cid}/features/{THIEF}/use",
                          json={"params": {"stolen": True, "spell_level": "1", "spell": "Dardo Incantato"}})
    assert r.status_code == 200, r.text
    assert (await _riga(client, cid, THIEF))["uses"] == 0
    await client.post(f"/characters/{cid}/rest", json={"rest_type": "long", "confirm_early": True})
    assert (await _riga(client, cid, THIEF))["uses"] == 1


@pytest.mark.caccia(id="CB-2572", fonte="2024 · Ladro · Colpo di Fortuna · pag. 131 (un uso fra un riposo e l'altro)", zona="regola:2024/rogue",
                    voce="ripetizione", copre=["carta:2024/classes/rogue.md#Colpo di Fortuna / Stroke of Luck (Ladro 20, pag. 131)",
                                               "POST /characters/{char_id}/saving_throws/{ability}/roll", "POST /characters/{char_id}/last-roll/options"])
async def test_colpo_di_fortuna_doppio_invio_spende_un_uso(client):
    cid = await _ladro(client, 20)
    assert (await client.post(f"/characters/{cid}/saving_throws/wisdom/roll", json={"die": 2})).status_code == 200
    rs = await asyncio.gather(*(client.post(f"/characters/{cid}/last-roll/options", json={"options": [LUCK]}) for _ in range(2)))
    assert sorted(r.status_code for r in rs) == [200, 409]
    assert (await _riga(client, cid, LUCK))["uses"] == 0


@pytest.mark.caccia(id="CB-2573", fonte="2024 · Ladro · Coltello dell'Anima, Conoscenza Potenziata da Psi · pag. 135 (il dado si spende solo se la prova riesce)",
                    zona="regola:2024/rogue", voce="annullamento",
                    copre=["carta:2024/classes/rogue.md#Conoscenza Potenziata da Psi / Psi-Bolstered Knack (Coltello dell'Anima 3, pag. 135)",
                           "POST /characters/{char_id}/last-roll/options", "POST /characters/{char_id}/last-roll/refund"])
async def test_conoscenza_potenziata_da_psi_fallita_comunque_rende_il_dado(client, dadi):
    cid = await _ladro(client, 3, "soulknife")
    assert (await client.patch(f"/characters/{cid}/skills", json={"skills": {"stealth": True}})).status_code == 200
    assert (await client.post(f"/characters/{cid}/skills/stealth/roll", json={"die": 2})).status_code == 200
    dadi(1)
    assert (await client.post(f"/characters/{cid}/last-roll/options", json={"options": [KNACK]})).status_code == 200
    assert (await _riga(client, cid, PSI))["uses"] == 3
    assert (await client.post(f"/characters/{cid}/last-roll/refund")).status_code == 200
    assert (await _riga(client, cid, PSI))["uses"] == 4
