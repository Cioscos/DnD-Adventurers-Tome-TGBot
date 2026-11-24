"""Controlli della zona flusso:caratteristiche-tiri."""
import pytest


async def _pg(client) -> int:
    return (await client.post("/characters", json={"name": "P"})).json()["id"]


@pytest.mark.caccia(id="CB-014", fonte="invariante: le caratteristiche sono sei", zona="flusso:caratteristiche-tiri",
                    voce="limiti", copre=["PATCH /characters/{char_id}/ability_scores/{ability_name}"])
async def test_caratteristica_inventata_rifiutata(client):
    cid = await _pg(client)
    assert (await client.patch(f"/characters/{cid}/ability_scores/luck", json={"value": 12})).status_code == 422
    assert (await client.get(f"/characters/{cid}")).status_code == 200
    assert (await client.patch(f"/characters/{cid}/ability_scores/Strength", json={"value": 12})).status_code == 200


@pytest.mark.caccia(id="CB-023", fonte="invariante: le caratteristiche sono sei", zona="flusso:caratteristiche-tiri",
                    voce="limiti", copre=["POST /characters/import"])
async def test_caratteristica_inventata_rifiutata_nell_import(client):
    dati = (await client.get(f"/characters/{await _pg(client)}/export")).json()
    dati["ability_scores"].append({"name": "luck", "value": 12})
    assert (await client.post("/characters/import", json=dati)).status_code == 422


@pytest.mark.caccia(id="CB-017", fonte="invariante: abilità e tiri salvezza sono un elenco chiuso", zona="flusso:caratteristiche-tiri",
                    voce="limiti", copre=["PATCH /characters/{char_id}/skills", "PATCH /characters/{char_id}/saving_throws"])
async def test_abilita_e_salvezze_inventate_rifiutate(client):
    cid = await _pg(client)
    for corpo in ({"banana": True}, {"athletics": "wizard"}, {"athletics": 5}):
        assert (await client.patch(f"/characters/{cid}/skills", json={"skills": corpo})).status_code == 422
    r = await client.patch(f"/characters/{cid}/saving_throws", json={"saving_throws": {"luck": True}})
    assert r.status_code == 422
    for valore in (True, "expert", False, None):
        assert (await client.patch(f"/characters/{cid}/skills", json={"skills": {"athletics": valore}})).status_code == 200
    r = await client.patch(f"/characters/{cid}/saving_throws", json={"saving_throws": {"wisdom": True}})
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# Controlli aggiunti dal cacciatore della zona (CB-237 e seguenti)
# ---------------------------------------------------------------------------
ABILITA = ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")


async def _scheda(client, edizione="2014", classe=None, livello=1, punteggi=None, dado_vita=8) -> int:
    corpo = {"name": "P", "rules_edition": edizione}
    if punteggi:
        corpo["ability_scores"] = punteggi
    if classe:
        corpo["initial_class"] = {"class_name": classe, "level": livello, "hit_die": dado_vita}
    r = await client.post("/characters", json=corpo)
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _leggi(client, cid) -> dict:
    return (await client.get(f"/characters/{cid}")).json()


async def _tira(client, cid, percorso, **corpo) -> dict:
    r = await client.post(f"/characters/{cid}/{percorso}", json=corpo)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.caccia(id="CB-237", fonte="schema SkillsUpdate: null/false nessuna, true competente, expert Maestria", zona="flusso:caratteristiche-tiri",
                    voce="contratto", copre=["PATCH /characters/{char_id}/skills", "POST /characters/{char_id}/skills/{skill_name}/roll"])
async def test_valore_proficient_accettato_da_la_competenza(client):
    cid = await _scheda(client, punteggi={"strength": 14})
    r = await client.patch(f"/characters/{cid}/skills", json={"skills": {"athletics": "proficient"}})
    if r.status_code == 200:  # se il valore si accetta, deve valere come competenza (+2 mod, +2 competenza)
        assert (await _tira(client, cid, "skills/athletics/roll", die=10))["bonus"] == 4
    else:
        assert r.status_code == 422


@pytest.mark.caccia(id="CB-238", fonte="2014 · Caratteristiche · Costituzione · pag. 177", zona="flusso:caratteristiche-tiri",
                    voce="limiti", copre=["PATCH /characters/{char_id}/ability_scores/{ability_name}", "route:/char/:id/stats"])
async def test_costituzione_a_1_e_di_nuovo_a_10_restituisce_i_pf(client):
    cid = await _scheda(client, "2014", "wizard", 4, dado_vita=6)
    prima = (await _leggi(client, cid))["hit_points"]
    for valore in (1, 10):
        await client.patch(f"/characters/{cid}/ability_scores/constitution", json={"value": valore})
    pg = await _leggi(client, cid)
    assert (pg["hit_points"], pg["current_hit_points"]) == (prima, prima)


@pytest.mark.caccia(id="CB-239", fonte="2014 · Caratteristiche · Costituzione · pag. 177", zona="flusso:caratteristiche-tiri",
                    voce="limiti", copre=["PATCH /characters/{char_id}/ability_scores/{ability_name}"])
async def test_costituzione_abbassata_da_i_pf_di_chi_ha_sempre_avuto_quel_valore(client):
    nato = await _scheda(client, "2014", "wizard", 4, {"constitution": 3}, dado_vita=6)
    cambiato = await _scheda(client, "2014", "wizard", 4, dado_vita=6)
    await client.patch(f"/characters/{cambiato}/ability_scores/constitution", json={"value": 3})
    assert (await _leggi(client, cambiato))["hit_points"] == (await _leggi(client, nato))["hit_points"]


def _totale_salvezza_scheda(pg: dict, abilita: str) -> int:
    """Lo stesso conto di SavingThrows.tsx: modificatore + competenza + homebrew + oggetti + regole."""
    punteggio = next(s for s in pg["ability_scores"] if s["name"] == abilita)
    return (punteggio["modifier"] + (pg["proficiency_bonus"] if pg["saving_throws"].get(abilita) else 0)
            + pg["saves_homebrew_modifiers"].get(abilita, 0) + pg["saves_items_modifiers"].get(abilita, 0)
            + pg["computed"]["save_flat"].get(abilita, 0))


@pytest.mark.caccia(id="CB-240", fonte="2014 · Druido · Forma Selvatica · pag. 66 / 2024 · Druido · Regole della Forma Selvatica · pag. 81",
                    zona="flusso:caratteristiche-tiri", voce="interazione",
                    copre=["POST /characters/{char_id}/saving_throws/{ability}/roll", "route:/char/:id/saves"])
@pytest.mark.parametrize("edizione", ["2014", "2024"])
async def test_totale_salvezza_mostrato_segue_la_forma_selvatica(client, edizione):
    cid = await _scheda(client, edizione, "druid", 4, {"strength": 8, "dexterity": 10, "constitution": 12})
    forma = (await client.post(f"/characters/{cid}/companions", json={
        "kind": "wild_shape", "name": "Orso", "max_hp": 34,
        "statblock": {"abilities": {"str": 19, "dex": 10, "con": 16}}})).json()["id"]
    assert (await client.post(f"/characters/{cid}/companions/{forma}/activate", json={"force": True})).status_code == 200
    pg = await _leggi(client, cid)
    tiro = await _tira(client, cid, "saving_throws/strength/roll", die=10)
    assert tiro["bonus"] == 4  # modificatore della bestia (+4), il più alto fra druido (-1) e bestia
    assert _totale_salvezza_scheda(pg, "strength") == tiro["bonus"]


