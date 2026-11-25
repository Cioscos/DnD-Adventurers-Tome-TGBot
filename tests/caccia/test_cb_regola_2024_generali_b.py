"""Controlli della zona regola:2024/generali (parte generali-b)."""
import pytest

from tests.integration.rules.test_2014_bard import _use
from tests.integration.rules.test_2024_sorcerer_subclasses import _make


async def _pg(client, classe="fighter", livello=1, edizione="2024") -> int:
    r = await client.post("/characters", json={"name": "Prova", "rules_edition": edizione,
                                               "initial_class": {"class_name": classe, "level": livello}})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _oggetto(client, cid, **corpo) -> int:
    r = await client.post(f"/characters/{cid}/items", json=corpo)
    assert r.status_code == 201, r.text
    return max(i["id"] for i in r.json()["items"])


async def _piastre(client, cid) -> int:
    return await _oggetto(client, cid, name="Piastre", item_type="armor", is_equipped=True,
                          item_metadata={"armor_type": "heavy", "ac_value": 18})


async def _condizioni(client, cid, **condizioni) -> dict:
    r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": condizioni})
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------------------------------------------------
# Rossi
# ---------------------------------------------------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-2911", fonte="2024 · Glossario · Punti Esperienza · pag. 366-367", zona="regola:2024/generali", voce="regola",
                    copre=["carta:2024/general.md#Experience Points (Punti Esperienza) (pag. 366-367)",
                           "PATCH /characters/{char_id}", "PATCH /characters/{char_id}/classes/distribute", "PATCH /characters/{char_id}/xp"])
@pytest.mark.xfail(strict=True, reason="CB-2911: difforme dal manuale, confermato")
async def test_assegnare_punti_esperienza_non_toglie_livelli_gia_presi(client):
    r = await client.post("/characters", json={"name": "Prova", "rules_edition": "2024",
                                               "initial_class": {"class_name": "fighter", "level": 1}})
    assert r.status_code == 201, r.text
    cid, classe = r.json()["id"], r.json()["classes"][0]["id"]
    assert (await client.patch(f"/characters/{cid}", json={"settings": {"advancement": "milestone"}})).status_code == 200
    r = await client.patch(f"/characters/{cid}/classes/distribute", json={"classes": [{"class_id": classe, "level": 5}]})
    assert r.status_code == 200 and r.json()["classes"][0]["level"] == 5, r.text
    assert (await client.patch(f"/characters/{cid}", json={"settings": {"advancement": "xp"}})).status_code == 200
    r = await client.patch(f"/characters/{cid}/xp", json={"add": 100})
    assert r.status_code == 200, r.text
    assert r.json()["classes"][0]["level"] == 5


@pytest.mark.caccia(id="CB-2912", fonte="2024 · Glossario · Prova di d20 · pag. 364; Stregone · Trance dell'Ordine · pag. 147",
                    zona="regola:2024/generali", voce="interazione",
                    copre=["carta:2024/general.md#D20 Test (Prova di d20) (pag. 364)",
                           "carta:2024/classes/sorcerer.md#Trance dell'Ordine / Trance of Order (Stregoneria Meccanica 14, pag. 147)",
                           "POST /characters/{char_id}/features/{feature_key}/use", "POST /characters/{char_id}/concentration/save"])
@pytest.mark.xfail(strict=True, reason="CB-2912: difforme dal manuale, confermato")
async def test_la_trance_dell_ordine_alza_a_10_anche_il_ts_di_concentrazione(client):
    cid = await _make(client, "clockwork", 14)
    assert (await _use(client, cid, "sorcerer.trance_of_order")).status_code == 200
    r = await client.post(f"/characters/{cid}/concentration/save", json={"damage": 10, "dice": [3]})
    assert r.status_code == 200, r.text
    assert r.json()["die"] == 10


@pytest.mark.caccia(id="CB-2913", fonte="2024 · Glossario · Addestramento con le armature · pag. 361", zona="regola:2024/generali", voce="regola",
                    copre=["carta:2024/general.md#Armor Training (Addestramento con le armature) (pag. 361)",
                           "POST /characters/{char_id}/items", "POST /characters/{char_id}/items/{item_id}/cast"])
