"""Controlli delle decisioni dell'utente D-021…D-044 (tests/caccia/decisioni.md), scritti nel giro che le applica."""
import pytest

from tests.integration._encounter_helpers import PLAYER_ID, as_user


async def _pg(client, edizione: str, classe: str | None = None, livello: int = 1, sottoclasse: str | None = None, **punteggi) -> int:
    corpo = {"name": "Prova", "rules_edition": edizione}
    if classe:
        corpo["initial_class"] = {"class_name": classe, "level": livello, "subclass": sottoclasse}
    r = await client.post("/characters", json=corpo)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    for nome, valore in punteggi.items():
        r = await client.patch(f"/characters/{cid}/ability_scores/{nome}", json={"value": valore})
        assert r.status_code == 200, r.text
    return cid


async def _scheda(client, cid) -> dict:
    return (await client.get(f"/characters/{cid}")).json()


async def _turno(client, cid) -> dict:
    return (await client.get(f"/characters/{cid}/turn-state")).json()["turn"]


@pytest.mark.caccia(id="CB-4601", fonte="decisione D-021 (tests/caccia/decisioni.md): nel 2024 «Termina» l'Ira è gratis; 2024 · Barbaro · Ira · pag. 51; 2014 · pag. 48",
                    zona="regola:2024/barbarian", voce="regola",
                    copre=["carta:2024/classes/barbarian.md#Ira / Rage (Barbaro 1, pag. 51)",
                           "DELETE /characters/{char_id}/active-states/{key}"])
@pytest.mark.parametrize("edizione, speso", [("2014", True), ("2024", False)])
async def test_terminare_l_ira_a_mano_costa_l_azione_bonus_solo_nel_2014(client, edizione, speso):
    cid = await _pg(client, edizione, "barbarian", 15)  # Ira Persistente: resta accesa al turno dopo senza attacchi
    assert (await client.post(f"/characters/{cid}/features/barbarian.rage/use", json={})).status_code == 200
    await client.post(f"/characters/{cid}/turn/new")
    assert (await client.delete(f"/characters/{cid}/active-states/rage")).status_code == 200
    assert (await _turno(client, cid))["bonus_used"] is speso
