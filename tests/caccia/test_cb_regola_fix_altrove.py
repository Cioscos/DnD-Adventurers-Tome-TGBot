"""Controlli delle revisioni delle correzioni regole 2026-11-24: lo stesso errore trovato altrove."""
import pytest

from tests.integration.rules.test_2014_bard import _roll_keys, _states, _use
from tests.integration.rules.test_2024_cleric_domains import _dom, _spell_rows
from tests.integration.test_magic_items import _item


@pytest.mark.caccia(id="CB-4701", fonte="2024 · Chierico · Benedizione del Dio della Guerra (nessun bonus al tiro per colpire) · pag. 77",
                    zona="regola:2024/cleric", voce="edizioni",
                    copre=["carta:2024/classes/cleric.md#Benedizione del Dio della Guerra / War God's Blessing (Guerra 6, pag. 77)",
                           "GET /characters/{char_id}/roll-options"])
async def test_la_benedizione_2024_non_offre_il_piu_dieci_del_2014(client):
    cid = await _dom(client, 6, "war")
    assert (await _use(client, cid, "cleric.war_gods_blessing", params={"spell": "shield-of-faith"})).status_code == 200
    scudo = (await _spell_rows(client, cid))["shield-of-faith"]["id"]
    assert (await client.post(f"/characters/{cid}/spells/{scudo}/use", json={"free_cast": True})).status_code == 200
    assert "war_gods_blessing" in [s["key"] for s in await _states(client, cid)]  # il minuto del privilegio
    assert "war_blessing:add" not in await _roll_keys(client, cid, "attack")