async def test_con_un_armatura_senza_addestramento_non_si_lancia_da_un_oggetto(client):
    cid = await _pg(client, "wizard")
    await _piastre(client, cid)
    bacchetta = await _oggetto(client, cid, name="Bacchetta", item_type="wondrous", item_metadata={
        "charges": {"current": 3, "max": 3}, "granted_spells": [{"name": "Dardo", "level": 1, "charges_cost": 1}]})
    r = await client.post(f"/characters/{cid}/items/{bacchetta}/cast", json={"spell_index": 0})
    assert r.status_code == 409 and "armor" in r.text, r.status_code


# ---------------------------------------------------------------------------------------------------------------------
# Verdi
# ---------------------------------------------------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-2914", fonte="2024 · Glossario · Concentrazione · pag. 363", zona="regola:2024/generali", voce="limiti",
                    copre=["carta:2024/general.md#Concentration (Concentrazione) (pag. 363)", "POST /characters/{char_id}/concentration/save"])
@pytest.mark.parametrize("danno,cd", [(1, 10), (21, 10), (22, 11), (60, 30), (61, 30), (70, 30)])
async def test_la_cd_della_concentrazione_e_il_maggiore_fra_10_e_meta_danno_fino_a_30(client, danno, cd):
    cid = await _pg(client, "wizard")
    r = await client.post(f"/characters/{cid}/concentration/save", json={"damage": danno, "dice": [10]})
    assert r.status_code == 200 and r.json()["dc"] == cd, r.text


@pytest.mark.caccia(id="CB-2920", fonte="2024 · Glossario · Concentrazione · pag. 363; 2014 · Incantesimi · Durata (Concentrazione) · pag. 203",
                    zona="regola:2024/generali", voce="edizioni",
                    copre=["carta:2024/general.md#Concentration (Concentrazione) (pag. 363)", "carta:2014/general.md#Durata / Duration (pag. 203)",
                           "POST /characters/{char_id}/concentration/save"])
@pytest.mark.parametrize("edizione,cd", [("2014", 35), ("2024", 30)])
async def test_solo_il_2024_ferma_la_cd_della_concentrazione_a_30(client, edizione, cd):
    cid = await _pg(client, "wizard", edizione=edizione)
    r = await client.post(f"/characters/{cid}/concentration/save", json={"damage": 70, "dice": [10]})
    assert r.status_code == 200 and r.json()["dc"] == cd, r.text


@pytest.mark.caccia(id="CB-2915", fonte="2024 · Glossario · Esaurimento pag. 366 e Prova di d20 pag. 364", zona="regola:2024/generali", voce="regola",
                    copre=["carta:2024/general.md#Exhaustion [Condition] (Esaurimento) (pag. 366)",
                           "carta:2024/general.md#D20 Test (Prova di d20) (pag. 364)", "PATCH /characters/{char_id}/conditions",
                           "POST /characters/{char_id}/ability_checks/{ability}/roll", "POST /characters/{char_id}/tool_checks/{tool}/roll"])
async def test_l_esaurimento_toglie_2_per_livello_anche_alle_prove_pure_e_con_strumento(client):
    cid = await _pg(client, "rogue")
    prova = lambda: client.post(f"/characters/{cid}/ability_checks/strength/roll", json={"die": 10})  # noqa: E731
    attrezzi = lambda: client.post(f"/characters/{cid}/tool_checks/thieves_tools/roll", json={"die": 10, "ability": "dexterity"})  # noqa: E731
    prima = ((await prova()).json()["total"], (await attrezzi()).json()["total"])
    scheda = await _condizioni(client, cid, exhaustion=3)
    assert ((await prova()).json()["total"], (await attrezzi()).json()["total"]) == (prima[0] - 6, prima[1] - 6)
    assert scheda["computed"]["speed"] == scheda["speed"] - 15