@pytest.mark.caccia(id="CB-241", fonte="2014 · Indebolimento · pag. 291 / 2024 · Exhaustion · pag. 366", zona="flusso:caratteristiche-tiri",
                    voce="edizioni", copre=["POST /characters/{char_id}/skills/{skill_name}/roll", "POST /characters/{char_id}/saving_throws/{ability}/roll",
                                            "POST /characters/{char_id}/ability_checks/{ability}/roll"])
@pytest.mark.parametrize("edizione", ["2014", "2024"])
async def test_indebolimento_su_prove_e_salvezze_per_edizione(client, edizione):
    cid = await _scheda(client, edizione, punteggi={"strength": 14})
    for livello in (1, 3, 5):
        await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"exhaustion": livello}})
        prova = await _tira(client, cid, "skills/athletics/roll", die=10)
        carat = await _tira(client, cid, "ability_checks/strength/roll", die=10)
        salv = await _tira(client, cid, "saving_throws/strength/roll", die=10)
        if edizione == "2014":
            assert (prova["mode"], carat["mode"], salv["mode"]) == ("disadvantage", "disadvantage", "disadvantage" if livello >= 3 else "normal")
            assert (prova["bonus"], salv["bonus"]) == (2, 2)
        else:
            assert (prova["mode"], carat["mode"], salv["mode"]) == ("normal",) * 3
            assert (prova["bonus"], carat["bonus"], salv["bonus"]) == (2 - 2 * livello,) * 3
    assert (await _leggi(client, cid))["passives"]["perception"] == (5 if edizione == "2014" else 0)


@pytest.mark.caccia(id="CB-242", fonte="2014 · Caratteristiche · pag. 173 (modificatore = (punteggio - 10) / 2 per difetto)", zona="flusso:caratteristiche-tiri",
                    voce="limiti", copre=["PATCH /characters/{char_id}/ability_scores/{ability_name}"])
async def test_modificatore_ai_limiti_del_punteggio(client):
    cid = await _scheda(client)
    attesi = {1: -5, 3: -4, 8: -1, 9: -1, 10: 0, 11: 0, 12: 1, 29: 9, 30: 10}
    for valore, mod in attesi.items():
        r = await client.patch(f"/characters/{cid}/ability_scores/strength", json={"value": valore})
        assert next(s for s in r.json()["ability_scores"] if s["name"] == "strength")["modifier"] == mod, valore
    for fuori in (0, 31, -1):
        assert (await client.patch(f"/characters/{cid}/ability_scores/strength", json={"value": fuori})).status_code == 400
    assert next(s for s in (await _leggi(client, cid))["ability_scores"] if s["name"] == "strength")["value"] == 30


@pytest.mark.caccia(id="CB-243", fonte="2014 · Ladro · Dote Affidabile · pag. 78 / 2024 · Ladro · Dote Affidabile · pag. 131", zona="flusso:caratteristiche-tiri",
                    voce="regola", copre=["POST /characters/{char_id}/skills/{skill_name}/roll", "POST /characters/{char_id}/ability_checks/{ability}/roll"])
@pytest.mark.parametrize("edizione, livello", [("2014", 11), ("2014", 10), ("2024", 7), ("2024", 6)])
async def test_dote_affidabile_solo_dal_livello_e_su_prove_competenti(client, edizione, livello):
    cid = await _scheda(client, edizione, "rogue", livello)
    await client.patch(f"/characters/{cid}/skills", json={"skills": {"stealth": True, "perception": "expert"}})
    attivo = (edizione, livello) in (("2014", 11), ("2024", 7))
    for abilita in ("stealth", "perception"):
        assert (await _tira(client, cid, f"skills/{abilita}/roll", die=3))["die"] == (10 if attivo else 3)
    assert (await _tira(client, cid, "skills/history/roll", die=3))["die"] == 3
    assert (await _tira(client, cid, "ability_checks/dexterity/roll", die=3))["die"] == 3
    assert (await _tira(client, cid, "skills/stealth/roll", mode="advantage", dice=[3, 4]))["die"] == (10 if attivo else 4)


@pytest.mark.caccia(id="CB-244", fonte="2014 · Bardo · Factotum · pag. 54 / 2024 · Bardo · Factotum · pag. 60", zona="flusso:caratteristiche-tiri",
                    voce="edizioni", copre=["POST /characters/{char_id}/ability_checks/{ability}/roll", "POST /characters/{char_id}/skills/{skill_name}/roll",
                                            "POST /characters/{char_id}/saving_throws/{ability}/roll"])
@pytest.mark.parametrize("edizione", ["2014", "2024"])
async def test_factotum_per_edizione(client, edizione):
    cid = await _scheda(client, edizione, "bard", 2, {"dexterity": 14, "strength": 10})
    assert (await _leggi(client, cid))["jack_of_all_trades"] is True
    assert (await _tira(client, cid, "skills/athletics/roll", die=10))["bonus"] == 1  # mezza competenza, non competente
    assert (await _tira(client, cid, "ability_checks/strength/roll", die=10))["bonus"] == (1 if edizione == "2014" else 0)
    assert (await _tira(client, cid, "saving_throws/strength/roll", die=10))["bonus"] == 0  # i TS non ne beneficiano
    await client.patch(f"/characters/{cid}/skills", json={"skills": {"athletics": "expert"}})
    assert (await _tira(client, cid, "skills/athletics/roll", die=10))["bonus"] == 4  # competenza già inclusa: niente metà in più


@pytest.mark.caccia(id="CB-245", fonte="2014 · Strumenti · pag. 154 / 2024 · Strumenti · pag. 220", zona="flusso:caratteristiche-tiri",
                    voce="edizioni", copre=["POST /characters/{char_id}/tool_checks/{tool}/roll"])
@pytest.mark.parametrize("edizione", ["2014", "2024"])
async def test_prova_con_strumento_per_edizione(client, edizione):
    cid = await _scheda(client, edizione, punteggi={"dexterity": 14})
    url = f"/characters/{cid}/tool_checks/thieves_tools/roll"
    assert (await client.post(url, json={"ability": "dexterity", "die": 10})).status_code == 409  # senza competenza
    await client.patch(f"/characters/{cid}", json={"tool_proficiencies": {"thieves_tools": True}})
    assert (await _tira(client, cid, "tool_checks/thieves_tools/roll", ability="dexterity", die=10))["bonus"] == 4
    await client.patch(f"/characters/{cid}", json={"tool_proficiencies": {"thieves_tools": "expert"}})
    assert (await _tira(client, cid, "tool_checks/thieves_tools/roll", ability="dexterity", die=10))["bonus"] == 6
    await client.patch(f"/characters/{cid}/skills", json={"skills": {"sleight_of_hand": True}})
    r = await client.post(url, json={"ability": "dexterity", "skill": "sleight_of_hand", "mode": "advantage", "dice": [10, 3]})
    assert r.status_code == (200 if edizione == "2024" else 422)
    if edizione == "2024":
        assert (r.json()["mode"], r.json()["die"]) == ("advantage", 10)
    assert (await client.post(f"/characters/{cid}/tool_checks/non_esiste/roll", json={"ability": "dexterity"})).status_code == 404
    assert (await client.post(url, json={"ability": "luck"})).status_code == 400


