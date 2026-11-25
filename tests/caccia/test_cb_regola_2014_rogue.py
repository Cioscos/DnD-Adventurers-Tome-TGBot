"""Controlli della zona regola:2014/rogue."""
import asyncio

import pytest

from tests.integration._encounter_helpers import GM_ID
from tests.integration.rules.test_2014_barbarian_round1 import _combatant_states
from tests.integration.rules.test_2014_rogue_thief import _reflexes_encounter

SNEAK, LUCK, UNCANNY, EVASION = "rogue.sneak_attack", "rogue.stroke_of_luck", "rogue.uncanny_dodge", "rogue.evasion"
EVASION_KO, THIEF, DEATH = "rogue.evasion_failed", "rogue.spell_thief", "rogue.death_strike"
SOTTOCLASSI = {"thief": "Furfante", "assassin": "Assassino", "arcane_trickster": "Mistificatore Arcano"}


async def _ladro(client, livello, sottoclasse=None, edizione="2014", **punteggi):
    body = {"name": "Ladro", "rules_edition": edizione,
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


async def _usa(client, cid, chiave, **params):
    return await client.post(f"/characters/{cid}/features/{chiave}/use", json={"params": params})


async def _opzioni(client, cid, tiro, **query):
    r = await client.get(f"/characters/{cid}/roll-options", params={"roll": tiro, **query})
    assert r.status_code == 200, r.text
    return [o["key"] for o in r.json()]


async def _turno(client, cid):
    return (await client.get(f"/characters/{cid}/turn-state")).json()["turn"]


async def _pf_pieni(client, cid, pf=60):
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": pf})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": pf})


async def _condizioni(client, cid, **cond):
    r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": cond})
    assert r.status_code == 200, r.text


def _slot(scheda):
    return {s["level"]: s["total"] for s in scheda["spell_slots"] if s["total"]}


async def _mano_magica(client, cid):
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Mano magica", "level": 0, "srd_index": "mage-hand"})
    assert r.status_code == 201, r.text


# --- Rossi -------------------------------------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-1961", fonte="2014 · Ladro · Mistificatore Arcano, Incantesimi · pag. 80; Multiclasse, Incantesimi · pag. 164 (solo con più classi che hanno Incantesimi)",
                    zona="regola:2014/rogue", voce="interazione",
                    copre=["carta:2014/classes/rogue.md#Incantesimi / Spellcasting (Mistificatore Arcano 3, pag. 80)",
                           "carta:2014/general.md#Incantesimi / Spellcasting (multiclasse) (pag. 164)",
                           "POST /characters/{char_id}/classes", "GET /characters/{char_id}"])
@pytest.mark.parametrize("livello, altra, atteso", [(4, "paladin", {1: 3}), (7, "ranger", {1: 4, 2: 2})])
async def test_mistificatore_con_un_paladino_o_ranger_di_1_livello_usa_la_propria_tabella(client, livello, altra, atteso):
    cid = await _ladro(client, livello, "arcane_trickster")
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": altra, "level": 1, "hit_die": 10})
    assert r.status_code == 201, r.text
    assert _slot(await _scheda(client, cid)) == atteso  # il paladino e il ranger 2014 non lanciano al 1° livello


@pytest.mark.caccia(id="CB-1962", fonte="2014 · Ladro · Schivata Prodigiosa · pag. 78 (reazione); Condizioni, Incapacitato · pag. 291",
                    zona="regola:2014/rogue", voce="interazione",
                    copre=["carta:2014/classes/rogue.md#Schivata Prodigiosa / Uncanny Dodge (Ladro 5, pag. 78)",
                           "carta:2014/general.md#Incapacitato / Incapacitated (pag. 291)",
                           "PATCH /characters/{char_id}/hp", "GET /characters/{char_id}/roll-options"])
@pytest.mark.parametrize("condizione", ["incapacitated", "paralyzed"])
async def test_schivata_prodigiosa_non_si_usa_da_incapacitato(client, condizione):
    cid = await _ladro(client, 5)
    await _pf_pieni(client, cid)
    await _condizioni(client, cid, **{condizione: True})
    assert UNCANNY not in await _opzioni(client, cid, "damage_taken")
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 20, "options": [UNCANNY]})
    assert r.status_code == 409, r.text[:200]
    assert (await _scheda(client, cid))["current_hit_points"] == 60 and (await _turno(client, cid))["reaction_used"] is False


