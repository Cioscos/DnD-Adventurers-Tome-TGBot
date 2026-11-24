"""Controlli scritti dal correttore del gruppo stati-turno per i dubbi risolti come difetti."""
import pytest

from tests.caccia.test_cb_regola_2014_barbarian import _in_ira
from tests.integration.rules.test_2014_barbarian import _barbarian, _hit, _rage, _states


@pytest.mark.caccia(id="CB-4191", fonte="2014 · Barbaro · Ira · pag. 48", zona="regola:2014/barbarian", voce="regola",
                    copre=["carta:2014/classes/barbarian.md#Ira / Rage (Barbaro 1, pag. 48)",
                           "POST /characters/{char_id}/turn/new", "PATCH /characters/{char_id}/hp"])
async def test_fuori_scontro_il_danno_subito_tiene_l_ira_per_un_turno_solo(client):
    cid = await _barbarian(client, 2)
    assert (await _rage(client, cid)).status_code == 200
    await _hit(client, cid, 1)
    assert (await client.post(f"/characters/{cid}/turn/new")).status_code == 200  # ha subito danni: l'ira resta
    assert _in_ira(await _states(client, cid))
    # il danno di prima è già stato contato: un turno senza attacchi né nuovi danni chiude l'ira
    assert (await client.post(f"/characters/{cid}/turn/new")).status_code == 200
    assert not _in_ira(await _states(client, cid))