@pytest.mark.caccia(id="CB-246", fonte="CLAUDE.md · Auth: ogni endpoint filtra per l'utente autenticato", zona="flusso:caratteristiche-tiri",
                    voce="permessi", copre=["PATCH /characters/{char_id}/skills", "PATCH /characters/{char_id}/saving_throws",
                                             "PATCH /characters/{char_id}/ability_scores/{ability_name}", "POST /characters/{char_id}/tool_checks/{tool}/roll"])
async def test_un_altro_utente_non_tira_ne_modifica(client, come_utente):
    cid = await _scheda(client, punteggi={"strength": 14})
    prima = await _leggi(client, cid)
    come_utente(9002)
    chiamate = [("post", "skills/athletics/roll", {"die": 5}), ("post", "saving_throws/strength/roll", {"die": 5}),
                ("post", "ability_checks/strength/roll", {"die": 5}), ("post", "tool_checks/thieves_tools/roll", {"ability": "dexterity"}),
                ("patch", "skills", {"skills": {"athletics": True}}), ("patch", "saving_throws", {"saving_throws": {"strength": True}}),
                ("patch", "ability_scores/strength", {"value": 20})]
    for metodo, percorso, corpo in chiamate:
        r = await getattr(client, metodo)(f"/characters/{cid}/{percorso}", json=corpo)
        assert r.status_code in (403, 404), (percorso, r.status_code)
    come_utente(1234)  # l'utente predefinito dei controlli
    dopo = await _leggi(client, cid)
    assert (dopo["skills"], dopo["saving_throws"], dopo["ability_scores"], dopo["rolls_history"]) == \
           (prima["skills"], prima["saving_throws"], prima["ability_scores"], prima["rolls_history"])


@pytest.mark.caccia(id="CB-247", fonte="invariante: una richiesta ripetuta non spende due volte l'Ispirazione", zona="flusso:caratteristiche-tiri",
                    voce="ripetizione", copre=["POST /characters/{char_id}/skills/{skill_name}/roll", "POST /characters/{char_id}/saving_throws/{ability}/roll",
                                               "POST /characters/{char_id}/ability_checks/{ability}/roll"])
@pytest.mark.parametrize("percorso", ["skills/athletics/roll", "saving_throws/strength/roll", "ability_checks/strength/roll"])
async def test_ritiro_con_ispirazione_una_sola_volta(client, percorso):
    import asyncio
    cid = await _scheda(client, "2024")
    await client.patch(f"/characters/{cid}/inspiration", json={"heroic_inspiration": True})
    risposte = await asyncio.gather(*[client.post(f"/characters/{cid}/{percorso}", json={"with_inspiration": True, "die": 7}) for _ in range(3)])
    assert sorted(r.status_code for r in risposte) == [200, 409, 409]
    assert (await _leggi(client, cid))["heroic_inspiration"] is False


@pytest.mark.caccia(id="CB-248", fonte="2014 · Ispirazione · prima del tiro / 2024 · Ispirazione Eroica · ritiro", zona="flusso:caratteristiche-tiri",
                    voce="edizioni", copre=["POST /characters/{char_id}/skills/{skill_name}/roll"])
async def test_ritiro_con_ispirazione_solo_nel_2024_e_senza_perdere_l_ispirazione_nel_2014(client):
    vecchio = await _scheda(client, "2014")
    await client.patch(f"/characters/{vecchio}/inspiration", json={"heroic_inspiration": True})
    r = await client.post(f"/characters/{vecchio}/skills/athletics/roll", json={"with_inspiration": True, "die": 7})
    assert r.status_code == 409
    assert (await _leggi(client, vecchio))["heroic_inspiration"] is True
    nuovo = await _scheda(client, "2024")
    assert (await client.post(f"/characters/{nuovo}/skills/athletics/roll", json={"with_inspiration": True, "die": 7})).status_code == 409


@pytest.mark.caccia(id="CB-249", fonte="invariante: un d20 ha 1-20 e il numero di dadi segue il modo", zona="flusso:caratteristiche-tiri",
                    voce="limiti", copre=["POST /characters/{char_id}/skills/{skill_name}/roll"])
async def test_dadi_fuori_dai_limiti_rifiutati_e_modo_rispettato(client):
    cid = await _scheda(client)
    url = f"/characters/{cid}/skills/athletics/roll"
    for corpo in ({"die": 0}, {"die": 21}, {"dice": [0]}, {"dice": [21]}, {"mode": "advantage", "dice": [5]},
                  {"mode": "advantage", "die": 5}, {"mode": "bogus"}):
        assert (await client.post(url, json=corpo)).status_code == 422, corpo
    assert (await client.post(f"/characters/{cid}/skills/inventata/roll", json={})).status_code == 400
    r = await client.post(url, json={"mode": "disadvantage", "dice": [3, 17]})
    assert (r.json()["die"], r.json()["total"]) == (3, 3)
    r = await client.post(url, json={"mode": "advantage", "dice": [3, 17]})
    assert r.json()["die"] == 17


@pytest.mark.caccia(id="CB-250", fonte="2014 · Condizioni · Paralizzato, Stordito, Privo di sensi, Pietrificato / 2024 · stesse condizioni", zona="flusso:caratteristiche-tiri",
                    voce="edizioni", copre=["POST /characters/{char_id}/saving_throws/{ability}/roll"])
@pytest.mark.parametrize("edizione", ["2014", "2024"])
async def test_fallimento_automatico_ai_ts_forza_e_destrezza(client, edizione):
    cid = await _scheda(client, edizione)
    for condizione in ("paralyzed", "stunned", "unconscious", "petrified"):
        await client.patch(f"/characters/{cid}/conditions", json={"conditions": {condizione: True}})
        esiti = {a: (await _tira(client, cid, f"saving_throws/{a}/roll", die=10))["auto_fail"] for a in ABILITA}
        assert esiti == {"strength": True, "dexterity": True, "constitution": False, "intelligence": False, "wisdom": False, "charisma": False}, condizione
        await client.patch(f"/characters/{cid}/conditions", json={"conditions": {condizione: False}})
    await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"restrained": True}})
    assert (await _tira(client, cid, "saving_throws/dexterity/roll", die=10))["mode"] == "disadvantage"
    assert (await _tira(client, cid, "saving_throws/strength/roll", die=10))["mode"] == "normal"


@pytest.mark.caccia(id="CB-251", fonte="2014 · Paladino · Aura di Protezione · pag. 98 / Monaco 14 · Anima di Diamante", zona="flusso:caratteristiche-tiri",
                    voce="regola", copre=["POST /characters/{char_id}/saving_throws/{ability}/roll", "route:/char/:id/saves"])
async def test_aura_di_protezione_minimo_1_e_totale_mostrato_uguale_al_tiro(client):
    cid = await _scheda(client, "2014", "paladin", 6, {"charisma": 8, "strength": 16, "wisdom": 12}, dado_vita=10)
    pg = await _leggi(client, cid)
    for abilita, atteso in (("strength", 4), ("charisma", 3), ("wisdom", 1 + 3 + 1), ("constitution", 1)):
        tiro = await _tira(client, cid, f"saving_throws/{abilita}/roll", die=10)
        assert tiro["bonus"] == atteso, abilita
        assert _totale_salvezza_scheda(pg, abilita) == atteso, abilita


