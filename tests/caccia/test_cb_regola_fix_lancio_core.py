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


@pytest.mark.caccia(id="CB-3992", fonte="2014 · Incantesimi · Vincolo di Interdizione · pag. 289", zona="regola:2014/incantesimi-S-Z", voce="regola",
                    copre=["carta:2014/spells.md#Vincolo di Interdizione", "POST /characters/{char_id}/spells/{spell_id}/use"])
@pytest.mark.parametrize("su_di_se", [True, False], ids=["su_di_se", "senza_bersagli"])
async def test_vincolo_di_interdizione_non_si_lancia_su_chi_lo_lancia(client, su_di_se):
    cid, classe = await _pg(client, "cleric", 3)
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Vincolo di Interdizione", "srd_index": "warding-bond", "level": 2,
                                                            "class_id": classe, "is_prepared": True})
    assert r.status_code == 201, r.text
    corpo = {"slot_level": 2, **({"targets": [cid]} if su_di_se else {})}
    r = await client.post(f"/characters/{cid}/spells/{r.json()['id']}/use", json=corpo)
    # Q-2014-incantesimi-s-z-1, opzione A: il vincolo lega chi lancia a un'altra creatura, che riceve +1 CA e TS e resistenza
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_target", r.text
    scheda = (await client.get(f"/characters/{cid}")).json()
    assert not any(s["key"] == "spell:warding_bond" for s in scheda["active_states"] or [])
    assert next(s for s in scheda["spell_slots"] if s["level"] == 2)["used"] == 0  # rifiutato prima di spendere lo slot