@pytest.mark.caccia(id="CB-1963", fonte="2014 · Ladro · Azione Scaltra · pag. 78, Ingannatore Versatile e Ladro di Incantesimi · pag. 80; Condizioni, Incapacitato · pag. 291",
                    zona="regola:2014/rogue", voce="interazione",
                    copre=["carta:2014/classes/rogue.md#Azione Scaltra / Cunning Action (Ladro 2, pag. 78)",
                           "carta:2014/classes/rogue.md#Ingannatore Versatile / Versatile Trickster (Mistificatore Arcano 13, pag. 80)",
                           "carta:2014/classes/rogue.md#Ladro di Incantesimi / Spell Thief (Mistificatore Arcano 17, pag. 80)",
                           "carta:2014/general.md#Incapacitato / Incapacitated (pag. 291)",
                           "POST /characters/{char_id}/features/{feature_key}/use"])
@pytest.mark.parametrize("chiave, livello, sottoclasse, params, slot", [
    ("rogue.cunning_action", 2, None, {"action": "dash"}, "bonus_used"),
    ("rogue.versatile_trickster", 13, "arcane_trickster", {}, "bonus_used"),
    ("rogue.spell_thief", 17, "arcane_trickster", {"stolen": False}, "reaction_used"),
])
async def test_azioni_bonus_e_reazioni_del_ladro_rifiutate_da_stordito(client, chiave, livello, sottoclasse, params, slot):
    cid = await _ladro(client, livello, sottoclasse)
    if sottoclasse:
        await _mano_magica(client, cid)
    usi = (await _riga(client, cid, chiave)).get("uses")
    await _condizioni(client, cid, stunned=True)
    r = await _usa(client, cid, chiave, **params)
    assert r.status_code == 409, r.text[:200]
    assert (await _turno(client, cid))[slot] is False and (await _riga(client, cid, chiave)).get("uses") == usi


@pytest.mark.caccia(id="CB-1964", fonte="2014 · Ladro · Mistificatore Arcano, Ladro di Incantesimi · pag. 80 (CD uguale alla CD degli incantesimi del ladro)",
                    zona="regola:2014/rogue", voce="regola",
                    copre=["carta:2014/classes/rogue.md#Ladro di Incantesimi / Spell Thief (Mistificatore Arcano 17, pag. 80)",
                           "POST /characters/{char_id}/items", "PATCH /characters/{char_id}/items/{item_id}", "GET /characters/{char_id}"])
async def test_ladro_di_incantesimi_mostra_la_cd_degli_incantesimi(client):
    cid = await _ladro(client, 17, "arcane_trickster", intelligence=16)
    r = await client.post(f"/characters/{cid}/items", json={"name": "Amuleto", "item_type": "accessory",
                                                           "item_metadata": {"bonuses": [{"target": "spell_dc", "value": 1}]}})
    assert r.status_code == 201, r.text
    iid = max(i["id"] for i in r.json()["items"])
    assert (await client.patch(f"/characters/{cid}/items/{iid}", json={"is_equipped": True, "equipment_slot": "neck"})).status_code == 200
    scheda = await _scheda(client, cid)
    cd = scheda["spellcasting"]["casters"][0]["save_dc"]
    assert cd == 8 + 6 + 3 + 1
    assert next(a for a in scheda["abilities"] if a["feature_key"] == THIEF)["dc"] == cd


@pytest.mark.caccia(id="CB-1965", fonte="2014 · Ladro · Inafferrabile · pag. 78 (spento solo da incapacitato); Combattere, Sorpresa · pag. 189 (la sorpresa non è una condizione)",
                    zona="regola:2014/rogue", voce="interazione",
                    copre=["carta:2014/classes/rogue.md#Inafferrabile / Elusive (Ladro 18, pag. 78)",
                           "PATCH /sessions/{session_id}/encounter/combatants/{combatant_id}", "POST /sessions/{session_id}/encounter/start",
                           "GET /sessions/{session_id}/live"])
async def test_inafferrabile_resta_visibile_nel_turno_della_sorpresa(client, test_session_factory):
    sid, _cid, live = await _reflexes_encounter(client, test_session_factory, surprised=True, level=18, subclass="Assassino")
    assert live["round"] == 1
    assert "elusive" in {s["key"] for s in await _combatant_states(client, sid, GM_ID)}


# --- Verdi -------------------------------------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-1966", fonte="2014 · Ladro · Attacco Furtivo · pag. 78 (tabella del Ladro, pag. 77)", zona="regola:2014/rogue", voce="limiti",
                    copre=["carta:2014/classes/rogue.md#Attacco Furtivo / Sneak Attack (Ladro 1, pag. 78)",
                           "POST /characters/{char_id}/items/{item_id}/attack", "POST /characters/{char_id}/attack/{attack_id}/damage"])