@pytest.mark.caccia(id="CB-2916", fonte="2024 · Glossario · Colpo Critico · pag. 364", zona="regola:2024/generali", voce="regola",
                    copre=["carta:2024/general.md#Critical Hit (Colpo Critico) (pag. 364)", "POST /characters/{char_id}/items/{item_id}/attack"])
async def test_il_critico_raddoppia_i_dadi_dell_arma_ma_non_il_modificatore(client, dadi):
    cid = await _pg(client)
    assert (await client.patch(f"/characters/{cid}/ability_scores/strength", json={"value": 16})).status_code == 200
    spada = await _oggetto(client, cid, name="Spada", item_type="weapon",
                           item_metadata={"damage_dice": "1d8", "weapon_type": "melee", "properties": []})
    dadi(5, 7)
    r = await client.post(f"/characters/{cid}/items/{spada}/attack", json={"die": 20})
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["is_critical"] and corpo["damage_rolls"] == [5, 7] and corpo["damage_total"] == 5 + 7 + 3


@pytest.mark.caccia(id="CB-2917", fonte="2024 · Glossario · Vantaggio pag. 360, Svantaggio pag. 366, Addestramento con le armature pag. 361",
                    zona="regola:2024/generali", voce="interazione",
                    copre=["carta:2024/general.md#Advantage (Vantaggio) (pag. 360)", "carta:2024/general.md#Disadvantage (Svantaggio) (pag. 366)",
                           "carta:2024/general.md#Armor Training (Addestramento con le armature) (pag. 361)",
                           "POST /characters/{char_id}/saving_throws/{ability}/roll"])
async def test_lo_svantaggio_dell_armatura_senza_addestramento_si_annulla_col_vantaggio(client):
    cid = await _pg(client, "wizard")
    await _piastre(client, cid)
    corpo = (await client.post(f"/characters/{cid}/saving_throws/dexterity/roll", json={"die": 10})).json()
    assert corpo["mode_applied"] == "disadvantage" and corpo["notes"] == ["armor:untrained"]
    corpo = (await client.post(f"/characters/{cid}/saving_throws/dexterity/roll", json={"mode": "advantage", "dice": [3, 18]})).json()
    assert corpo["mode_applied"] == "normal" and corpo["dice"] == [3] and corpo["die"] == 3


@pytest.mark.caccia(id="CB-2918", fonte="2024 · Glossario · Sintonia · pag. 361", zona="regola:2024/generali", voce="limiti",
                    copre=["carta:2024/general.md#Attunement (Sintonia) (pag. 361)", "POST /characters/{char_id}/items"])
async def test_al_massimo_tre_oggetti_in_sintonia(client):
    cid = await _pg(client)
    anello = lambda n: client.post(f"/characters/{cid}/items", json={  # noqa: E731
        "name": f"Anello {n}", "item_type": "wondrous", "item_metadata": {"requires_attunement": True, "attuned": True}})
    assert [(await anello(n)).status_code for n in range(3)] == [201, 201, 201]
    r = await anello(3)
    assert r.status_code == 409 and "attunement_limit" in r.text


@pytest.mark.caccia(id="CB-2919", fonte="2024 · Glossario · Morto · pag. 365", zona="regola:2024/generali", voce="regola",
                    copre=["carta:2024/general.md#Dead (Morto) (pag. 365)", "PATCH /characters/{char_id}/hp", "POST /characters/{char_id}/revive"])
async def test_tornato_in_vita_ha_un_livello_di_esaurimento_in_meno_e_nessuna_sintonia(client):
    cid = await _pg(client)
    await _oggetto(client, cid, name="Anello", item_type="wondrous", item_metadata={"requires_attunement": True, "attuned": True})
    await _condizioni(client, cid, exhaustion=3)
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 200})
    assert r.status_code == 200 and r.json()["is_dead"], r.text
    r = await client.post(f"/characters/{cid}/revive")
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert not corpo["is_dead"] and corpo["conditions"]["exhaustion"] == 2
    assert [i["item_metadata"].get("attuned") for i in corpo["items"]] == [False]
