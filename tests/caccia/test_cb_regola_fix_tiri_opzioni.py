"""Controlli scritti dal correttore del gruppo tiri-opzioni per i dubbi «Q-…» risolti dai verificatori come difetti."""
import pytest

from tests.caccia.test_cb_regola_2024_paladin import _seduti
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, setup_full_encounter
from tests.integration.rules.test_2014_paladin import _hurt, _paladin


async def _pg(client, edizione="2024", classe="fighter", livello=5) -> int:
    r = await client.post("/characters", json={"name": "P", "rules_edition": edizione,
                                               "initial_class": {"class_name": classe, "level": livello}})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    r = await client.patch(f"/characters/{cid}", json={"rules_edition": edizione})
    assert r.status_code == 200, r.text
    return cid


async def _cond(client, cid, **condizioni) -> dict:
    r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": condizioni})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.caccia(id="CB-4231", fonte="2024 · Regole di gioco · Vantaggio e Svantaggio, rilanci · pag. 12-13; Ispirazione Eroica · pag. 13", zona="regola:2024/generali",
                    voce="interazione", copre=["carta:2024/general.md#Vantaggio e Svantaggio / Advantage/Disadvantage (pag. 12-13)",
                                               "carta:2024/general.md#Ispirazione Eroica / Heroic Inspiration (pag. 13)",
                                               "POST /characters/{char_id}/skills/{skill_name}/roll"])
@pytest.mark.parametrize("primo,atteso", [
    ({"mode": "advantage", "dice": [8, 5]}, ("advantage", 8)),  # rilancia il 5: max(8, 3) = 8
    ({"mode": "normal", "dice": [15, 3], "avvelenato": True}, ("disadvantage", 15)),  # svantaggio automatico: min(15, 18) = 15
])
async def test_il_rilancio_con_ispirazione_tiene_l_altro_d20_e_il_modo(client, primo, atteso):
    cid = await _pg(client)
    if primo.pop("avvelenato", False):
        await _cond(client, cid, poisoned=True)
    await client.patch(f"/characters/{cid}/inspiration", json={"heroic_inspiration": True})
    assert (await client.post(f"/characters/{cid}/skills/stealth/roll", json=primo)).status_code == 200
    nuovo = 3 if atteso[0] == "advantage" else 18
    r = await client.post(f"/characters/{cid}/skills/stealth/roll", json={"with_inspiration": True, "die": nuovo})
    assert r.status_code == 200, r.text
    # un solo d20 si rilancia, l'altro resta e il vantaggio o lo svantaggio continua a decidere
    assert (r.json()["mode"], r.json()["die"]) == atteso, r.json()
    assert len(r.json()["dice"]) == 2 and nuovo in r.json()["dice"], r.json()


@pytest.mark.caccia(id="CB-4232", fonte="2014 · Condizioni · Privo di Sensi · pag. 292", zona="regola:2014/generali",
                    voce="edizioni", copre=["carta:2014/general.md#Privo di Sensi / Unconscious (pag. 292)",
                                            "PATCH /characters/{char_id}/conditions"])
async def test_2014_privo_di_sensi_messo_a_mano_fa_cadere_prono(client):
    cid = await _pg(client, "2014")
    # «lascia cadere ciò che impugna e cade prono», da qualunque fonte venga la condizione (non solo dagli 0 PF)
    assert (await _cond(client, cid, unconscious=True))["conditions"] == {"unconscious": True, "prone": True}
    # risvegliandosi resta prono: ci si rialza spendendo movimento
    assert (await _cond(client, cid, unconscious=False))["conditions"] == {"unconscious": False, "prone": True}


