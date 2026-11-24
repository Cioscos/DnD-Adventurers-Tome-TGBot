"""Controlli scritti dalla correzione del gruppo lancio-core per i dubbi risolti come difetti (Q-…)."""
import pytest


async def _pg(client, classe, livello, **punteggi) -> tuple[int, int]:
    """``(personaggio, classe)`` 2014."""
    r = await client.post("/characters", json={"name": "Incantatore", "rules_edition": "2014",
                                               "initial_class": {"class_name": classe, "level": livello}})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    for caratteristica, valore in punteggi.items():
        r = await client.patch(f"/characters/{cid}/ability_scores/{caratteristica}", json={"value": valore})
        assert r.status_code == 200, r.text
    return cid, (await client.get(f"/characters/{cid}")).json()["classes"][0]["id"]


@pytest.mark.caccia(id="CB-3991", fonte="2014 · Incantesimi · Contattare Altri Piani · pag. 224", zona="regola:2014/incantesimi-A-C", voce="regola",
                    copre=["carta:2014/spells.md#Contattare Altri Piani", "GET /characters/{char_id}/spells"])
async def test_contattare_altri_piani_mostra_la_cd_15_fissa_del_ts_di_chi_lancia(client):
    cid, classe = await _pg(client, "warlock", 9, charisma=20)  # CD degli incantesimi 8 + 4 + 5 = 17
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Contattare Altri Piani", "srd_index": "contact-other-plane", "level": 5,
                                                            "attack_save": "SAVE", "class_id": classe, "is_prepared": True})
    assert r.status_code == 201, r.text
    contatto = next(s for s in (await client.get(f"/characters/{cid}/spells")).json() if s["srd_index"] == "contact-other-plane")
    # Q-2014-incantesimi-a-c-3, opzione A: chi lancia fa un TS di Intelligenza con CD 15, qualunque sia la sua CD
    assert (contatto["attack_save"], contatto["save_dc"]) == ("SAVE", 15)