@pytest.mark.caccia(id="CB-252", fonte="2014 · Oggetti magici · Guanti della Forza da Ogre / invariante: tolto l'oggetto tutto torna com'era", zona="flusso:caratteristiche-tiri",
                    voce="annullamento", copre=["POST /characters/{char_id}/items", "PATCH /characters/{char_id}/items/{item_id}", "POST /characters/{char_id}/ability_checks/{ability}/roll"])
async def test_oggetto_che_cambia_una_caratteristica_si_toglie_e_tutto_torna(client):
    cid = await _scheda(client, "2014", "fighter", 3, {"strength": 10, "constitution": 12}, dado_vita=10)
    prima = await _leggi(client, cid)
    guanti = {"ability_modifiers": [{"ability": "strength", "kind": "absolute", "value": 19}]}
    fascia = {"ability_modifiers": [{"ability": "constitution", "kind": "relative", "value": 4}]}
    sintonia = {**guanti, "requires_attunement": True}
    for meta, str_atteso, pf_atteso in ((guanti, 4, prima["hit_points"]), (fascia, 0, prima["hit_points"] + 6), (sintonia, 0, prima["hit_points"])):
        r = await client.post(f"/characters/{cid}/items", json={"name": "O", "item_metadata": meta, "is_equipped": True})
        iid = r.json()["items"][-1]["id"] if "items" in r.json() else r.json()["id"]
        assert (await _tira(client, cid, "ability_checks/strength/roll", die=10))["bonus"] == str_atteso
        assert (await _leggi(client, cid))["hit_points"] == pf_atteso
        await client.patch(f"/characters/{cid}/items/{iid}", json={"is_equipped": False})
        dopo = await _leggi(client, cid)
        assert (dopo["hit_points"], dopo["current_hit_points"]) == (prima["hit_points"], prima["current_hit_points"])
        assert (await _tira(client, cid, "ability_checks/strength/roll", die=10))["bonus"] == 0
        await client.delete(f"/characters/{cid}/items/{iid}")


@pytest.mark.caccia(id="CB-253", fonte="2014 · Bonus di competenza per livello · pag. 15", zona="flusso:caratteristiche-tiri",
                    voce="limiti", copre=["POST /characters/{char_id}/skills/{skill_name}/roll"])
@pytest.mark.parametrize("livello, bonus", [(1, 2), (4, 2), (5, 3), (8, 3), (9, 4), (12, 4), (13, 5), (16, 5), (17, 6), (20, 6)])
async def test_bonus_di_competenza_ai_livelli_soglia(client, livello, bonus):
    cid = await _scheda(client, "2014", "fighter", livello, dado_vita=10)
    await client.patch(f"/characters/{cid}/skills", json={"skills": {"athletics": "expert"}})
    pg = await _leggi(client, cid)
    assert pg["proficiency_bonus"] == bonus
    assert (await _tira(client, cid, "skills/athletics/roll", die=10))["bonus"] == 2 * bonus
    assert pg["skill_bonuses"]["athletics"] == 2 * bonus


@pytest.mark.caccia(id="CB-254", fonte="invariante: esportare e importare non cambia competenze né totali", zona="flusso:caratteristiche-tiri",
                    voce="persistenza", copre=["GET /characters/{char_id}/export", "POST /characters/import"])
async def test_export_import_conserva_competenze_e_totali(client):
    cid = await _scheda(client, "2014", "rogue", 5, {"strength": 13})
    await client.patch(f"/characters/{cid}/skills", json={"skills": {"stealth": "expert", "acrobatics": True}})
    await client.patch(f"/characters/{cid}/saving_throws", json={"saving_throws": {"wisdom": True}})
    await client.patch(f"/characters/{cid}", json={"tool_proficiencies": {"thieves_tools": "expert"}})
    prima = await _leggi(client, cid)
    nuovo = (await client.post("/characters/import", json=(await client.get(f"/characters/{cid}/export")).json())).json()["id"]
    dopo = await _leggi(client, nuovo)
    for chiave in ("skills", "saving_throws", "tool_proficiencies", "proficiency_bonus", "skill_bonuses", "passives"):
        assert dopo[chiave] == prima[chiave], chiave


@pytest.mark.caccia(id="CB-256", fonte="2014 · Capacità di carico = punteggio di Forza × 15 (general.md)", zona="flusso:caratteristiche-tiri",
                    voce="interazione", copre=["POST /characters/{char_id}/items"])
async def test_capacita_di_carico_segue_la_forza_data_da_un_oggetto(client):
    cid = await _scheda(client, "2014", punteggi={"strength": 10})
    assert (await _leggi(client, cid))["carry_capacity"] == 150
    meta = {"ability_modifiers": [{"ability": "strength", "kind": "absolute", "value": 19}]}
    await client.post(f"/characters/{cid}/items", json={"name": "Guanti", "item_metadata": meta, "is_equipped": True})
    assert (await _leggi(client, cid))["carry_capacity"] == 285


@pytest.mark.caccia(id="CB-257", fonte="invariante: un booleano JSON non è un numero", zona="flusso:caratteristiche-tiri",
                    voce="limiti", copre=["PATCH /characters/{char_id}/ability_scores/{ability_name}", "POST /characters/{char_id}/skills/{skill_name}/roll"])
async def test_booleano_non_e_un_numero(client):
    cid = await _scheda(client)
    r1 = await client.patch(f"/characters/{cid}/ability_scores/strength", json={"value": True})
    r2 = await client.post(f"/characters/{cid}/skills/athletics/roll", json={"dice": [True]})
    assert (r1.status_code, r2.status_code) == (422, 422)


@pytest.mark.caccia(id="CB-258", fonte="2014 · Bonus di competenza per livello · pag. 15; modificatore = (punteggio - 10) / 2 per difetto", zona="flusso:caratteristiche-tiri",
                    voce="normale", copre=["PATCH /characters/{char_id}/ability_scores/{ability_name}", "PATCH /characters/{char_id}/skills",
                                            "PATCH /characters/{char_id}/saving_throws", "route:/char/:id/stats", "route:/char/:id/skills"])
async def test_percorso_comune_punteggio_competenza_e_tiri(client):
    cid = await _scheda(client, "2014", "fighter", 5, dado_vita=10)  # competenza +3
    await client.patch(f"/characters/{cid}/ability_scores/strength", json={"value": 16})  # +3
    await client.patch(f"/characters/{cid}/ability_scores/dexterity", json={"value": 14})  # +2
    await client.patch(f"/characters/{cid}/skills", json={"skills": {"athletics": True}})
    await client.patch(f"/characters/{cid}/saving_throws", json={"saving_throws": {"dexterity": True}})
    prova = await _tira(client, cid, "skills/athletics/roll", die=10)
    salv = await _tira(client, cid, "saving_throws/dexterity/roll", die=12)
    assert (prova["bonus"], prova["total"]) == (6, 16)
    assert (salv["bonus"], salv["total"]) == (5, 17)
    pg = await _leggi(client, cid)
    assert pg["proficiency_bonus"] == 3
    assert pg["skill_bonuses"]["athletics"] == 6
    assert (pg["skills"]["athletics"], pg["saving_throws"]["dexterity"]) == (True, True)
    mods = {s["name"]: s["modifier"] for s in pg["ability_scores"]}
    assert (mods["strength"], mods["dexterity"]) == (3, 2)