async def _scontro(client, test_session_factory, edizione):
    """Incontro avviato (turno del PG, poi goblin 1 e goblin 2) con il PG nell'edizione chiesta."""
    sid, _ = await setup_full_encounter(client, test_session_factory)
    pg, goblin1, goblin2 = (await client.post(f"/sessions/{sid}/encounter/start", json={})).json()["combatants"]
    as_user(PLAYER_ID)
    assert (await client.patch(f"/characters/{pg['character_id']}", json={"rules_edition": edizione})).status_code == 200
    as_user(GM_ID)
    return sid, pg, goblin1, goblin2


async def _applica(client, sid, bersaglio, fonte, round_, **altro):
    r = await client.post(f"/sessions/{sid}/encounter/combatants/{bersaglio['id']}/conditions", json={
        "slug": "frightened", "expiry": {"anchor": "owner", "edge": "end", "count": round_},
        "source_combatant_id": fonte["id"], **altro})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.caccia(id="CB-4233", fonte="2014 · Condizioni · Regole generali · pag. 290", zona="regola:2014/generali",
                    voce="interazione", copre=["carta:2014/general.md#Regole generali / General (pag. 290)",
                                               "POST /sessions/{session_id}/encounter/combatants/{combatant_id}/conditions",
                                               "POST /sessions/{session_id}/encounter/next-turn"])
async def test_2014_due_fonti_della_stessa_condizione_hanno_ciascuna_la_sua_durata(client, test_session_factory):
    sid, pg, goblin1, goblin2 = await _scontro(client, test_session_factory, "2014")
    await _applica(client, sid, pg, goblin1, 10)
    await _applica(client, sid, pg, goblin2, 1)
    for _ in range(4):  # finita l'istanza da 1 round, quella da 10 round tiene la condizione
        assert (await client.post(f"/sessions/{sid}/encounter/next-turn")).status_code == 200
    as_user(PLAYER_ID)
    scheda = (await client.get(f"/characters/{pg['character_id']}")).json()
    assert scheda["conditions"].get("frightened") is True
    assert [e["source_name"] for e in scheda["condition_effects"]] == [goblin1["name"]], scheda["condition_effects"]
    as_user(GM_ID)  # il turno indietro rimette anche l'istanza finita con l'ultimo avanzamento
    assert (await client.post(f"/sessions/{sid}/encounter/prev-turn")).status_code == 200
    as_user(PLAYER_ID)
    scheda = (await client.get(f"/characters/{pg['character_id']}")).json()
    assert sorted((e["source_name"], e["expiry_count"]) for e in scheda["condition_effects"]) == [
        (goblin1["name"], 10), (goblin2["name"], 1)], scheda["condition_effects"]


@pytest.mark.caccia(id="CB-4234", fonte="2024 · Regole di gioco · Condizioni, istanze multiple · pag. 29", zona="regola:2024/generali",
                    voce="interazione", copre=["carta:2024/general.md#Condizioni / Conditions (pag. 29)",
                                               "POST /sessions/{session_id}/encounter/combatants/{combatant_id}/conditions",
                                               "POST /sessions/{session_id}/encounter/pending-saves/{save_id}/resolve"])
async def test_la_stessa_fonte_corregge_la_sua_istanza_e_un_ts_superato_chiude_solo_quella(client, test_session_factory):
    sid, pg, goblin1, goblin2 = await _scontro(client, test_session_factory, "2024")
    await _applica(client, sid, goblin1, pg, 10)
    await _applica(client, sid, goblin1, goblin2, 1, save={"ability": "wisdom", "dc": 13, "edge": "end"})
    # la stessa fonte che la riapplica corregge la propria istanza, non ne aggiunge un'altra
    enc = await _applica(client, sid, goblin1, goblin2, 5, save={"ability": "wisdom", "dc": 13, "edge": "end"})
    mostro = next(c for c in enc["combatants"] if c["id"] == goblin1["id"])
    assert sorted(e["expiry_count"] for e in mostro["condition_effects"]) == [5, 10], mostro["condition_effects"]
    for _ in range(2):  # fine del turno del goblin 1: il TS dell'istanza del goblin 2
        r = await client.post(f"/sessions/{sid}/encounter/next-turn")
        assert r.status_code == 200, r.text
    [ts] = next(c for c in r.json()["combatants"] if c["id"] == goblin1["id"])["pending_saves"]
    r = await client.post(f"/sessions/{sid}/encounter/pending-saves/{ts['id']}/resolve", json={"passed": True})
    assert r.status_code == 200, r.text
    mostro = next(c for c in r.json()["combatants"] if c["id"] == goblin1["id"])
    # il TS superato chiude l'istanza del goblin 2; quella del PG resta e con lei la condizione
    assert mostro["conditions"].get("frightened") is True
    assert [e["source_name"] for e in mostro["condition_effects"]] == [pg["name"]], mostro["condition_effects"]


