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