# ---------------------------------------------------------------------------
# Secondo giro (CB-973 e seguenti): Furore, Atleta Straordinario, strumenti, passiva, combinazioni
# ---------------------------------------------------------------------------
async def _classe(client, edizione, classe, livello, sottoclasse=None, punteggi=None, dado_vita=10) -> int:
    corpo = {"name": "P", "rules_edition": edizione,
             "initial_class": {"class_name": classe, "level": livello, "hit_die": dado_vita, "subclass": sottoclasse}}
    if punteggi:
        corpo["ability_scores"] = punteggi
    r = await client.post("/characters", json=corpo)
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _ira(client, cid) -> None:
    r = await client.post(f"/characters/{cid}/features/barbarian.rage/use", json={})
    assert r.status_code == 200, r.text


@pytest.mark.caccia(id="CB-973", fonte="2014 · Barbaro · Ira · pag. 48 / 2024 · Barbaro · Ira · pag. 52", zona="flusso:caratteristiche-tiri",
                    voce="regola", copre=["POST /characters/{char_id}/features/{feature_key}/use", "POST /characters/{char_id}/ability_checks/{ability}/roll",
                                           "POST /characters/{char_id}/saving_throws/{ability}/roll", "POST /characters/{char_id}/skills/{skill_name}/roll"])
@pytest.mark.parametrize("edizione", ["2014", "2024"])
async def test_ira_da_vantaggio_solo_a_prove_e_ts_di_forza(client, edizione):
    cid = await _classe(client, edizione, "barbarian", 1, punteggi={"strength": 16, "dexterity": 14})
    assert (await _tira(client, cid, "ability_checks/strength/roll", die=10))["mode"] == "normal"
    await _ira(client, cid)
    modi = {
        "prova Forza": (await _tira(client, cid, "ability_checks/strength/roll", die=10))["mode"],
        "Atletica": (await _tira(client, cid, "skills/athletics/roll", die=10))["mode"],
        "TS Forza": (await _tira(client, cid, "saving_throws/strength/roll", die=10))["mode"],
        "prova Destrezza": (await _tira(client, cid, "ability_checks/dexterity/roll", die=10))["mode"],
        "Acrobazia": (await _tira(client, cid, "skills/acrobatics/roll", die=10))["mode"],
        "TS Destrezza": (await _tira(client, cid, "saving_throws/dexterity/roll", die=10))["mode"],
    }
    assert modi == {"prova Forza": "advantage", "Atletica": "advantage", "TS Forza": "advantage",
                    "prova Destrezza": "normal", "Acrobazia": "normal", "TS Destrezza": "normal"}
    await client.delete(f"/characters/{cid}/active-states/rage")
    assert (await _tira(client, cid, "ability_checks/strength/roll", die=10))["mode"] == "normal"


@pytest.mark.caccia(id="CB-974", fonte="2014 · Vantaggio e svantaggio · pag. 173 (si annullano, comunque siano più fonti) / 2024 · stesso", zona="flusso:caratteristiche-tiri",
                    voce="interazione", copre=["POST /characters/{char_id}/ability_checks/{ability}/roll", "POST /characters/{char_id}/saving_throws/{ability}/roll"])
@pytest.mark.parametrize("edizione", ["2014", "2024"])
async def test_due_vantaggi_e_uno_svantaggio_si_annullano(client, edizione):
    cid = await _classe(client, edizione, "barbarian", 1, punteggi={"strength": 16})
    await _ira(client, cid)  # vantaggio dal Furore
    await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"poisoned": True}})  # svantaggio alle prove
    r = await _tira(client, cid, "ability_checks/strength/roll", mode="advantage", dice=[4, 15])  # secondo vantaggio, dal giocatore
    assert r["mode"] == "normal" and len(r["dice"]) == 1
    r = await _tira(client, cid, "ability_checks/strength/roll", die=9)  # Furore contro Avvelenato
    assert r["mode"] == "normal"
    r = await _tira(client, cid, "saving_throws/strength/roll", die=9)  # Avvelenato non tocca i TS
    assert r["mode"] == "advantage"
    r = await _tira(client, cid, "ability_checks/strength/roll", mode="disadvantage", dice=[4, 15])  # due svantaggi, un vantaggio
    assert r["mode"] == "normal"


@pytest.mark.caccia(id="CB-975", fonte="2014 · Guerriero · Campione · Atleta Straordinario · pag. 72", zona="flusso:caratteristiche-tiri",
                    voce="regola", copre=["POST /characters/{char_id}/skills/{skill_name}/roll", "POST /characters/{char_id}/ability_checks/{ability}/roll",
                                           "POST /characters/{char_id}/tool_checks/{tool}/roll"])
@pytest.mark.parametrize("livello, extra", [(7, 2), (6, 0)])
async def test_atleta_straordinario_2014_mezza_competenza_per_eccesso(client, livello, extra):
    cid = await _classe(client, "2014", "fighter", livello, "champion")  # competenza +3 dal 5 (mezza per eccesso = 2)
    await client.patch(f"/characters/{cid}/skills", json={"skills": {"stealth": True}})
    assert (await _tira(client, cid, "skills/athletics/roll", die=10))["bonus"] == extra
    assert (await _tira(client, cid, "skills/acrobatics/roll", die=10))["bonus"] == extra
    assert (await _tira(client, cid, "ability_checks/constitution/roll", die=10))["bonus"] == extra
    assert (await _tira(client, cid, "ability_checks/strength/roll", die=10))["bonus"] == extra
    assert (await _tira(client, cid, "skills/stealth/roll", die=10))["bonus"] == 3  # già competente: niente in più
    assert (await _tira(client, cid, "ability_checks/intelligence/roll", die=10))["bonus"] == 0
    assert (await _tira(client, cid, "skills/history/roll", die=10))["bonus"] == 0
    assert (await _tira(client, cid, "saving_throws/dexterity/roll", die=10))["bonus"] == 0
    assert (await _leggi(client, cid))["skill_bonuses"]["athletics"] == extra  # la scheda mostra ciò che si tira


@pytest.mark.caccia(id="CB-976", fonte="2024 · Guerriero · Campione · Atleta Straordinario · pag. 111", zona="flusso:caratteristiche-tiri",
                    voce="edizioni", copre=["POST /characters/{char_id}/skills/{skill_name}/roll", "POST /characters/{char_id}/ability_checks/{ability}/roll"])
@pytest.mark.parametrize("livello, atteso", [(3, "advantage"), (2, "normal")])
async def test_atleta_straordinario_2024_vantaggio_ad_atletica(client, livello, atteso):
    cid = await _classe(client, "2024", "fighter", livello, "champion")
    assert (await _tira(client, cid, "skills/athletics/roll", die=10))["mode"] == atteso
    assert (await _tira(client, cid, "skills/acrobatics/roll", die=10))["mode"] == "normal"
    assert (await _tira(client, cid, "ability_checks/strength/roll", die=10))["mode"] == "normal"
    assert (await _tira(client, cid, "skills/athletics/roll", die=10))["bonus"] == 0  # nel 2024 niente mezza competenza


@pytest.mark.caccia(id="CB-977", fonte="2014 · Ladro · Dote Affidabile · pag. 78 / 2024 · Ladro · Dote Affidabile · pag. 131", zona="flusso:caratteristiche-tiri",
                    voce="regola", copre=["POST /characters/{char_id}/tool_checks/{tool}/roll"])
