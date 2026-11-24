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
