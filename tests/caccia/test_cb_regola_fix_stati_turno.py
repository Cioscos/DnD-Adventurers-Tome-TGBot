"""Controlli scritti dal correttore del gruppo stati-turno per i dubbi risolti come difetti."""
import pytest

from tests.caccia.test_cb_regola_2014_barbarian import _in_ira
from tests.integration.rules.test_2014_barbarian import _barbarian, _hit, _rage, _states
from tests.integration.rules.test_2014_fighter import _fighter


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


@pytest.mark.caccia(id="CB-4192", fonte="2014 · Regole di gioco · Vantaggio e Svantaggio · pag. 173; Guerriero · Indomito · pag. 72",
                    zona="regola:2014/generali", voce="interazione",
                    copre=["carta:2014/general.md#Vantaggio e Svantaggio / Advantage and Disadvantage (pag. 173)",
                           "carta:2014/classes/fighter.md#Indomito / Indomitable (Guerriero 9, pag. 72)",
                           "POST /characters/{char_id}/saving_throws/{ability}/roll", "POST /characters/{char_id}/last-roll/options"])
@pytest.mark.parametrize("svantaggio", ["trattenuto", "scelto"])
async def test_indomito_con_svantaggio_ritira_un_solo_d20(client, dadi, svantaggio):
    cid = await _fighter(client, 9)
    if svantaggio == "trattenuto":  # Trattenuto: svantaggio ai TS di Destrezza, messo dal server
        r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"restrained": True}})
        assert r.status_code == 200, r.text
    corpo = {"dice": [4, 15]} if svantaggio == "trattenuto" else {"mode": "disadvantage", "dice": [4, 15]}
    r = await client.post(f"/characters/{cid}/saving_throws/dexterity/roll", json=corpo)
    assert r.status_code == 200, r.text
    assert (r.json()["die"], r.json()["mode"]) == (4, "disadvantage")
    dadi(7)  # un secondo d20 nuovo, se il server ritirasse tutto il tiro
    r = await client.post(f"/characters/{cid}/last-roll/options", json={"options": ["fighter.indomitable"], "dice": [18]})
    assert r.status_code == 200, r.text
    # si ritira il 4: il 15 resta e con lo svantaggio vale il più basso fra 18 e 15
    assert (r.json()["die"], r.json()["mode"]) == (15, "disadvantage"), r.json()