@pytest.mark.parametrize("edizione, livello", [("2014", 11), ("2014", 10), ("2024", 7), ("2024", 6)])
async def test_dote_affidabile_vale_per_gli_strumenti(client, edizione, livello):
    cid = await _classe(client, edizione, "rogue", livello, dado_vita=8)
    await client.patch(f"/characters/{cid}", json={"tool_proficiencies": {"thieves_tools": True}})
    attivo = (edizione, livello) in (("2014", 11), ("2024", 7))
    r = await _tira(client, cid, "tool_checks/thieves_tools/roll", ability="dexterity", die=3)
    assert r["die"] == (10 if attivo else 3)
    r = await _tira(client, cid, "tool_checks/thieves_tools/roll", ability="dexterity", die=14)
    assert r["die"] == 14


@pytest.mark.caccia(id="CB-978", fonte="2014 · Barbaro · Ira · pag. 48 / Avvelenato · pag. 290", zona="flusso:caratteristiche-tiri",
                    voce="interazione", copre=["POST /characters/{char_id}/tool_checks/{tool}/roll"])
@pytest.mark.parametrize("edizione", ["2014", "2024"])
async def test_prova_con_strumento_riceve_vantaggi_e_svantaggi_automatici(client, edizione):
    cid = await _classe(client, edizione, "barbarian", 1, punteggi={"strength": 16, "dexterity": 14})
    await client.patch(f"/characters/{cid}", json={"tool_proficiencies": {"smiths_tools": True}})
    assert (await _tira(client, cid, "tool_checks/smiths_tools/roll", ability="strength", die=10))["mode"] == "normal"
    await _ira(client, cid)
    assert (await _tira(client, cid, "tool_checks/smiths_tools/roll", ability="strength", die=10))["mode"] == "advantage"
    assert (await _tira(client, cid, "tool_checks/smiths_tools/roll", ability="dexterity", die=10))["mode"] == "normal"
    await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"poisoned": True}})
    assert (await _tira(client, cid, "tool_checks/smiths_tools/roll", ability="strength", die=10))["mode"] == "normal"
    assert (await _tira(client, cid, "tool_checks/smiths_tools/roll", ability="dexterity", die=10))["mode"] == "disadvantage"


@pytest.mark.caccia(id="CB-979", fonte="2024 · Strumenti · pag. 220 (abilità competente insieme allo strumento: vantaggio) / Avvelenato", zona="flusso:caratteristiche-tiri",
                    voce="interazione", copre=["POST /characters/{char_id}/tool_checks/{tool}/roll"])
async def test_strumento_con_abilita_e_avvelenato_si_annullano(client):
    cid = await _scheda(client, "2024", punteggi={"dexterity": 14})
    await client.patch(f"/characters/{cid}", json={"tool_proficiencies": {"thieves_tools": True}})
    await client.patch(f"/characters/{cid}/skills", json={"skills": {"sleight_of_hand": True}})
    await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"poisoned": True}})
    r = await _tira(client, cid, "tool_checks/thieves_tools/roll", ability="dexterity", skill="sleight_of_hand", die=10)
    assert r["mode"] == "normal"
    r = await _tira(client, cid, "tool_checks/thieves_tools/roll", ability="dexterity", skill="sleight_of_hand", mode="advantage", dice=[2, 9])
    assert r["mode"] == "normal"


@pytest.mark.caccia(id="CB-980", fonte="invariante: una richiesta ripetuta non spende due volte l'Ispirazione", zona="flusso:caratteristiche-tiri",
                    voce="ripetizione", copre=["POST /characters/{char_id}/tool_checks/{tool}/roll"])
async def test_ritiro_con_ispirazione_su_prova_con_strumento_una_sola_volta(client):
    import asyncio
    cid = await _scheda(client, "2024")
    await client.patch(f"/characters/{cid}", json={"tool_proficiencies": {"thieves_tools": True}})
    await client.patch(f"/characters/{cid}/inspiration", json={"heroic_inspiration": True})
    corpo = {"ability": "dexterity", "with_inspiration": True, "die": 7}
    risposte = await asyncio.gather(*[client.post(f"/characters/{cid}/tool_checks/thieves_tools/roll", json=corpo) for _ in range(3)])
    assert sorted(r.status_code for r in risposte) == [200, 409, 409]
    assert (await _leggi(client, cid))["heroic_inspiration"] is False


@pytest.mark.caccia(id="CB-981", fonte="2014 · Barbaro · Potenza Indomabile · pag. 49 / 2024 · Barbaro · Potenza Indomabile (prove e TS di Forza)", zona="flusso:caratteristiche-tiri",
                    voce="edizioni", copre=["POST /characters/{char_id}/ability_checks/{ability}/roll", "POST /characters/{char_id}/saving_throws/{ability}/roll",
                                           "POST /characters/{char_id}/tool_checks/{tool}/roll"])
@pytest.mark.parametrize("edizione", ["2014", "2024"])
async def test_potenza_indomabile_totale_minimo_pari_alla_forza(client, edizione):
    cid = await _classe(client, edizione, "barbarian", 18, punteggi={"strength": 20, "dexterity": 10})
    await client.patch(f"/characters/{cid}", json={"tool_proficiencies": {"smiths_tools": True}})
    assert (await _tira(client, cid, "ability_checks/strength/roll", die=1))["total"] == 20
    assert (await _tira(client, cid, "skills/athletics/roll", die=1))["total"] == 20
    assert (await _tira(client, cid, "tool_checks/smiths_tools/roll", ability="strength", die=1))["total"] == 20
    assert (await _tira(client, cid, "ability_checks/dexterity/roll", die=1))["total"] == 1
    assert (await _tira(client, cid, "saving_throws/strength/roll", die=1))["total"] == (1 + 5 + 6 if edizione == "2014" else 20)
    assert (await _tira(client, cid, "ability_checks/strength/roll", die=19))["total"] == 24


@pytest.mark.caccia(id="CB-982", fonte="2014 · Prove Passive · pag. 175 (10 + modificatori; vantaggio +5, svantaggio -5) / 2024 · Passive Checks", zona="flusso:caratteristiche-tiri",
                    voce="regola", copre=["GET /characters/{char_id}", "route:/char/:id/skills"])
@pytest.mark.parametrize("edizione", ["2014", "2024"])
async def test_percezione_passiva_con_competenza_maestria_e_factotum(client, edizione):
    cid = await _classe(client, edizione, "bard", 5, punteggi={"wisdom": 14}, dado_vita=8)  # competenza +3, Saggezza +2
    assert (await _leggi(client, cid))["passives"]["perception"] == 10 + 2 + 1  # Factotum: metà competenza per difetto
    await client.patch(f"/characters/{cid}/skills", json={"skills": {"perception": True}})
    assert (await _leggi(client, cid))["passives"]["perception"] == 15
    await client.patch(f"/characters/{cid}/skills", json={"skills": {"perception": "expert"}})
    assert (await _leggi(client, cid))["passives"]["perception"] == 18
    await client.patch(f"/characters/{cid}/ability_scores/wisdom", json={"value": 1})
    assert (await _leggi(client, cid))["passives"]["perception"] == 10 - 5 + 6
    await client.patch(f"/characters/{cid}/ability_scores/wisdom", json={"value": 30})
    assert (await _leggi(client, cid))["passives"]["perception"] == 10 + 10 + 6


