"""Controlli scritti dal correttore del gruppo oggetti per i dubbi risolti come difetti (Q-…)."""
import pytest

from tests.integration.rules.test_feats_2014_selection import _char14
from tests.integration.rules.test_feats_take_complete import _take


@pytest.mark.caccia(id="CB-4271", fonte="2014 · Talenti · Aggressore Selvaggio / Savage Attacker · pag. 165",
                    zona="regola:2014/talenti", voce="interazione",
                    copre=["carta:2014/feats.md#Aggressore Selvaggio / Savage Attacker (pag. 165)",
                           "POST /characters/{char_id}/items/{item_id}/attack"])
async def test_aggressore_selvaggio_ritira_anche_i_dadi_del_critico(client, dadi):
    cid = (await _char14(client, "fighter", strength=10))["id"]
    assert (await _take(client, cid, "savage_attacker")).status_code == 201
    r = await client.post(f"/characters/{cid}/items", json={"name": "Spada lunga", "item_type": "weapon", "item_metadata": {
        "damage_dice": "1d8", "weapon_type": "melee", "weapon_category": "martial", "properties": []}})
    spada = max(i["id"] for i in r.json()["items"])
    dadi(1, 1, 8, 8)  # primo tiro del critico: 1 + 1; secondo tiro: 8 + 8
    r = await client.post(f"/characters/{cid}/items/{spada}/attack", json={"die": 20})
    assert r.status_code == 200, r.text
    # al critico i dadi dei danni dell'arma sono due d8: Aggressore Selvaggio li ritira tutti e tiene il risultato migliore
    assert r.json()["damage_rolls"] == [8, 8]