@pytest.mark.parametrize("livello, dadi", [(1, 1), (2, 1), (3, 2), (4, 2), (19, 10), (20, 10)])
async def test_attacco_furtivo_dadi_ai_livelli_di_soglia(client, livello, dadi):
    cid = await _ladro(client, livello)
    r = await client.post(f"/characters/{cid}/items", json={"name": "Stocco", "item_type": "weapon", "item_metadata": {
        "damage_dice": "1d8", "weapon_type": "melee", "properties": ["finesse"]}})
    iid = max(i["id"] for i in r.json()["items"])
    await client.patch(f"/characters/{cid}/items/{iid}", json={"is_equipped": True, "equipment_slot": "main_hand"})
    colpo = (await client.post(f"/characters/{cid}/items/{iid}/attack", json={
        "die": 10, "mode": "advantage", "dice": [10, 12], "defer_damage": True, "confirm_extra_attack": True})).json()
    r = await client.post(f"/characters/{cid}/attack/{colpo['attack_id']}/damage", json={"options": [SNEAK]})
    assert r.status_code == 200, r.text
    tiri = r.json()["option_result"]["extra_rolls"]
    assert len(tiri) == dadi and all(1 <= v <= 6 for v in tiri)


@pytest.mark.caccia(id="CB-1967", fonte="2014 · Ladro · Mistificatore Arcano, Tabella Incantesimi · pag. 80", zona="regola:2014/rogue", voce="limiti",
                    copre=["carta:2014/classes/rogue.md#Incantesimi / Spellcasting (Mistificatore Arcano 3, pag. 80)", "GET /characters/{char_id}"])
@pytest.mark.parametrize("livello, trucchetti, conosciuti, slot", [
    (3, 3, 3, {1: 2}), (4, 3, 4, {1: 3}), (7, 3, 5, {1: 4, 2: 2}), (10, 4, 7, {1: 4, 2: 3}),
    (13, 4, 9, {1: 4, 2: 3, 3: 2}), (19, 4, 12, {1: 4, 2: 3, 3: 3, 4: 1}), (20, 4, 13, {1: 4, 2: 3, 3: 3, 4: 1}),
])
async def test_mistificatore_slot_trucchetti_e_conosciuti_ai_livelli_di_soglia(client, livello, trucchetti, conosciuti, slot):
    scheda = await _scheda(client, await _ladro(client, livello, "arcane_trickster", intelligence=14))
    limiti = scheda["spellcasting"]["limits"][0]
    assert (limiti["cantrips_limit"], limiti["known_limit"], _slot(scheda)) == (trucchetti, conosciuti, slot)
    assert scheda["spellcasting"]["casters"][0]["ability"] == "intelligence"


@pytest.mark.caccia(id="CB-1968", fonte="2014 · Ladro · Mistificatore Arcano, Ladro di Incantesimi · pag. 80 (un uso per riposo lungo, reazione)",
                    zona="regola:2014/rogue", voce="regola",
                    copre=["carta:2014/classes/rogue.md#Ladro di Incantesimi / Spell Thief (Mistificatore Arcano 17, pag. 80)",
                           "POST /characters/{char_id}/features/{feature_key}/use", "POST /characters/{char_id}/rest"])
async def test_ladro_di_incantesimi_2014_spende_l_uso_anche_se_il_ts_riesce_e_torna_col_riposo_lungo(client):
    cid = await _ladro(client, 17, "arcane_trickster")
    assert (await _riga(client, cid, THIEF))["uses"] == 1
    r = await _usa(client, cid, THIEF, stolen=False)
    assert r.status_code == 200, r.text
    assert (await _riga(client, cid, THIEF))["uses"] == 0 and (await _turno(client, cid))["reaction_used"] is True
    await client.post(f"/characters/{cid}/rest", json={"rest_type": "short"})
    assert (await _riga(client, cid, THIEF))["uses"] == 0
    await client.post(f"/characters/{cid}/rest", json={"rest_type": "long"})
    assert (await _riga(client, cid, THIEF))["uses"] == 1


@pytest.mark.caccia(id="CB-1969", fonte="2014 · Ladro · Colpo di Fortuna · pag. 79 (attacco o prova di caratteristica, riposo breve o lungo)",
                    zona="regola:2014/rogue", voce="regola",
                    copre=["carta:2014/classes/rogue.md#Colpo di Fortuna / Stroke of Luck (Ladro 20, pag. 79)",
                           "POST /characters/{char_id}/ability_checks/{ability}/roll", "POST /characters/{char_id}/last-roll/options",
                           "POST /characters/{char_id}/rest", "GET /characters/{char_id}/roll-options"])
