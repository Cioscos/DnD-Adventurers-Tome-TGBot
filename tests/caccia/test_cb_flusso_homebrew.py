"""Controlli della zona flusso:homebrew."""
import pytest

from tests.integration.homebrew.test_passive_modifiers import _build_passive_rule
from tests.integration.homebrew.test_passive_modifiers import _ALWAYS_TRUE_CHAR


@pytest.mark.caccia(id="CB-1504", fonte="invariante (come CB-1379): i PF correnti non superano il massimo", zona="flusso:homebrew", voce="annullamento",
                    copre=["DELETE /characters/{char_id}/homebrew/rules/{rule_id}", "PATCH /characters/{char_id}/homebrew/rules/{rule_id}",
                           "POST /characters/{char_id}/homebrew/rules/{rule_id}/enable"])
@pytest.mark.parametrize("via", ["elimina", "disattiva", "modifica"])
async def test_tolta_la_regola_che_alza_i_pf_massimi_i_correnti_scendono(client, via):
    cid = (await client.post("/characters", json={"name": "H", "initial_class": {"class_name": "fighter", "level": 3}})).json()["id"]
    regola = _build_passive_rule("+10 PF", {"type": "character"}, "character.hit_points_max", 10, _ALWAYS_TRUE_CHAR)
    r = await client.post(f"/characters/{cid}/homebrew/rules", json=regola)
    assert r.status_code == 201, r.text
    rid = r.json()["id"]
    await client.patch(f"/characters/{cid}/hp", json={"op": "heal", "value": 100})
    prima = (await client.get(f"/characters/{cid}")).json()
    assert prima["current_hit_points"] == prima["computed"]["hp_max_effective"] == prima["hit_points"] + 10
    url = f"/characters/{cid}/homebrew/rules/{rid}"
    if via == "elimina":
        r = await client.delete(url)
    elif via == "disattiva":
        r = await client.post(f"{url}/enable", json={"enabled": False})
    else:
        r = await client.patch(url, json={"enabled": False})
    assert r.status_code < 300, r.text
    j = (await client.get(f"/characters/{cid}")).json()
    assert j["current_hit_points"] == j["computed"]["hp_max_effective"] == prima["hit_points"]


@pytest.mark.caccia(id="CB-1512", fonte="invariante: una regola homebrew sbagliata non rende illeggibile la scheda", zona="flusso:homebrew", voce="contratto",
                    copre=["POST /characters/{char_id}/homebrew/rules", "GET /characters/{char_id}"])
async def test_una_regola_con_un_percorso_inesistente_non_blocca_la_scheda(client):
    cid = (await client.post("/characters", json={"name": "H", "initial_class": {"class_name": "fighter", "level": 3}})).json()["id"]
    prima = (await client.get(f"/characters/{cid}")).json()["computed"]["hp_max_effective"]
    regola = _build_passive_rule("+10 PF", {"type": "character"}, "character.hit_points_max", 10, {"path": "$character.level", "op": "gte", "value": 1})
    assert (await client.post(f"/characters/{cid}/homebrew/rules", json=regola)).status_code == 201
    r = await client.get(f"/characters/{cid}")
    assert r.status_code == 200 and r.json()["computed"]["hp_max_effective"] == prima


@pytest.mark.caccia(id="CB-1520", fonte="invariante (come CB-1504): vale anche per una regola nuova che abbassa il massimo", zona="flusso:homebrew", voce="normale",
                    copre=["POST /characters/{char_id}/homebrew/rules"])
async def test_una_regola_nuova_che_abbassa_il_massimo_taglia_i_pf(client):
    cid = (await client.post("/characters", json={"name": "H", "initial_class": {"class_name": "fighter", "level": 3}})).json()["id"]
    regola = _build_passive_rule("-5 PF", {"type": "character"}, "character.hit_points_max", -5, _ALWAYS_TRUE_CHAR)
    assert (await client.post(f"/characters/{cid}/homebrew/rules", json=regola)).status_code == 201
    j = (await client.get(f"/characters/{cid}")).json()
    assert j["current_hit_points"] == j["computed"]["hp_max_effective"] == j["hit_points"] - 5


