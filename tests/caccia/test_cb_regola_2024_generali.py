"""Controlli della zona regola:2024/generali (parte generali: Fondamenti, Multiclasse, Lancio di incantesimi)."""
import pytest

from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, seed_session, setup_full_encounter
from tests.integration.rules.test_2014_warlock_invocations import _spells_by_index
from tests.integration.rules.test_2024_warlock import _caster24


async def _pg(client, classe="wizard", livello=5, edizione="2024", **punteggi):
    r = await client.post("/characters", json={"name": "P", "rules_edition": edizione,
                                               "initial_class": {"class_name": classe, "level": livello}})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    for abilita, valore in punteggi.items():
        assert (await client.patch(f"/characters/{cid}/ability_scores/{abilita}", json={"value": valore})).status_code == 200
    return cid


async def _scheda(client, cid):
    return (await client.get(f"/characters/{cid}")).json()


async def _classe(client, cid, classe, livello):
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": classe, "level": livello})
    assert r.status_code in (200, 201), r.text
    return await _scheda(client, cid)


async def _pf(client, cid, massimo, attuali):
    assert (await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": massimo})).status_code == 200
    assert (await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": attuali})).status_code == 200


def _slot(scheda):
    return {s["level"]: s["total"] for s in scheda["spell_slots"] if s["total"] and not s["is_pact"]}


# ---------------------------------------------------------------------------
# Rossi
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-2861", fonte="2024 · Regole di gioco · Vantaggio e Svantaggio, rilanci · pag. 12-13; Ispirazione Eroica · pag. 13", zona="regola:2024/generali",
                    voce="interazione", copre=["carta:2024/general.md#Vantaggio e Svantaggio / Advantage/Disadvantage (pag. 12-13)",
                                               "carta:2024/general.md#Ispirazione Eroica / Heroic Inspiration (pag. 13)",
                                               "POST /characters/{char_id}/skills/{skill_name}/roll",
                                               "POST /characters/{char_id}/saving_throws/{ability}/roll"])
@pytest.mark.parametrize("percorso", ["skills/athletics/roll", "saving_throws/wisdom/roll"])
async def test_il_rilancio_con_ispirazione_tocca_un_solo_d20_e_lo_svantaggio_resta(client, percorso):
    cid = await _pg(client)
    await client.patch(f"/characters/{cid}/inspiration", json={"heroic_inspiration": True})
    primo = (await client.post(f"/characters/{cid}/{percorso}", json={"mode": "disadvantage", "dice": [3, 15]})).json()
    assert primo["die"] == 3 and primo["mode"] == "disadvantage"
    r = await client.post(f"/characters/{cid}/{percorso}", json={"with_inspiration": True, "die": 18})
    assert r.status_code == 200, r.text
    # si rilancia uno solo dei due d20: l'altro (15) resta e con lo svantaggio vale il più basso
    assert r.json()["die"] <= 15, r.json()


@pytest.mark.caccia(id="CB-2862", fonte="2024 · Regole di gioco · Ispirazione Eroica · pag. 13", zona="regola:2024/generali",
                    voce="regola", copre=["carta:2024/general.md#Ispirazione Eroica / Heroic Inspiration (pag. 13)",
                                          "POST /sessions/{session_id}/inspiration/grant", "POST /characters/{char_id}/rest"])
@pytest.mark.parametrize("da_chi", ["master", "riposo_lungo_umano"])
async def test_un_ispirazione_ricevuta_avendone_gia_una_si_puo_cedere(client, test_session_factory, da_chi):
    if da_chi == "master":
        sid, cid = await seed_session(test_session_factory)
        as_user(PLAYER_ID)
        assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
        await client.patch(f"/characters/{cid}/inspiration", json={"heroic_inspiration": True})
        as_user(GM_ID)
        r = await client.post(f"/sessions/{sid}/inspiration/grant", json={"character_id": cid, "heroic_inspiration": True})
        assert r.status_code == 204, r.text
        as_user(PLAYER_ID)
    else:
        r = await client.post("/characters", json={
            "name": "U", "rules_edition": "2024", "initial_class": {"class_name": "fighter"},
            "species_2024": {"key": "2024_human", "options": {"size": "medium", "skill": "arcana", "origin_feat": "2024_lucky"}}})
        assert r.status_code == 201, r.text
        cid = r.json()["id"]
        await client.patch(f"/characters/{cid}/inspiration", json={"heroic_inspiration": True})
        assert (await client.post(f"/characters/{cid}/rest", json={"rest_type": "long"})).status_code == 200
    scheda = await _scheda(client, cid)
    # ne tiene una e la seconda ricevuta si può dare a un compagno che ne è privo
    assert (scheda["heroic_inspiration"], scheda["inspiration_extra"]) == (True, True)


@pytest.mark.caccia(id="CB-2863", fonte="2024 · Lancio di incantesimi · Combinare effetti · pag. 238", zona="regola:2024/generali",
                    voce="ripetizione", copre=["carta:2024/general.md#Combinare effetti / Combining Spell Effects (pag. 238)",
                                               "POST /characters/{char_id}/spells/{spell_id}/use"])
async def test_lo_stesso_incantesimo_rilanciato_piu_debole_non_toglie_quello_piu_potente(client):
    cid = await _pg(client, "cleric", 5)
    aiuto = (await client.post(f"/characters/{cid}/spells", json={"name": "Aid", "srd_index": "aid", "level": 2, "is_prepared": True})).json()
    base = (await _scheda(client, cid))["computed"]["hp_max_effective"]
    assert (await client.post(f"/characters/{cid}/spells/{aiuto['id']}/use", json={"slot_level": 3})).status_code == 200
    assert (await _scheda(client, cid))["computed"]["hp_max_effective"] == base + 10
    await client.post(f"/characters/{cid}/turn/new")
    assert (await client.post(f"/characters/{cid}/spells/{aiuto['id']}/use", json={"slot_level": 2})).status_code == 200
    # i due lanci si sovrappongono: vale il più potente (+10), non l'ultimo (+5)
    assert (await _scheda(client, cid))["computed"]["hp_max_effective"] == base + 10


@pytest.mark.caccia(id="CB-2864", fonte="2024 · Lancio di incantesimi · Tempo di lancio, un solo slot per turno · pag. 236; Lanciare senza slot · pag. 235-236", zona="regola:2024/generali",
                    voce="interazione", copre=["carta:2024/general.md#Tempo di lancio / Casting Time (pag. 236)",
                                               "carta:2024/general.md#Lanciare senza slot / Casting Without Slots (pag. 235-236)",
                                               "POST /characters/{char_id}/spells/{spell_id}/use"])
@pytest.mark.parametrize("chi", ["warlock_a_volonta", "ranger_marchio_gratuito"])
async def test_un_lancio_senza_slot_dopo_uno_con_slot_non_chiede_conferme(client, chi):
    if chi == "warlock_a_volonta":
        cid = await _caster24(client, 2, "armor_of_shadows")
    else:
        cid = await _pg(client, "ranger", 2)
    prova = (await client.post(f"/characters/{cid}/spells", json={
        "name": "Prova", "level": 1, "is_prepared": True,  # l'altra azione del turno resta per il lancio senza slot
        "casting_time": "1 azione bonus" if chi == "warlock_a_volonta" else "1 azione"})).json()
    assert (await client.post(f"/characters/{cid}/spells/{prova['id']}/use", json={"slot_level": 1})).status_code == 200
    if chi == "warlock_a_volonta":
        senza_slot = (await _spells_by_index(client, cid))["mage-armor"]
    else:
        assert (await client.post(f"/characters/{cid}/features/ranger.favored_enemy/use", json={})).status_code == 200
        senza_slot = (await _spells_by_index(client, cid))["hunters-mark"]
    r = await client.post(f"/characters/{cid}/spells/{senza_slot['id']}/use", json={"free_cast": True})
    # nel turno si è speso un solo slot: il lancio senza slot non ne spende un secondo
    assert r.status_code == 200, r.text


@pytest.mark.caccia(id="CB-2865", fonte="2024 · Regole di gioco · Condizioni, istanze multiple · pag. 29", zona="regola:2024/generali",
                    voce="interazione", copre=["carta:2024/general.md#Condizioni / Conditions (pag. 29)",
                                               "POST /sessions/{session_id}/encounter/combatants/{combatant_id}/conditions",
                                               "POST /sessions/{session_id}/encounter/next-turn"])
async def test_una_seconda_istanza_piu_corta_non_accorcia_la_condizione(client, test_session_factory):
    sid, _ = await setup_full_encounter(client, test_session_factory)
    pg, goblin1, goblin2 = (await client.post(f"/sessions/{sid}/encounter/start", json={})).json()["combatants"]
    as_user(PLAYER_ID)
    assert (await client.patch(f"/characters/{pg['character_id']}", json={"rules_edition": "2024"})).status_code == 200
    as_user(GM_ID)
    url = f"/sessions/{sid}/encounter/combatants/{pg['id']}/conditions"
    for fonte, round_ in ((goblin1, 10), (goblin2, 1)):
        r = await client.post(url, json={"slug": "frightened", "expiry": {"anchor": "owner", "edge": "end", "count": round_},
                                         "source_combatant_id": fonte["id"]})
        assert r.status_code == 200, r.text
    for _ in range(4):  # poco più di un round: l'istanza da 10 round è ancora in corso
        assert (await client.post(f"/sessions/{sid}/encounter/next-turn")).status_code == 200
    as_user(PLAYER_ID)
    assert (await _scheda(client, pg["character_id"]))["conditions"].get("frightened") is True


@pytest.mark.caccia(id="CB-2866", fonte="2024 · Regole di gioco · Tiri per i danni · pag. 27", zona="regola:2024/generali",
                    voce="limiti", copre=["carta:2024/general.md#Tiri per i danni / Damage Rolls (pag. 27)",
                                          "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
async def test_il_danno_di_un_incantesimo_non_scende_sotto_zero(client):
    cid = await _pg(client, "wizard", 1)
    trucchetto = (await client.post(f"/characters/{cid}/spells", json={"name": "Dardo", "level": 0, "damage_dice": "1d10",
                                                                       "damage_type": "fire"})).json()
    r = await client.post(f"/characters/{cid}/spells/{trucchetto['id']}/roll_damage",
                          json={"main_rolls": [1], "extra_dice": "1d4-5", "extra_rolls": [1]})
    assert r.status_code == 200, r.text
    assert r.json()["total"] >= 0 and r.json()["half_damage"] >= 0, r.json()


@pytest.mark.caccia(id="CB-2867", fonte="2024 · Lancio di incantesimi · Livello dell'incantesimo e Slot incantesimo · pag. 235", zona="regola:2024/generali",
                    voce="limiti", copre=["carta:2024/general.md#Livello dell'incantesimo / Spell Level (pag. 235)",
                                          "carta:2024/general.md#Slot incantesimo / Spell Slots (pag. 235)",
                                          "POST /characters/{char_id}/spells", "POST /characters/{char_id}/spell_slots"])
@pytest.mark.parametrize("percorso,corpo", [
    ("spells", {"name": "Decimo", "level": 10}), ("spells", {"name": "Negativo", "level": -1}),
    ("spell_slots", {"level": 0, "total": 1}), ("spell_slots", {"level": 10, "total": 1})])
async def test_livelli_di_incantesimo_e_di_slot_fuori_dalla_scala_rifiutati(client, percorso, corpo):
    cid = await _pg(client)
    r = await client.post(f"/characters/{cid}/{percorso}", json=corpo)
    assert r.status_code == 422, (r.status_code, r.text[:200])


@pytest.mark.caccia(id="CB-2868", fonte="2024 · Regole di gioco · Punteggi di caratteristica, massimo 30 · pag. 10", zona="regola:2024/generali",
                    voce="limiti", copre=["carta:2024/general.md#Punteggi di caratteristica / Ability Scores (pag. 10)",
                                          "POST /characters/{char_id}/items", "GET /characters/{char_id}"])
async def test_il_punteggio_effettivo_non_supera_30(client):
    cid = await _pg(client, strength=30)
    meta = {"ability_modifiers": [{"ability": "strength", "kind": "relative", "value": 2}]}
    r = await client.post(f"/characters/{cid}/items", json={"name": "Cintura", "item_metadata": meta, "is_equipped": True})
    assert r.status_code in (200, 201), r.text
    forza = next(s for s in (await _scheda(client, cid))["ability_scores"] if s["name"] == "strength")
    assert (forza["value"], forza["modifier"]) == (30, 10), forza


# ---------------------------------------------------------------------------
# Verdi
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-2869", fonte="2024 · Regole di gioco · Competenza, tabella · pag. 13; Multiclasse, livello totale · pag. 44", zona="regola:2024/generali",
                    voce="limiti", copre=["carta:2024/general.md#Competenza / Proficiency (pag. 13)",
                                          "carta:2024/general.md#Regole di base (pag. 44)", "GET /characters/{char_id}"])
@pytest.mark.parametrize("classi,bonus", [
    ([("fighter", 1)], 2), ([("fighter", 4)], 2), ([("fighter", 5)], 3), ([("fighter", 8)], 3), ([("fighter", 9)], 4),
    ([("fighter", 12)], 4), ([("fighter", 13)], 5), ([("fighter", 16)], 5), ([("fighter", 17)], 6), ([("fighter", 20)], 6),
    ([("wizard", 3), ("fighter", 2)], 3)])
async def test_bonus_di_competenza_dal_livello_totale(client, classi, bonus):
    (prima, livello), *altre = classi
    cid = await _pg(client, prima, livello)
    for classe, liv in altre:
        await _classe(client, cid, classe, liv)
    assert (await _scheda(client, cid))["proficiency_bonus"] == bonus


@pytest.mark.caccia(id="CB-2870", fonte="2024 · Multiclasse · Lancio di incantesimi, esempio Ranger 4 / Stregone 3, e tabella degli slot · pag. 44-45", zona="regola:2024/generali",
                    voce="interazione", copre=["carta:2024/general.md#Lancio di incantesimi nel multiclasse / Spellcasting (pag. 44-45)",
                                               "carta:2024/general.md#Multiclass Spellcaster: Spell Slots per Spell Level (pag. 45)",
                                               "POST /characters/{char_id}/classes"])
async def test_ranger_4_stregone_3_slot_e_preparati_per_classe(client):
    cid = await _pg(client, "ranger", 4)
    scheda = await _classe(client, cid, "sorcerer", 3)
    assert _slot(scheda) == {1: 4, 2: 3, 3: 2}
    limiti = {c["class_name"]: c for c in scheda["spellcasting"]["limits"]}
    assert limiti["ranger"]["prepared_limit"] == 5 and limiti["sorcerer"]["prepared_limit"] == 6


@pytest.mark.caccia(id="CB-2871", fonte="2024 · Multiclasse · Slot: metà dei livelli di Paladino per eccesso · pag. 44; 2014 · Multiclasse · Incantesimi: metà per difetto · pag. 164",
                    zona="regola:2024/generali", voce="edizioni",
                    copre=["carta:2024/general.md#Lancio di incantesimi nel multiclasse / Spellcasting (pag. 44-45)",
                           "carta:2014/general.md#Incantesimi / Spellcasting (multiclasse) (pag. 164)", "POST /characters/{char_id}/classes"])
@pytest.mark.parametrize("edizione,slot", [("2024", {1: 4, 2: 2}), ("2014", {1: 3})])
async def test_paladino_3_stregone_1_slot_per_edizione(client, edizione, slot):
    cid = await _pg(client, "paladin", 3, edizione=edizione)
    assert _slot(await _classe(client, cid, "sorcerer", 1)) == slot


@pytest.mark.caccia(id="CB-2872", fonte="2024 · Multiclasse · Regole di base: PF fissi della nuova classe, niente nuovi tiri salvezza · pag. 44", zona="regola:2024/generali",
                    voce="interazione", copre=["carta:2024/general.md#Regole di base (pag. 44)", "POST /characters/{char_id}/classes"])
async def test_seconda_classe_pf_fissi_e_nessun_tiro_salvezza_in_piu(client):
    cid = await _pg(client, "fighter", 1, constitution=10)
    prima = await _scheda(client, cid)
    assert prima["hit_points"] == 10
    scheda = await _classe(client, cid, "wizard", 1)
    assert scheda["hit_points"] == 10 + 4  # d6: il valore fisso, non il massimo del dado
    assert {k for k, v in scheda["saving_throws"].items() if v} == {k for k, v in prima["saving_throws"].items() if v}


@pytest.mark.caccia(id="CB-2873", fonte="2024 · Multiclasse · Trucchetti col livello totale · pag. 44-45", zona="regola:2024/generali",
                    voce="normale", copre=["carta:2024/general.md#Lancio di incantesimi nel multiclasse / Spellcasting (pag. 44-45)",
                                           "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
async def test_trucchetto_scala_con_il_livello_totale(client):
    cid = await _pg(client, "wizard", 1)
    await _classe(client, cid, "fighter", 4)
    trucchetto = (await client.post(f"/characters/{cid}/spells", json={"name": "Dardo", "level": 0, "damage_dice": "1d10",
                                                                       "damage_type": "fire"})).json()
    r = await client.post(f"/characters/{cid}/spells/{trucchetto['id']}/roll_damage", json={"main_rolls": [3, 4]})
    assert r.status_code == 200, r.text
    assert (r.json()["scaled_dice"], r.json()["total"]) == ("2d10", 7), r.json()


@pytest.mark.caccia(id="CB-2874", fonte="2024 · Regole di gioco · Tiri salvezza contro morte · pag. 28-29", zona="regola:2024/generali",
                    voce="regola", copre=["carta:2024/general.md#Tiri salvezza contro morte / Death Saving Throws (pag. 28-29)",
                                          "POST /characters/{char_id}/death_saves/roll"])
async def test_tiri_contro_morte_1_naturale_due_fallimenti_20_naturale_un_pf(client):
    cid = await _pg(client, "fighter", 3)
    await _pf(client, cid, 20, 0)
    uno = (await client.post(f"/characters/{cid}/death_saves/roll", json={"die": 1})).json()
    assert (uno["failures"], uno["successes"], uno["current_hp"]) == (2, 0, 0), uno
    venti = (await client.post(f"/characters/{cid}/death_saves/roll", json={"die": 20})).json()
    assert (venti["current_hp"], venti["failures"], venti["successes"], venti["revived"]) == (1, 0, 0, True), venti


@pytest.mark.caccia(id="CB-2875", fonte="2024 · Regole di gioco · Resistenza e Vulnerabilità, Immunità · pag. 28", zona="regola:2024/generali",
                    voce="regola", copre=["carta:2024/general.md#Resistenza e Vulnerabilità / Resistance and Vulnerability (pag. 28)",
                                          "carta:2024/general.md#Immunità / Immunity (pag. 28; glossario pag. 369)", "PATCH /characters/{char_id}/hp"])
@pytest.mark.parametrize("modificatori,persi", [
    ({"resistances": ["fire"], "vulnerabilities": ["fire"]}, 22), ({"resistances": ["fire"]}, 11),
    ({"vulnerabilities": ["fire"]}, 46), ({"immunities": ["fire"], "vulnerabilities": ["fire"]}, 0)])
async def test_prima_la_resistenza_poi_la_vulnerabilita_per_difetto(client, modificatori, persi):
    cid = await _pg(client, "fighter", 3)
    await _pf(client, cid, 100, 100)
    assert (await client.patch(f"/characters/{cid}", json={"damage_modifiers": modificatori})).status_code == 200
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 23, "damage_type": "fire"})
    assert r.status_code == 200, r.text
    assert 100 - r.json()["current_hit_points"] == persi


@pytest.mark.caccia(id="CB-2876", fonte="2024 · Regole di gioco · Scendere a 0 PF, Danno Massiccio · pag. 28", zona="regola:2024/generali",
                    voce="limiti", copre=["carta:2024/general.md#Scendere a 0 punti ferita / Dropping to 0 Hit Points (pag. 28)",
                                          "PATCH /characters/{char_id}/hp"])
@pytest.mark.parametrize("danno,morto", [(14, False), (15, True)])
async def test_danno_massiccio_alla_soglia_dei_pf_massimi(client, danno, morto):
    cid = await _pg(client, "fighter", 3)
    await _pf(client, cid, 10, 5)
    scheda = (await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": danno})).json()
    assert (scheda["current_hit_points"], scheda["is_dead"]) == (0, morto), scheda.get("is_dead")
