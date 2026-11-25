"""Controlli scritti dai correttori del gruppo spells-danni per i dubbi «Q-…» risolti come difetti."""
import random

import pytest


@pytest.mark.caccia(id="CB-3951", fonte="2024 · Incantesimi · Esplosione occulta · pag. 267", zona="regola:2024/incantesimi-D-F", voce="regola",
                    copre=["carta:2024/spells.md#Esplosione occulta", "POST /characters/{char_id}/spells/{spell_id}/attack"])
async def test_esplosione_occulta_al_quinto_livello_fa_un_tiro_per_colpire_per_raggio(client, monkeypatch):
    r = await client.post("/characters", json={"name": "Warlock", "rules_edition": "2024",
                                               "initial_class": {"class_name": "warlock", "level": 5}})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Esplosione occulta", "level": 0, "srd_index": "eldritch-blast",
                                                             "attack_save": "ATK", "damage_dice": "1d10", "damage_type": "force"})
    assert r.status_code == 201, r.text
    d20: list[int] = []
    vero = random.randint

    def conta(a: int, b: int) -> int:
        if (a, b) == (1, 20):
            d20.append(1)
        return vero(a, b)
    monkeypatch.setattr(random, "randint", conta)
    attacco = f"/characters/{cid}/spells/{r.json()['id']}/attack"
    # due raggi al 5° livello, ciascuno col suo tiro per colpire (anche su bersagli diversi): uno per richiesta (D-037), un solo lancio
    for corpo, stato in (({}, 200), ({"ray": True}, 200), ({"ray": True}, 409)):
        r = await client.post(attacco, json=corpo)
        assert r.status_code == stato, r.text
    assert len(d20) == 2