@pytest.mark.caccia(id="CB-1521", fonte="invariante (come CB-1512): una regola illeggibile si legge, si disattiva e si elimina", zona="flusso:homebrew", voce="annullamento",
                    copre=["DELETE /characters/{char_id}/homebrew/rules/{rule_id}", "POST /characters/{char_id}/homebrew/rules/{rule_id}/enable"])
@pytest.mark.parametrize("quando", [None, {"path": 3}])
async def test_una_regola_illeggibile_si_disattiva_e_si_elimina(client, test_session_factory, quando):
    from core.db.models import HomebrewRule
    cid = (await client.post("/characters", json={"name": "H", "initial_class": {"class_name": "fighter", "level": 3}})).json()["id"]
    regola = _build_passive_rule("+10 PF", {"type": "character"}, "character.hit_points_max", 10, _ALWAYS_TRUE_CHAR)
    rid = (await client.post(f"/characters/{cid}/homebrew/rules", json=regola)).json()["id"]
    async with test_session_factory() as s:
        row = await s.get(HomebrewRule, rid)
        mod = {k: v for k, v in row.dsl["passive_modifiers"][0].items() if k != "when"}
        row.dsl = {**row.dsl, "passive_modifiers": [{**mod, **({"when": quando} if quando else {})}]}
        await s.commit()
    assert (await client.get(f"/characters/{cid}")).status_code == 200
    url = f"/characters/{cid}/homebrew/rules/{rid}"
    assert (await client.post(f"{url}/enable", json={"enabled": False})).status_code == 200
    assert (await client.delete(url)).status_code == 204


@pytest.mark.caccia(id="CB-1531", fonte="invariante (come CB-1512)", zona="flusso:homebrew", voce="contratto", copre=["GET /characters/{char_id}"])
async def test_una_condizione_homebrew_con_un_valore_non_confrontabile_non_blocca_la_scheda(client):
    cid = (await client.post("/characters", json={"name": "H", "initial_class": {"class_name": "fighter", "level": 3}})).json()["id"]
    regola = _build_passive_rule("x", {"type": "character"}, "character.hit_points_max", 10, {"path": "$character", "op": "has_property", "value": ["a"]})
    assert (await client.post(f"/characters/{cid}/homebrew/rules", json=regola)).status_code in (201, 422)
    assert (await client.get(f"/characters/{cid}")).status_code == 200


@pytest.mark.caccia(id="CB-1557", fonte="invariante: una condizione che non può essere vera si rifiuta a chi la scrive; un file vecchio resta importabile", zona="flusso:homebrew",
                    voce="contratto", copre=["POST /characters/{char_id}/homebrew/rules", "POST /characters/import"])
@pytest.mark.parametrize("op", ["has_property", "gt"])
async def test_una_condizione_non_confrontabile_si_rifiuta_ma_il_file_si_importa(client, op):
    cid = (await client.post("/characters", json={"name": "H", "initial_class": {"class_name": "fighter", "level": 3}})).json()["id"]
    buona = _build_passive_rule("x", {"type": "character"}, "character.hit_points_max", 10, {"path": "$character.level", "op": op, "value": "1"})
    assert (await client.post(f"/characters/{cid}/homebrew/rules", json=buona)).status_code == 201
    dati = (await client.get(f"/characters/{cid}/export")).json()
    brutta = _build_passive_rule("x", {"type": "character"}, "character.hit_points_max", 10, {"path": "$character.level", "op": op, "value": ["1"]})
    assert (await client.post(f"/characters/{cid}/homebrew/rules", json=brutta)).status_code == 422
    dati["homebrew_rules"][0]["dsl"] = brutta["dsl"]
    assert (await client.post("/characters/import", json=dati)).status_code == 201
