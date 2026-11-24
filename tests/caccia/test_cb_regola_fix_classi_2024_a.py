"""Controlli scritti dal correttore del gruppo classi-2024-a per i dubbi risolti come difetti."""
import pytest

from tests.integration.rules.test_2014_barbarian import _ability, _keys, _weapon
from tests.integration.rules.test_2024_barbarian import _barbarian, _new_turn, _rage
from tests.integration.rules.test_2024_barbarian_paths import _use
from tests.integration.rules.test_2024_barbarian_strike import _damage, _deferred
from tests.integration.rules.test_2024_bard import _bard24

RAGE = "barbarian.rage"
RECKLESS = "barbarian.reckless_attack"
FRENZY = "barbarian.frenzy"
TREE = "Cammino dell'Albero del Mondo"
BERSERKER = "Cammino del Berserker"


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


@pytest.mark.caccia(id="CB-4472", fonte="2024 · Barbaro, Cammino del Berserker · Frenesia · pag. 54; Barbaro · Attacco Irruento · pag. 52",
                    zona="regola:2024/barbarian", voce="interazione",
                    copre=["carta:2024/classes/barbarian.md#Frenesia / Frenzy (Cammino del Berserker 3, pag. 54)",
                           "carta:2024/classes/barbarian.md#Attacco Irruento / Reckless Attack (Barbaro 2, pag. 52)",
                           "POST /characters/{char_id}/items/{item_id}/attack", "POST /characters/{char_id}/attack/{attack_id}/damage"])
async def test_frenesia_solo_se_l_attacco_irruento_e_dichiarato_in_ira(client):
    cid = await _barbarian(client, 5, BERSERKER, strength=16)
    ascia = await _weapon(client, cid)
    await _new_turn(client, cid)
    await _deferred(client, cid, ascia, options=[RECKLESS], dice=[1, 1])  # Irruento senza Ira: mancato
    assert (await _rage(client, cid)).status_code == 200
    colpo = await _deferred(client, cid, ascia, dice=[15, 15])  # Attacco Extra, ora in Ira
    assert FRENZY not in await _keys(client, cid, "attack", item_id=ascia)
    r = await _damage(client, cid, colpo, [FRENZY])
    assert r.status_code == 409, "l'Attacco Irruento è stato usato prima che l'Ira fosse attiva: niente Frenesia"


@pytest.mark.caccia(id="CB-4473", fonte="2024 · Bardo · Segreti Magici · pag. 61", zona="regola:2024/bard", voce="regola",
                    copre=["carta:2024/classes/bard.md#Segreti Magici / Magical Secrets (Bardo 10, pag. 61)",
                           "GET /characters/{char_id}"])
@pytest.mark.parametrize("livello", [10, 20])
async def test_segreti_magici_2024_e_un_permesso_non_una_scelta_da_fare(client, livello):
    cid = await _bard24(client, livello)
    full = (await client.get(f"/characters/{cid}")).json()
    assert "bard.magical_secrets" in {a["feature_key"] for a in full["abilities"]}
    assert not [c for c in full["pending_choices"] if c.get("group") == "magical_secrets"],         "i nuovi preparati possono venire dalle quattro liste: nessuna scelta obbligatoria"