@pytest.mark.caccia(id="CB-4235", fonte="2014 · Paladino · Aura di Protezione · pag. 98", zona="regola:2014/paladin",
                    voce="interazione", copre=["carta:2014/classes/paladin.md#Aura di Protezione / Aura of Protection (Paladino 6, pag. 98)",
                                               "GET /characters/{char_id}/roll-options",
                                               "POST /characters/{char_id}/saving_throws/{ability}/roll",
                                               "POST /characters/{char_id}/death_saves/roll"])
async def test_2014_il_paladino_prende_l_aura_di_protezione_piu_forte_di_un_compagno(client, test_session_factory):
    as_user(GM_ID)
    debole = await _paladin(client, 6, charisma=10)  # la sua aura dà +1
    as_user(PLAYER_ID)
    forte = await _paladin(client, 9, charisma=20)  # la sua aura dà +5
    await _seduti(test_session_factory, (GM_ID, debole), (PLAYER_ID, forte))
    as_user(GM_ID)
    semplice = (await client.post(f"/characters/{debole}/saving_throws/dexterity/roll", json={"die": 10})).json()["total"]
    r = await client.post(f"/characters/{debole}/saving_throws/dexterity/roll", json={"die": 10, "options": ["aura:protection"]})
    assert r.status_code == 200, r.text
    assert r.json()["total"] == semplice + 4  # vale l'aura più forte (+5) al posto della propria (+1), non la somma
    # a 0 PF la sua aura è spenta (deve essere cosciente per conferirla), ma è una creatura amica entro 3 m del compagno
    await _hurt(test_session_factory, debole, 0)
    r = await client.post(f"/characters/{debole}/death_saves/roll", json={"die": 7, "options": ["aura:protection"]})
    assert r.status_code == 200, r.text
    assert r.json()["outcome"] == "success", r.json()  # 7 + 5 = 12


# ---------------------------------------------------------------------------
# Revisione: istanze multiple della stessa condizione, rilanci e dado del Valore
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-4236", fonte="2024 · Condizioni · pag. 29 (ogni istanza ha la sua durata); fuga contro la CD dell'effetto (U36)", zona="regola:2024/generali",
                    voce="interazione", copre=["carta:2024/general.md#Condizioni / Conditions (pag. 29)",
                                               "POST /characters/{char_id}/conditions/{slug}/escape"])
async def test_liberarsi_chiude_solo_la_presa_battuta(client, test_session_factory):
    sid, pg, goblin1, goblin2 = await _scontro(client, test_session_factory, "2024")
    for fonte, cd in ((goblin1, 25), (goblin2, 5)):
        r = await client.post(f"/sessions/{sid}/encounter/combatants/{pg['id']}/conditions", json={
            "slug": "grappled", "save": {"ability": "strength", "dc": cd, "edge": "end"}, "source_combatant_id": fonte["id"]})
        assert r.status_code == 200, r.text
    as_user(PLAYER_ID)
    cid = pg["character_id"]
    facile = next(e for e in (await client.get(f"/characters/{cid}")).json()["condition_effects"] if e["save_dc"] == 5)
    r = await client.post(f"/characters/{cid}/conditions/grappled/escape?skill=athletics&effect_id={facile['id']}", json={"die": 10})
    assert r.status_code == 200, r.text
    assert (r.json()["dc"], r.json()["escaped"]) == (5, True), r.json()
    scheda = (await client.get(f"/characters/{cid}")).json()
    # liberato dalla presa del goblin 2: quella del goblin 1, con la sua CD, lo tiene ancora afferrato
    assert scheda["conditions"].get("grappled") is True
    assert [(e["source_name"], e["save_dc"]) for e in scheda["condition_effects"]] == [(goblin1["name"], 25)]