async def test_colpo_di_fortuna_2014_prove_e_attacchi_non_tiri_salvezza(client):
    assert await _riga(client, await _ladro(client, 19), LUCK) is None
    cid = await _ladro(client, 20)
    assert LUCK not in await _opzioni(client, cid, "save", ability="dexterity")
    await client.post(f"/characters/{cid}/ability_checks/strength/roll", json={"die": 2})
    r = await client.post(f"/characters/{cid}/last-roll/options", json={"options": [LUCK]})
    assert r.status_code == 200 and r.json()["die"] == 20, r.text[:200]
    assert (await _riga(client, cid, LUCK))["uses"] == 0
    await client.post(f"/characters/{cid}/rest", json={"rest_type": "short"})
    assert (await _riga(client, cid, LUCK))["uses"] == 1


@pytest.mark.caccia(id="CB-1970", fonte="2014 · Ladro · Mente Sfuggente · pag. 78 (solo Saggezza); 2024 · Ladro · Mente Sfuggente · pag. 131 (Saggezza e Carisma)",
                    zona="regola:2014/rogue", voce="edizioni",
                    copre=["carta:2014/classes/rogue.md#Mente Sfuggente / Slippery Mind (Ladro 15, pag. 78)",
                           "carta:2024/classes/rogue.md#Mente Sfuggente / Slippery Mind (Ladro 15, pag. 131)",
                           "POST /characters/{char_id}/saving_throws/{ability}/roll"])
@pytest.mark.parametrize("edizione, carisma", [("2014", 2), ("2024", 2 + 5)])
async def test_mente_sfuggente_per_edizione(client, edizione, carisma):
    cid = await _ladro(client, 15, edizione=edizione, wisdom=14, charisma=14)
    tiri = {ab: (await client.post(f"/characters/{cid}/saving_throws/{ab}/roll", json={"die": 10})).json()["bonus"]
            for ab in ("wisdom", "charisma")}
    assert tiri == {"wisdom": 2 + 5, "charisma": carisma}


@pytest.mark.caccia(id="CB-1971", fonte="2014 · Ladro · Assassino, Colpo Mortale · pag. 79 (CD 8 + Destrezza + competenza)", zona="regola:2014/rogue", voce="limiti",
                    copre=["carta:2014/classes/rogue.md#Colpo Mortale / Death Strike (Assassino 17, pag. 79)", "GET /characters/{char_id}"])
@pytest.mark.parametrize("livello, destrezza, cd", [(16, 18, None), (17, 18, 8 + 6 + 4), (20, 20, 8 + 6 + 5)])
async def test_colpo_mortale_cd_ai_livelli_di_soglia(client, livello, destrezza, cd):
    riga = await _riga(client, await _ladro(client, livello, "assassin", dexterity=destrezza), DEATH)
    assert (riga or {}).get("dc") == cd


@pytest.mark.caccia(id="CB-1972", fonte="2014 · Ladro · Elusione · pag. 78 (nessuna eccezione per l'incapacitato); Paralizzato · pag. 291", zona="regola:2014/rogue",
                    voce="regola", copre=["carta:2014/classes/rogue.md#Elusione / Evasion (Ladro 7, pag. 78)",
                                          "POST /characters/{char_id}/saving_throws/{ability}/roll", "PATCH /characters/{char_id}/hp"])
async def test_elusione_2014_dimezza_anche_da_paralizzato(client):
    cid = await _ladro(client, 7)
    await _pf_pieni(client, cid)
    await _condizioni(client, cid, paralyzed=True)
    r = await client.post(f"/characters/{cid}/saving_throws/dexterity/roll", json={"die": 15, "options": [EVASION]})
    assert r.status_code == 200 and r.json()["auto_fail"] is True, r.text[:200]
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 21, "options": [EVASION_KO]})
    assert r.status_code == 200 and r.json()["current_hit_points"] == 60 - 10, r.text[:200]


@pytest.mark.caccia(id="CB-1973", fonte="2014 · Ladro · Assassino, Maestro Infiltrato · pag. 79 (25 mo per identità)", zona="regola:2014/rogue", voce="ripetizione",
                    copre=["carta:2014/classes/rogue.md#Maestro Infiltrato / Infiltration Expertise (Assassino 9, pag. 79)",
                           "POST /characters/{char_id}/features/{feature_key}/use", "PATCH /characters/{char_id}/currency"])
async def test_maestro_infiltrato_doppio_invio_spende_25_mo_una_volta(client):
    cid = await _ladro(client, 9, "assassin")
    await client.patch(f"/characters/{cid}/currency", json={"gold": 100})
    rs = await asyncio.gather(*(_usa(client, cid, "rogue.infiltration_expertise", identity="Mario") for _ in range(3)))
    assert sorted(r.status_code for r in rs) == [200, 409, 409]
    assert (await _scheda(client, cid))["currency"]["gold"] == 75
