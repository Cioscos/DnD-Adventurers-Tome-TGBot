"""Controlli scritti dalla correzione del gruppo classi-2014-a per i dubbi risolti come difetti (Q-…)."""
import pytest

BI = "bard.bardic_inspiration"


async def _riga(client, cid, chiave) -> dict | None:
    return next((a for a in (await client.get(f"/characters/{cid}")).json()["abilities"] if a["feature_key"] == chiave), None)


@pytest.mark.caccia(id="CB-4391", fonte="2014 · Bardo · Ispirazione Superiore · pag. 54", zona="regola:2014/bard", voce="regola",
                    copre=["carta:2014/classes/bard.md#Ispirazione Superiore / Superior Inspiration (Bardo 20, pag. 54)",
                           "POST /characters/{char_id}/dice/initiative"])
async def test_ispirazione_superiore_scatta_da_sola_al_tiro_di_iniziativa(client):
    r = await client.post("/characters", json={"name": "Bardo", "rules_edition": "2014",
                                               "initial_class": {"class_name": "bard", "level": 20}})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    riga = await _riga(client, cid, BI)
    assert (await client.patch(f"/characters/{cid}/abilities/{riga['id']}", json={"uses": 0})).status_code == 200
    # privilegio passivo (Q-2014-bard-1): il giocatore non spunta nulla
    r = await client.post(f"/characters/{cid}/dice/initiative", json={"die": 8})
    assert r.status_code == 200, r.text
    assert (await _riga(client, cid, BI))["uses"] == 1


@pytest.mark.caccia(id="CB-4392", fonte="2014 · Guerriero · Superiorità in Combattimento · pag. 73", zona="regola:2014/fighter", voce="regola",
                    copre=["carta:2014/classes/fighter.md#Superiorità in Combattimento / Combat Superiority (Maestro di Battaglia 3, pag. 73)",
                           "POST /characters/{char_id}/classes/{class_id}/options/replace"])
@pytest.mark.xfail(strict=True, reason="CB-4392: difforme dal manuale, confermato (Q-2014-fighter-2, rinviato: serve un segno salvato e un cambio di UX)")
async def test_al_7_livello_si_sostituisce_una_sola_manovra(client):
    r = await client.post("/characters", json={"name": "Maestro", "rules_edition": "2014", "initial_class": {
        "class_name": "fighter", "level": 3, "subclass": "Maestro di Battaglia"}})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    full = (await client.get(f"/characters/{cid}")).json()
    scelta = next(c for c in full["pending_choices"] if c.get("group") == "maneuvers")
    r = await client.post(f"/characters/{cid}/choices/{scelta['id']}/resolve",
                          json={"kind": "class_option", "options": ["trip", "rally", "parry"]})
    assert r.status_code == 200, r.text
    classe = full["classes"][0]["id"]
    assert (await client.patch(f"/characters/{cid}/classes/{classe}", json={"level": 7})).status_code == 200
    url = f"/characters/{cid}/classes/{classe}/options/replace"
    # al 7° impara due manovre e può sostituirne una sola già nota (Q-2014-fighter-2)
    assert (await client.post(url, json={"group": "maneuvers", "old_key": "trip", "new_key": "goading"})).status_code == 200
    r = await client.post(url, json={"group": "maneuvers", "old_key": "rally", "new_key": "riposte"})
    assert r.status_code >= 400, r.status_code


@pytest.mark.caccia(id="CB-4393", fonte="2014 · Warlock · Succhiavita · pag. 119", zona="regola:2014/warlock", voce="regola",
                    copre=["carta:2014/classes/warlock.md#Succhiavita / Lifedrinker (Suppliche Occulte, livello 12, Patto della Lama, pag. 119)",
                           "POST /characters/{char_id}/attack/{attack_id}/damage"])
@pytest.mark.parametrize("carisma,extra", [(18, 4), (6, 1)])
async def test_succhiavita_aggiunge_il_danno_senza_spuntare_nulla(client, carisma, extra):
    from tests.integration.rules.test_2014_fighter_eldritch_knight import _hit
    from tests.integration.rules.test_2014_warlock_invocations import _blade, _caster
    cid = await _caster(client, 12, "lifedrinker", boon="blade", charisma=carisma, strength=10)
    lama = await _blade(client, cid)
    colpo = await _hit(client, cid, lama)
    # privilegio passivo (Q-2014-warlock-3): il danno necrotico c'è anche senza opzioni
    r = await client.post(f"/characters/{cid}/attack/{colpo['attack_id']}/damage", json={"main_rolls": [4]})
    assert r.status_code == 200, r.text
    assert r.json()["damage_bonus"] == extra
