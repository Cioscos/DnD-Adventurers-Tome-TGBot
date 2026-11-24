"""Controlli della zona flusso:riposo."""
import pytest


async def _pg(client, edizione) -> tuple[int, int]:
    cid = (await client.post("/characters", json={"name": "P"})).json()["id"]
    await client.post(f"/characters/{cid}/classes", json={"class_name": "fighter", "level": 4, "hit_die": 10})
    await client.patch(f"/characters/{cid}", json={"rules_edition": edizione})
    return cid, (await client.get(f"/characters/{cid}")).json()["classes"][0]["id"]


async def _spendi(client, cid, classe):
    return await client.post(f"/characters/{cid}/hit_dice/spend", json={"class_id": classe, "count": 1, "rolls": [5]})


@pytest.mark.caccia(id="CB-005", fonte="invariante: un morto non recupera PF né spende dadi vita", zona="flusso:riposo",
                    voce="edizioni", copre=["POST /characters/{char_id}/hit_dice/spend"])
@pytest.mark.parametrize("edizione", ["2014", "2024"])
async def test_un_morto_non_spende_dadi_vita(client, edizione):
    cid, classe = await _pg(client, edizione)
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 0})
    for _ in range(3):
        await client.patch(f"/characters/{cid}/death_saves", json={"action": "failure"})
    assert (await client.get(f"/characters/{cid}")).json()["is_dead"] is True
    assert (await _spendi(client, cid, classe)).status_code == 409
    pg = (await client.get(f"/characters/{cid}")).json()
    assert (pg["current_hit_points"], pg["classes"][0]["hit_dice_used"]) == (0, 0)


@pytest.mark.caccia(id="CB-021", fonte="CLAUDE.md · Rests by edition: 2024 nessun riposo a 0 PF", zona="flusso:riposo",
                    voce="edizioni", copre=["POST /characters/{char_id}/hit_dice/spend"])
async def test_dadi_vita_a_zero_pf_per_edizione(client):
    for edizione, atteso in (("2024", 409), ("2014", 200)):
        cid, classe = await _pg(client, edizione)
        await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 0})
        assert (await _spendi(client, cid, classe)).status_code == atteso


@pytest.mark.caccia(id="CB-012", fonte="CLAUDE.md · ate_and_drank=false blocca la riduzione nel 2014", zona="flusso:riposo",
                    voce="contratto", copre=["GET /characters/{char_id}/rest/preview"])
@pytest.mark.parametrize("edizione, atteso", [("2014", 0), ("2024", -1)])
async def test_anteprima_senza_mangiare(client, edizione, atteso):
    cid, _ = await _pg(client, edizione)
    await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"exhaustion": 2}})
    url = f"/characters/{cid}/rest/preview?rest_type=long"
    assert (await client.get(url)).json()["exhaustion_change"] == -1
    assert (await client.get(url + "&ate_and_drank=false")).json()["exhaustion_change"] == atteso