@pytest.mark.caccia(id="CB-4237", fonte="2014 · Condizioni · Regole generali · pag. 290; Calmare Emozioni · pag. 218", zona="regola:2014/generali",
                    voce="interazione", copre=["carta:2014/general.md#Regole generali / General (pag. 290)",
                                               "POST /characters/{char_id}/spells/{spell_id}/use", "POST /characters/{char_id}/rounds/tick",
                                               "PATCH /characters/{char_id}/concentration"])
async def test_calmare_emozioni_sospende_ogni_istanza_con_la_sua_durata(client, test_session_factory):
    from api.services.condition_effects import ExpirySpec, upsert_effect
    cid = await _pg(client, "2014", "cleric")
    classe = (await client.get(f"/characters/{cid}")).json()["classes"][0]["id"]
    spell = (await client.post(f"/characters/{cid}/spells", json={
        "name": "calm-emotions", "level": 2, "srd_index": "calm-emotions", "is_prepared": True, "is_concentration": True, "class_id": classe})).json()["id"]
    await _cond(client, cid, charmed=True)
    async with test_session_factory() as s:
        for nota, durata in (("Driade", 5), ("Vampiro", 2)):
            await upsert_effect(s, ("character", cid), "charmed", expiry=ExpirySpec("owner", "start", durata), source_note=nota)
        await s.commit()
    r = await client.post(f"/characters/{cid}/spells/{spell}/use", json={"slot_level": 2, "removal": {"targets": ["self"]}})
    assert r.status_code == 200, r.text
    for _ in range(2):  # sospese, le durate scorrono: quella del vampiro finisce, quella della driade no
        assert (await client.post(f"/characters/{cid}/rounds/tick")).status_code == 200
    await client.patch(f"/characters/{cid}/concentration", json={"spell_id": None})
    scheda = (await client.get(f"/characters/{cid}")).json()
    assert scheda["conditions"].get("charmed") is True
    assert [(e["source_note"], e["expiry_count"]) for e in scheda["condition_effects"]] == [("Driade", 3)]


@pytest.mark.caccia(id="CB-4238", fonte="2024 · Condizioni · pag. 29 (ogni istanza ha la sua durata)", zona="regola:2024/generali",
                    voce="persistenza", copre=["carta:2024/general.md#Condizioni / Conditions (pag. 29)",
                                               "GET /characters/{char_id}/export", "POST /characters/import"])
async def test_export_e_import_tengono_ogni_istanza_della_stessa_condizione(client, test_session_factory):
    from api.services.condition_effects import ExpirySpec, upsert_effect
    cid = await _pg(client)
    await _cond(client, cid, frightened=True)
    async with test_session_factory() as s:  # due fonti senza nota: la fonte non viaggia con il file
        for fonte, durata in ((None, 10), (cid, 1)):
            await upsert_effect(s, ("character", cid), "frightened", expiry=ExpirySpec("owner", "start", durata), source_character_id=fonte)
        await s.commit()
    r = await client.post("/characters/import", json=(await client.get(f"/characters/{cid}/export")).json())
    assert r.status_code == 201, r.text
    assert sorted(e["expiry_count"] for e in r.json()["condition_effects"]) == [1, 10], r.json()["condition_effects"]
