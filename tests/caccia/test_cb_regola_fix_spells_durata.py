"""Controlli scritti dai correttori del gruppo spells-durata per i dubbi risolti come difetti."""
import pytest

from tests.caccia.test_cb_regola_2014_incantesimi_d_f import _impara, _pg
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


@pytest.mark.caccia(id="CB-3912", fonte="2014 · Incantesimi · Deflagrazione Occulta (un tiro per colpire per ogni raggio) · pag. 229",
                    zona="regola:2014/incantesimi-D-F", voce="regola",
                    copre=["carta:2014/spells.md#Deflagrazione Occulta", "POST /characters/{char_id}/spells/{spell_id}/attack"])
@pytest.mark.xfail(strict=True, reason="CB-3912: difforme dal manuale, rinviato (un tiro e un danno per raggio cambiano la UX del lancio)")
async def test_deflagrazione_occulta_tira_per_colpire_una_volta_per_raggio(client, dadi):
    # Q-2014-incantesimi-d-f-1: «effettuando un tiro per colpire separato per ogni raggio», anche sullo stesso bersaglio
    cid = await _pg(client, "warlock", 5)  # due raggi
    sid = await _impara(client, cid, "eldritch-blast")
    dadi(20, 1)  # il primo raggio fa 20 naturale, il secondo 1: nessuno dei due decide per l'altro
    r = await client.post(f"/characters/{cid}/spells/{sid}/attack", json={})
    assert r.status_code == 200, r.text
    assert sorted(r.json()["dice"]) == [1, 20]  # oggi un solo d20 vale per tutti i raggi: critico o mancato tutto insieme