@pytest.mark.caccia(id="CB-983", fonte="2014 · Prove Passive · pag. 175 / Avvelenato · pag. 290 (svantaggio alle prove di caratteristica)", zona="flusso:caratteristiche-tiri",
                    voce="interazione", copre=["GET /characters/{char_id}", "PATCH /characters/{char_id}/conditions"])
async def test_passiva_scende_di_5_con_svantaggio_da_avvelenato_e_torna_dopo(client):
    cid = await _scheda(client, "2014", punteggi={"wisdom": 14})
    await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"poisoned": True}})
    pg = await _leggi(client, cid)
    assert (pg["passives"]["perception"], pg["passives"]["insight"]) == (7, 7)
    await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"poisoned": False}})
    assert (await _leggi(client, cid))["passives"]["perception"] == 12


@pytest.mark.caccia(id="CB-984", fonte="2014 · Oggetti magici · Guanti della Forza da Ogre (se la Forza è già 19 o più non succede nulla)", zona="flusso:caratteristiche-tiri",
                    voce="limiti", copre=["POST /characters/{char_id}/items", "route:/char/:id/stats"])
async def test_oggetto_assoluto_non_abbassa_un_punteggio_piu_alto_e_vince_il_maggiore(client):
    cid = await _scheda(client, "2014")
    await client.patch(f"/characters/{cid}/ability_scores/strength", json={"value": 22})
    def guanti(v): return {"ability_modifiers": [{"ability": "strength", "kind": "absolute", "value": v}]}
    await client.post(f"/characters/{cid}/items", json={"name": "G19", "item_metadata": guanti(19), "is_equipped": True})
    assert (await _tira(client, cid, "ability_checks/strength/roll", die=10))["bonus"] == 6
    assert (await _leggi(client, cid))["carry_capacity"] == 22 * 15
    await client.post(f"/characters/{cid}/items", json={"name": "G25", "item_metadata": guanti(25), "is_equipped": True})
    assert (await _tira(client, cid, "ability_checks/strength/roll", die=10))["bonus"] == 7


@pytest.mark.caccia(id="CB-986", fonte="2014 · Riposo lungo · pag. 186 / Ira · pag. 48 (dura 1 minuto)", zona="flusso:caratteristiche-tiri",
                    voce="persistenza", copre=["POST /characters/{char_id}/rest", "POST /characters/{char_id}/ability_checks/{ability}/roll"])
@pytest.mark.parametrize("edizione", ["2014", "2024"])
async def test_dopo_un_riposo_lungo_il_vantaggio_del_furore_non_c_e_piu(client, edizione):
    cid = await _classe(client, edizione, "barbarian", 3, punteggi={"strength": 16})
    await _ira(client, cid)
    assert (await _tira(client, cid, "ability_checks/strength/roll", die=10))["mode"] == "advantage"
    r = await client.post(f"/characters/{cid}/rest", json={"rest_type": "long", "confirm_early": True})
    assert r.status_code == 200, r.text
    assert (await _tira(client, cid, "ability_checks/strength/roll", die=10))["mode"] == "normal"


@pytest.mark.caccia(id="CB-987", fonte="invariante: togliere una competenza la toglie davvero", zona="flusso:caratteristiche-tiri",
                    voce="annullamento", copre=["PATCH /characters/{char_id}", "POST /characters/{char_id}/tool_checks/{tool}/roll"])
async def test_togliere_la_competenza_nello_strumento_rifiuta_la_prova_e_abbassa_la_maestria(client):
    cid = await _scheda(client, "2014", punteggi={"dexterity": 14})
    url = f"/characters/{cid}/tool_checks/thieves_tools/roll"
    await client.patch(f"/characters/{cid}", json={"tool_proficiencies": {"thieves_tools": "expert"}})
    assert (await _tira(client, cid, "tool_checks/thieves_tools/roll", ability="dexterity", die=10))["bonus"] == 6
    await client.patch(f"/characters/{cid}", json={"tool_proficiencies": {"thieves_tools": True}})
    assert (await _tira(client, cid, "tool_checks/thieves_tools/roll", ability="dexterity", die=10))["bonus"] == 4
    await client.patch(f"/characters/{cid}", json={"tool_proficiencies": {}})
    assert (await client.post(url, json={"ability": "dexterity", "die": 10})).status_code == 409
    assert (await _leggi(client, cid))["tool_proficiencies"].get("thieves_tools") in (None, False)


@pytest.mark.caccia(id="CB-988", fonte="2014 · Indebolimento · pag. 291 / 2024 · Exhaustion · pag. 366", zona="flusso:caratteristiche-tiri",
                    voce="edizioni", copre=["POST /characters/{char_id}/tool_checks/{tool}/roll"])
@pytest.mark.parametrize("edizione", ["2014", "2024"])
async def test_spossatezza_sulla_prova_con_strumento_per_edizione(client, edizione):
    cid = await _scheda(client, edizione, punteggi={"dexterity": 14})
    await client.patch(f"/characters/{cid}", json={"tool_proficiencies": {"thieves_tools": True}})
    await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"exhaustion": 2}})
    r = await _tira(client, cid, "tool_checks/thieves_tools/roll", ability="dexterity", die=10)
    assert (r["mode"], r["bonus"]) == (("disadvantage", 4) if edizione == "2014" else ("normal", 0))


@pytest.mark.caccia(id="CB-989", fonte="2014 · Barbaro · Ira · pag. 48 (benefici solo senza armatura pesante) / Armature · pag. 144", zona="flusso:caratteristiche-tiri",
                    voce="interazione", copre=["POST /characters/{char_id}/items", "PATCH /characters/{char_id}/items/{item_id}", "POST /characters/{char_id}/ability_checks/{ability}/roll"])
async def test_armatura_pesante_toglie_e_rimette_il_vantaggio_del_furore(client):
    cid = await _classe(client, "2014", "barbarian", 1, punteggi={"strength": 16})
    await _ira(client, cid)
    r = await client.post(f"/characters/{cid}/items", json={"name": "Piastre", "item_type": "armor", "is_equipped": True,
                                                              "equipment_slot": "body", "item_metadata": {"armor_type": "heavy", "ac_value": 18}})
    assert r.status_code in (200, 201), r.text
    iid = next(i["id"] for i in (await _leggi(client, cid))["items"] if i["name"] == "Piastre")
    assert (await _tira(client, cid, "ability_checks/strength/roll", die=10))["mode"] == "disadvantage"  # senza competenza: svantaggio a Forza e Destrezza
    await client.patch(f"/characters/{cid}/items/{iid}", json={"is_equipped": False})
    assert (await _tira(client, cid, "ability_checks/strength/roll", die=10))["mode"] == "advantage"
    await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"exhaustion": 1}})  # 2014: svantaggio alle prove
    assert (await _tira(client, cid, "ability_checks/strength/roll", die=10))["mode"] == "normal"
    assert (await _tira(client, cid, "saving_throws/strength/roll", die=10))["mode"] == "advantage"


@pytest.mark.caccia(id="CB-990", fonte="CLAUDE.md · contratto: AbilityScores.tsx legge base_value (valore base) e value (effettivo con gli oggetti)", zona="flusso:caratteristiche-tiri",
                    voce="contratto", copre=["PATCH /characters/{char_id}/ability_scores/{ability_name}", "GET /characters/{char_id}", "route:/char/:id/stats"])
