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
