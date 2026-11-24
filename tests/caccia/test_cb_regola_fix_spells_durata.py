"""Controlli scritti dai correttori del gruppo spells-durata per i dubbi risolti come difetti."""
import pytest

from tests.integration.rules.test_2014_bard import _add_spell, _full, _roll_keys
from tests.integration.rules.test_2024_bard import VALOR, _bard24
from tests.integration.rules.test_2024_bard_lore_valor import _sword


@pytest.mark.caccia(id="CB-3911", fonte="2024 · Bardo · Collegio del Valore · Magia da Battaglia · pag. 67; Regole generali · Tempo di lancio · pag. 236",
                    zona="regola:2024/bard", voce="regola",
                    copre=["carta:2024/classes/bard.md#Magia da Battaglia / Battle Magic (Collegio del Valore 14, pag. 67)",
                           "carta:2024/general.md#Tempo di lancio / Casting Time (pag. 236)",
                           "POST /characters/{char_id}/spells/{spell_id}/use", "GET /characters/{char_id}/roll-options"])
async def test_magia_da_battaglia_non_segue_un_lancio_rituale(client):
    # Q-2024-bard-2: il rituale (+10 minuti) è un tempo di lancio lungo, non il tempo di lancio di un'azione
    cid = await _bard24(client, 14, VALOR)
    sword = await _sword(client, cid)
    bard_class = (await _full(client, cid))["classes"][0]["id"]
    spell = (await _add_spell(client, cid, "Rituale da un'azione", 1, casting_time="1 azione", is_ritual=True,
                              is_prepared=True, class_id=bard_class)).json()
    r = await client.post(f"/characters/{cid}/spells/{spell['id']}/use", json={"as_ritual": True})
    assert r.status_code == 200, r.text
    assert "bard.battle_magic" not in await _roll_keys(client, cid, "attack", item_id=sword)
