"""Controlli della zona flusso:hp-morte."""
import pytest


async def _pg(client, edizione="2014") -> int:
    cid = (await client.post("/characters", json={"name": "P"})).json()["id"]
    await client.post(f"/characters/{cid}/classes", json={"class_name": "fighter", "level": 3, "hit_die": 10})
    await client.patch(f"/characters/{cid}", json={"rules_edition": edizione})
    return cid


@pytest.mark.caccia(id="CB-015", fonte="invariante: un danno negativo non esiste", zona="flusso:hp-morte",
                    voce="limiti", copre=["PATCH /characters/{char_id}/hp"])
async def test_danno_negativo_rifiutato(client):
    cid = await _pg(client)
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_temp", "value": 3})
    assert (await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": -9})).status_code == 422
    assert (await client.patch(f"/characters/{cid}/hp", json={"op": "heal", "value": -4})).status_code == 422
    assert (await client.get(f"/characters/{cid}")).json()["temp_hp"] == 3


@pytest.mark.caccia(id="CB-016", fonte="2014 · Tiri salvezza contro la morte · pag. 197; 2024 · pag. 28", zona="flusso:hp-morte",
                    voce="regola", copre=["POST /characters/{char_id}/death_saves/roll"])
@pytest.mark.parametrize("edizione", ["2014", "2024"])
async def test_tiro_morte_solo_a_zero_e_non_stabile(client, edizione):
    cid = await _pg(client, edizione)
    prima = (await client.get(f"/characters/{cid}")).json()
    assert (await client.post(f"/characters/{cid}/death_saves/roll", json={"die": 20})).status_code == 409
    dopo = (await client.get(f"/characters/{cid}")).json()
    assert (dopo["current_hit_points"], dopo["death_saves"]) == (prima["current_hit_points"], prima["death_saves"])

    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 0})
    await client.patch(f"/characters/{cid}/death_saves", json={"action": "stabilize"})
    assert (await client.post(f"/characters/{cid}/death_saves/roll", json={"die": 2})).status_code == 409
    assert (await client.get(f"/characters/{cid}")).json()["death_saves"] == {"successes": 0, "failures": 0, "stable": True}

    await client.patch(f"/characters/{cid}/death_saves", json={"action": "reset"})
    assert (await client.post(f"/characters/{cid}/death_saves/roll", json={"die": 2})).json()["failures"] == 1


@pytest.mark.caccia(id="CB-1503", fonte="invariante (come CB-1379): i PF correnti non superano il massimo", zona="flusso:hp-morte", voce="annullamento",
                    copre=["POST /characters/{char_id}/hp/undo"])
async def test_annullare_il_danno_non_supera_un_massimo_calato_nel_frattempo(client):
    umano = {"key": "2024_human", "options": {"size": "medium", "skill": "arcana", "origin_feat": "2024_tough"}}
    cid = (await client.post("/characters", json={"name": "R", "rules_edition": "2024", "species_2024": umano,
        "initial_class": {"class_name": "fighter", "level": 4, "skill_choices": ["athletics", "history"]}})).json()["id"]
    pg = (await client.get(f"/characters/{cid}")).json()
    massimo = pg["computed"]["hp_max_effective"]
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": massimo})
    await client.patch(f"/characters/{cid}/hp", json={"op": "heal", "value": massimo})
    danno = (await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 10})).json()
    robusto = next(a["id"] for a in pg["abilities"] if a["feature_key"] == "feat.2024_tough")
    assert (await client.delete(f"/characters/{cid}/abilities/{robusto}")).status_code < 300
    r = await client.post(f"/characters/{cid}/hp/undo", json={"op_id": danno["hp_undo_id"]})
    assert r.status_code in (200, 409), r.text
    j = (await client.get(f"/characters/{cid}")).json()
    assert j["current_hit_points"] <= j["computed"]["hp_max_effective"]
