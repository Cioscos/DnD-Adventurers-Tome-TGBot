"""Controlli dei dubbi della zona talenti che i verificatori hanno risolto come difetti (correzione del gruppo talenti)."""
import pytest

from tests.integration.rules.test_2014_bard import _full, _roll_keys
from tests.integration.rules.test_feats_2014_selection import _char14
from tests.integration.rules.test_feats_take_complete import _take

EVASIONE = "feat.shield_master_evasion"


async def _scudo(client, cid: int) -> None:
    r = await client.post(f"/characters/{cid}/items", json={"name": "Scudo", "item_type": "shield", "item_metadata": {"ac_value": 2}})
    iid = next(i["id"] for i in r.json()["items"] if i["name"] == "Scudo")
    r = await client.patch(f"/characters/{cid}/items/{iid}", json={"is_equipped": True, "equipment_slot": "off_hand"})
    assert r.status_code == 200, r.text


async def _turno(client, cid: int) -> dict:
    r = await client.get(f"/characters/{cid}/turn-state")
    assert r.status_code == 200, r.text
    return r.json()["turn"]


@pytest.mark.caccia(id="CB-4151", fonte="2014 · Talenti · Maestro degli Scudi · pag. 169", zona="regola:2014/talenti", voce="regola",
                    copre=["carta:2014/feats.md#Maestro degli Scudi / Shield Master (pag. 169)", "PATCH /characters/{char_id}/hp",
                           "GET /characters/{char_id}/roll-options", "PATCH /characters/{char_id}/conditions"])
async def test_maestro_degli_scudi_annulla_i_danni_con_la_reazione(client):
    ch = await _char14(client, "fighter")
    cid = ch["id"]
    assert (await _take(client, cid, "shield_master")).status_code == 201
    await _scudo(client, cid)
    pieni = (await _full(client, cid))["current_hit_points"]
    assert EVASIONE in await _roll_keys(client, cid, "damage_taken")
    danno = {"op": "damage", "value": 20, "damage_type": "fire", "options": [EVASIONE]}
    r = await client.patch(f"/characters/{cid}/hp", json=danno)
    assert r.status_code == 200, r.text
    assert r.json()["current_hit_points"] == pieni
    # Testo intero del PHB 2014 IT, pag. 169: «può usare la sua reazione per non subire alcun danno»
    assert (await _turno(client, cid))["reaction_used"] is True
    assert EVASIONE not in await _roll_keys(client, cid, "damage_taken")
    assert (await client.patch(f"/characters/{cid}/hp", json=danno)).status_code == 409
    assert (await client.post(f"/characters/{cid}/turn/new")).status_code == 200
    assert EVASIONE in await _roll_keys(client, cid, "damage_taken")
    # Incapacitato: niente reazioni
    r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"incapacitated": True}})
    assert r.status_code == 200, r.text
    assert EVASIONE not in await _roll_keys(client, cid, "damage_taken")
