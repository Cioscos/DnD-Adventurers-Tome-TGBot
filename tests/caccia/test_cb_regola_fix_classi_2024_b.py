"""Controlli scritti dai correttori del gruppo classi-2024-b per i dubbi risolti come difetti."""
import pytest

from tests.integration.rules.test_2014_bard import _full
from tests.integration.rules.test_2014_sorcerer import _sorcerer


async def _surge(client, cid, **body):
    return await client.post(f"/characters/{cid}/wild-magic/surge", json=body)


@pytest.mark.caccia(id="CB-4511", fonte="2014 · Stregone · Impulso di Magia Selvaggia, tabella 59-60 · pag. 112; Multiclasse · Magia del Patto · pag. 164",
                    zona="regola:2014/sorcerer", voce="interazione",
                    copre=["carta:2014/classes/sorcerer.md#Impulso di Magia Selvaggia / Wild Magic Surge (Magia Selvaggia 1, pag. 111)",
                           "POST /characters/{char_id}/wild-magic/surge"])
async def test_impulso_59_60_recupera_lo_slot_del_patto_se_e_il_piu_basso(client):
    # spesi il Patto di 1° e un normale di 2°: «lo slot speso di livello più basso» è quello del Patto
    cid = await _sorcerer(client, 3, "wild_magic")
    assert (await client.post(f"/characters/{cid}/classes", json={"class_name": "warlock", "level": 1})).status_code == 201
    slots = (await _full(client, cid))["spell_slots"]
    pact = next(s for s in slots if s["is_pact"])
    second = next(s for s in slots if not s["is_pact"] and s["level"] == 2)
    for slot in (pact, second):
        assert (await client.patch(f"/characters/{cid}/spell_slots/{slot['id']}", json={"used": 1})).status_code == 200
    r = await _surge(client, cid, die=1, percentile=[59])
    assert r.status_code == 200, r.text
    assert r.json()["applied"]["slot_level"] == 1
    after = {s["id"]: s["used"] for s in (await _full(client, cid))["spell_slots"]}
    assert after[pact["id"]] == 0 and after[second["id"]] == 1