async def test_valore_base_ed_effettivo_della_caratteristica_con_un_oggetto(client):
    cid = await _scheda(client, "2014", punteggi={"strength": 12})
    meta = {"ability_modifiers": [{"ability": "strength", "kind": "relative", "value": 2}]}
    await client.post(f"/characters/{cid}/items", json={"name": "Cintura", "item_metadata": meta, "is_equipped": True})
    risposta = await client.patch(f"/characters/{cid}/ability_scores/strength", json={"value": 13})
    for pg in (risposta.json(), await _leggi(client, cid)):
        forza = next(s for s in pg["ability_scores"] if s["name"] == "strength")
        assert (forza["base_value"], forza["value"], forza["modifier"]) == (13, 15, 2)
        assert pg["carry_capacity"] == 15 * 15
    destrezza = next(s for s in (await _leggi(client, cid))["ability_scores"] if s["name"] == "dexterity")
    assert (destrezza["base_value"], destrezza["value"]) == (10, 10)


@pytest.mark.caccia(id="CB-991", fonte="decisione D-013: il punteggio effettivo non scende sotto 1, il modificatore non sotto -5; invariante: la capacità di carico non è negativa",
                    zona="flusso:caratteristiche-tiri", voce="limiti", copre=["POST /characters/{char_id}/items", "GET /characters/{char_id}", "POST /characters/{char_id}/ability_checks/{ability}/roll"])
@pytest.mark.parametrize("edizione", ["2014", "2024"])
async def test_forza_ridotta_da_un_oggetto_resta_a_1(client, edizione):
    cid = await _scheda(client, edizione, punteggi={"strength": 8})
    meta = {"ability_modifiers": [{"ability": "strength", "kind": "relative", "value": -10}]}
    await client.post(f"/characters/{cid}/items", json={"name": "Maledetto", "item_metadata": meta, "is_equipped": True})
    pg = await _leggi(client, cid)
    forza = next(s for s in pg["ability_scores"] if s["name"] == "strength")
    assert (forza["value"], forza["modifier"]) == (1, -5)
    assert (await _tira(client, cid, "ability_checks/strength/roll", die=10))["bonus"] == -5
    assert pg["carry_capacity"] >= 0


@pytest.mark.caccia(id="CB-1001", fonte="decisione D-013: il punteggio effettivo non scende sotto 1, il modificatore non sotto -5",
                    zona="flusso:caratteristiche-tiri", voce="limiti", copre=["POST /characters/{char_id}/items", "GET /characters/{char_id}"])
@pytest.mark.parametrize("edizione", ["2014", "2024"])
async def test_costituzione_ridotta_da_un_oggetto_resta_a_1_e_i_pf_la_seguono(client, edizione):
    cid = await _scheda(client, edizione, "wizard", 4, {"constitution": 8}, dado_vita=6)
    meta = {"ability_modifiers": [{"ability": "constitution", "kind": "relative", "value": -10}]}
    await client.post(f"/characters/{cid}/items", json={"name": "Maledetto", "item_metadata": meta, "is_equipped": True})
    pg = await _leggi(client, cid)
    con = next(s for s in pg["ability_scores"] if s["name"] == "constitution")
    assert (con["value"], con["modifier"]) == (1, -5)
    assert (await _tira(client, cid, "ability_checks/constitution/roll", die=10))["bonus"] == -5
    assert pg["hit_points"] >= 4


@pytest.mark.caccia(id="CB-994", fonte="CLAUDE.md · Auth: ogni endpoint filtra per l'utente autenticato; invariante: nessun dato altrui nelle risposte", zona="flusso:caratteristiche-tiri",
                    voce="permessi", copre=["POST /characters/{char_id}/tool_checks/{tool}/roll", "PATCH /characters/{char_id}", "PATCH /characters/{char_id}/inspiration",
                                             "GET /characters/{char_id}", "POST /characters/{char_id}/dice/initiative"])
async def test_un_altro_utente_non_tocca_strumenti_ispirazione_e_dettagli(client, come_utente):
    cid = await _scheda(client, "2024", punteggi={"dexterity": 14})
    await client.patch(f"/characters/{cid}", json={"tool_proficiencies": {"thieves_tools": True}})
    await client.patch(f"/characters/{cid}/inspiration", json={"heroic_inspiration": True})
    prima = await _leggi(client, cid)
    come_utente(9002)
    chiamate = [("get", "", None),
                ("post", "tool_checks/thieves_tools/roll", {"ability": "dexterity", "with_inspiration": True, "die": 5}),
                ("post", "skills/athletics/roll", {"with_inspiration": True, "die": 5}),
                ("post", "dice/initiative", {"die": 5}),
                ("patch", "", {"tool_proficiencies": {"thieves_tools": "expert", "smiths_tools": True}}),
                ("patch", "inspiration", {"heroic_inspiration": False})]
    for metodo, percorso, corpo in chiamate:
        url = f"/characters/{cid}/{percorso}".rstrip("/")
        r = await (getattr(client, metodo)(url) if corpo is None else getattr(client, metodo)(url, json=corpo))
        assert r.status_code in (403, 404), (metodo, percorso, r.status_code)
        assert "thieves_tools" not in r.text, (metodo, percorso)
    come_utente(1234)
    dopo = await _leggi(client, cid)
    assert (dopo["tool_proficiencies"], dopo["heroic_inspiration"], dopo["rolls_history"]) == \
           (prima["tool_proficiencies"], True, prima["rolls_history"])


@pytest.mark.caccia(id="CB-995", fonte="2014 · Guerriero · Campione · Atleta Straordinario · pag. 72 (l'iniziativa è una prova di Destrezza)", zona="flusso:caratteristiche-tiri",
                    voce="regola", copre=["POST /characters/{char_id}/dice/initiative"])
@pytest.mark.parametrize("livello, extra", [(7, 2), (6, 0)])
async def test_atleta_straordinario_2014_vale_per_l_iniziativa(client, livello, extra):
    cid = await _classe(client, "2014", "fighter", livello, "champion")
    r = await _tira(client, cid, "dice/initiative", die=10)
    assert r["total"] == 10 + extra


@pytest.mark.caccia(id="CB-996", fonte="2014 · Bardo · Factotum · pag. 54 / Guerriero · Campione · Atleta Straordinario · pag. 72 (vale il maggiore dei due, non si sommano)", zona="flusso:caratteristiche-tiri",
                    voce="interazione", copre=["POST /characters/{char_id}/classes", "POST /characters/{char_id}/skills/{skill_name}/roll",
                                               "POST /characters/{char_id}/ability_checks/{ability}/roll"])
async def test_factotum_e_atleta_straordinario_non_si_sommano(client):
    cid = await _classe(client, "2014", "fighter", 7, "champion")  # competenza +3 dopo l'aggiunta di 2 livelli di Bardo: 9 livelli, +4
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "bard", "level": 2, "hit_die": 8})
    assert r.status_code == 201, r.text
    pg = await _leggi(client, cid)
    pb = pg["proficiency_bonus"]
    atteso = max(pb // 2, (pb + 1) // 2)
    assert (await _tira(client, cid, "ability_checks/strength/roll", die=10))["bonus"] == atteso
    assert (await _tira(client, cid, "skills/athletics/roll", die=10))["bonus"] == atteso
    assert (await _tira(client, cid, "ability_checks/intelligence/roll", die=10))["bonus"] == pb // 2  # solo Factotum
