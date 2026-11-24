"""Controlli scritti dal correttore del gruppo classi-2024-a per i dubbi risolti come difetti."""
import pytest

from tests.integration.rules.test_2014_barbarian import _ability
from tests.integration.rules.test_2024_barbarian import _barbarian, _new_turn, _rage
from tests.integration.rules.test_2024_barbarian_paths import _use

RAGE = "barbarian.rage"
TREE = "Cammino dell'Albero del Mondo"


@pytest.mark.caccia(id="CB-4471", fonte="2024 · Barbaro, Cammino dell'Albero del Mondo · Viaggio lungo l'Albero · pag. 56",
                    zona="regola:2024/barbarian", voce="regola",
                    copre=["carta:2024/classes/barbarian.md#Viaggio lungo l'Albero / Travel along the Tree (Cammino dell'Albero del Mondo 14, pag. 56)",
                           "POST /characters/{char_id}/features/{feature_key}/use"])
async def test_viaggio_lungo_l_albero_a_150_piedi_gia_all_ingresso_in_ira(client):
    cid = await _barbarian(client, 15, TREE)  # dal 15° l'Ira non va prolungata: i turni passano senza attacchi
    assert "far" in {t["key"] for t in (await _ability(client, cid, RAGE))["use_toggles"]}
    entrata = await _rage(client, cid, far=True)
    assert entrata.status_code == 200, entrata.text
    assert "45 m" in entrata.json()["message"]["it"] and "150 ft" in entrata.json()["message"]["en"]
    await _new_turn(client, cid)
    r = await _use(client, cid, "travel_along_the_tree", params={"far": True})
    assert r.status_code == 409, "la versione a 150 piedi, una volta per Ira, è già stata usata entrando in Ira"
