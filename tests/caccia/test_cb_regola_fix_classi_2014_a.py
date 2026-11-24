"""Controlli scritti dalla correzione del gruppo classi-2014-a per i dubbi risolti come difetti (Q-…)."""
import pytest

BI = "bard.bardic_inspiration"


async def _riga(client, cid, chiave) -> dict | None:
    return next((a for a in (await client.get(f"/characters/{cid}")).json()["abilities"] if a["feature_key"] == chiave), None)


@pytest.mark.caccia(id="CB-4391", fonte="2014 · Bardo · Ispirazione Superiore · pag. 54", zona="regola:2014/bard", voce="regola",
                    copre=["carta:2014/classes/bard.md#Ispirazione Superiore / Superior Inspiration (Bardo 20, pag. 54)",
                           "POST /characters/{char_id}/dice/initiative"])
async def test_ispirazione_superiore_scatta_da_sola_al_tiro_di_iniziativa(client):
    r = await client.post("/characters", json={"name": "Bardo", "rules_edition": "2014",
                                               "initial_class": {"class_name": "bard", "level": 20}})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    riga = await _riga(client, cid, BI)
    assert (await client.patch(f"/characters/{cid}/abilities/{riga['id']}", json={"uses": 0})).status_code == 200
    # privilegio passivo (Q-2014-bard-1): il giocatore non spunta nulla
    r = await client.post(f"/characters/{cid}/dice/initiative", json={"die": 8})
    assert r.status_code == 200, r.text
    assert (await _riga(client, cid, BI))["uses"] == 1
