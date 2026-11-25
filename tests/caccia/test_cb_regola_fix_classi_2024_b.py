"""Controlli scritti dai correttori del gruppo classi-2024-b per i dubbi risolti come difetti."""
import pytest

from tests.integration.rules.test_2014_bard import _ability, _full
from tests.integration.rules.test_2014_fighter_eldritch_knight import _cast, _spell
from tests.integration.rules.test_2014_sorcerer import _sorcerer

TAMED = "sorcerer.tamed_surge"


async def _surge(client, cid, **body):
    return await client.post(f"/characters/{cid}/wild-magic/surge", json=body)


@pytest.mark.caccia(id="CB-4511", fonte="2014 · Stregone · Impulso di Magia Selvaggia, tabella 59-60 · pag. 112; Multiclasse · Magia del Patto · pag. 164",
                    zona="regola:2014/sorcerer", voce="interazione",
                    copre=["carta:2014/classes/sorcerer.md#Impulso di Magia Selvaggia / Wild Magic Surge (Magia Selvaggia 1, pag. 111)",
                           "POST /characters/{char_id}/wild-magic/surge"])
async def test_impulso_59_60_recupera_lo_slot_del_patto_se_e_il_piu_basso(client):
    # spesi il Patto di 1° e un normale di 2°: «lo slot speso di livello più basso» è quello del Patto
    cid = await _sorcerer(client, 3, "wild_magic")
    assert (await client.post(f"/characters/{cid}/classes", json={"class_name": "warlock", "level": 1})).status_code == 201
    slots = (await _full(client, cid))["spell_slots"]
    pact = next(s for s in slots if s["is_pact"])
    second = next(s for s in slots if not s["is_pact"] and s["level"] == 2)
    for slot in (pact, second):
        assert (await client.patch(f"/characters/{cid}/spell_slots/{slot['id']}", json={"used": 1})).status_code == 200
    r = await _surge(client, cid, die=1, percentile=[59])
    assert r.status_code == 200, r.text
    assert r.json()["applied"]["slot_level"] == 1
    after = {s["id"]: s["used"] for s in (await _full(client, cid))["spell_slots"]}
    assert after[pact["id"]] == 0 and after[second["id"]] == 1


@pytest.mark.caccia(id="CB-4512", fonte="2024 · Stregone · Magia Selvaggia, Impulso Domato · pag. 150 (subito dopo un incantesimo da stregone lanciato con uno slot)",
                    zona="regola:2024/sorcerer", voce="regola",
                    copre=["carta:2024/classes/sorcerer.md#Impulso Domato / Tamed Surge (Magia Selvaggia 18, pag. 150)",
                           "POST /characters/{char_id}/wild-magic/surge", "POST /characters/{char_id}/spells/{spell_id}/use"])
async def test_impulso_domato_solo_dopo_un_lancio_con_slot(client):
    r = await client.post("/characters", json={"name": "Stregone", "rules_edition": "2024", "initial_class": {
        "class_name": "sorcerer", "level": 18, "subclass": "Magia Selvaggia"}})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    r = await _surge(client, cid, tamed=True, percentile=[53])  # nessun lancio: niente azione extra scelta a piacere
    assert r.status_code == 409, r.text[:200]
    assert (await _ability(client, cid, TAMED))["uses"] == 1
    spell = await _spell(client, cid, "Ragnatela", 2)
    assert (await _cast(client, cid, spell, slot_level=2)).status_code == 200
    r = await _surge(client, cid, tamed=True, percentile=[53])
    assert r.status_code == 200, r.text[:200]
    assert r.json()["applied"]["extra_action"] is True and (await _ability(client, cid, TAMED))["uses"] == 0


@pytest.mark.caccia(id="CB-4513", fonte="2024 · Guerriero · Stile di Combattimento · pag. 91 (a ogni livello da guerriero si può sostituire il talento scelto)",
                    zona="regola:2024/fighter", voce="limiti",
                    copre=["carta:2024/classes/fighter.md#Stile di Combattimento / Fighting Style (Guerriero 1, pag. 91)",
                           "POST /characters/{char_id}/classes/{class_id}/options/replace", "PATCH /characters/{char_id}/classes/{class_id}"])
async def test_stile_di_combattimento_2024_una_sostituzione_per_livello_guadagnato(client):
    r = await client.post("/characters", json={"name": "Guerriero", "rules_edition": "2024",
                                               "initial_class": {"class_name": "fighter", "level": 1}})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    scheda = (await client.get(f"/characters/{cid}")).json()
    scelta = next(c for c in scheda["pending_choices"] if c.get("group") == "fighting_style")
    r = await client.post(f"/characters/{cid}/choices/{scelta['id']}/resolve", json={"kind": "class_option", "options": ["defense"]})
    assert r.status_code == 200, r.text
    classe = scheda["classes"][0]["id"]
    url = f"/characters/{cid}/classes/{classe}/options/replace"
    assert (await client.post(url, json={"group": "fighting_style", "old_key": "defense", "new_key": "archery"})).status_code == 409
    assert (await client.patch(f"/characters/{cid}/classes/{classe}", json={"level": 2})).status_code == 200
    assert (await client.post(url, json={"group": "fighting_style", "old_key": "defense", "new_key": "archery"})).status_code == 200
    r = await client.post(url, json={"group": "fighting_style", "old_key": "archery", "new_key": "dueling"})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "replace_on_level_up", r.text[:200]
    assert (await client.patch(f"/characters/{cid}/classes/{classe}", json={"level": 3})).status_code == 200
    assert (await client.post(url, json={"group": "fighting_style", "old_key": "archery", "new_key": "dueling"})).status_code == 200


@pytest.mark.caccia(id="CB-4514", fonte="2024 · Guerriero · Maestro di Battaglia, Superiorità in Combattimento · pag. 93 (a ogni nuova scelta di manovre se ne sostituisce una)",
                    zona="regola:2024/fighter", voce="limiti",
                    copre=["carta:2024/classes/fighter.md#Superiorità in Combattimento / Combat Superiority (Maestro di Battaglia 3, pag. 93)",
                           "POST /characters/{char_id}/classes/{class_id}/options/replace", "PATCH /characters/{char_id}/classes/{class_id}"])
async def test_manovre_2024_una_sostituzione_quando_se_ne_imparano_di_nuove(client):
    r = await client.post("/characters", json={"name": "Guerriero", "rules_edition": "2024", "initial_class": {
        "class_name": "fighter", "level": 6, "subclass": "Maestro di Battaglia"}})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    scheda = (await client.get(f"/characters/{cid}")).json()
    scelta = next(c for c in scheda["pending_choices"] if c.get("group") == "maneuvers")
    r = await client.post(f"/characters/{cid}/choices/{scelta['id']}/resolve",
                          json={"kind": "class_option", "options": ["trip", "rally", "parry"]})
    assert r.status_code == 200, r.text
    classe = scheda["classes"][0]["id"]
    url = f"/characters/{cid}/classes/{classe}/options/replace"
    assert (await client.post(url, json={"group": "maneuvers", "old_key": "trip", "new_key": "goading"})).status_code == 409  # al 6° nessuna nuova
    assert (await client.patch(f"/characters/{cid}/classes/{classe}", json={"level": 7})).status_code == 200
    assert (await client.post(url, json={"group": "maneuvers", "old_key": "trip", "new_key": "goading"})).status_code == 200
    r = await client.post(url, json={"group": "maneuvers", "old_key": "rally", "new_key": "menacing"})
    assert r.status_code == 409, r.text[:200]


async def _maestro_mago(client, *manovre) -> tuple[int, int]:
    """Maestro di Battaglia 2024 di 3° con un livello da mago e Dardo di Fuoco (attacco con incantesimo)."""
    r = await client.post("/characters", json={"name": "Guerriero", "rules_edition": "2024", "initial_class": {
        "class_name": "fighter", "level": 3, "subclass": "Maestro di Battaglia"}})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    scelta = next(c for c in r.json()["pending_choices"] if c.get("group") == "maneuvers")
    r = await client.post(f"/characters/{cid}/choices/{scelta['id']}/resolve", json={"kind": "class_option", "options": list(manovre)})
    assert r.status_code == 200, r.text
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "wizard", "level": 1})
    assert r.status_code == 201, r.text
    mago = next(c["id"] for c in r.json()["classes"] if c["class_name"] == "wizard")
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Dardo di Fuoco", "level": 0, "attack_save": "ATK", "damage_dice": "1d10",
                                                              "damage_type": "fire", "casting_time": "1 azione", "class_id": mago})
    assert r.status_code == 201, r.text
    return cid, r.json()["id"]


async def _opzioni_attacco(client, cid, spell_id) -> set[str]:
    r = await client.get(f"/characters/{cid}/roll-options", params={"roll": "attack", "spell_id": spell_id})
    assert r.status_code == 200, r.text
    return {o["key"] for o in r.json()}


@pytest.mark.caccia(id="CB-4515", fonte="2024 · Guerriero · Maestro di Battaglia, Attacco Preciso e Attacco con Finta · pag. 95 (un tiro per colpire, non solo con arma); Glossario, Tiro per Colpire · pag. 361",
                    zona="regola:2024/fighter", voce="interazione",
                    copre=["carta:2024/classes/fighter.md#Attacco Preciso / Precision Attack (Manovra, Maestro di Battaglia 3, pag. 95)",
                           "carta:2024/classes/fighter.md#Attacco con Finta / Feinting Attack (Manovra, Maestro di Battaglia 3, pag. 95)",
                           "POST /characters/{char_id}/spells/{spell_id}/attack", "POST /characters/{char_id}/last-roll/options",
                           "GET /characters/{char_id}/roll-options"])
async def test_attacco_preciso_e_finta_valgono_anche_per_l_attacco_con_incantesimo(client):
    cid, dardo = await _maestro_mago(client, "precision", "feinting", "menacing")
    r = await client.post(f"/characters/{cid}/spells/{dardo}/attack", json={"die": 2})
    assert r.status_code == 200, r.text
    r = await client.post(f"/characters/{cid}/last-roll/options", json={"options": ["fighter.maneuver_precision"]})
    assert r.status_code == 200, r.text[:200]
    assert (await _ability(client, cid, "fighter.superiority_dice"))["uses"] == 3
    assert (await client.post(f"/characters/{cid}/features/fighter.maneuver_feinting/use", json={})).status_code == 200
    assert "fighter.maneuver_feinting_strike" in await _opzioni_attacco(client, cid, dardo)
    r = await client.post(f"/characters/{cid}/spells/{dardo}/attack", json={"dice": [3, 15], "options": ["fighter.maneuver_feinting_strike"]})
    assert r.status_code == 200, r.text[:200]
    assert r.json()["mode"] == "advantage" and r.json()["to_hit_die"] == 15


@pytest.mark.caccia(id="CB-4516", fonte="2024 · Guerriero · Maestro di Battaglia, Attacco Disarmante, Colpo Distraente, Attacco Adescante, Attacco con Manovra, Attacco Minaccioso · pag. 95 (se si colpisce, senza limite all'arma)",
                    zona="regola:2024/fighter", voce="interazione",
                    copre=["carta:2024/classes/fighter.md#Attacco Minaccioso / Menacing Attack (Manovra, Maestro di Battaglia 3, pag. 95)",
                           "carta:2024/classes/fighter.md#Attacco Disarmante / Disarming Attack (Manovra, Maestro di Battaglia 3, pag. 95)",
                           "GET /characters/{char_id}/roll-options"])
@pytest.mark.xfail(strict=True, reason="CB-4516: difforme dal manuale, confermato (rinviato: il flusso degli attacchi con incantesimo non ha una fase after_hit)")
async def test_le_manovre_dopo_un_colpo_valgono_anche_per_l_attacco_con_incantesimo(client):
    cid, dardo = await _maestro_mago(client, "precision", "disarming", "menacing")
    assert {"fighter.maneuver_disarming", "fighter.maneuver_menacing"} <= await _opzioni_attacco(client, cid, dardo)


@pytest.mark.caccia(id="CB-4517", fonte="decisione D-044 (tests/caccia/decisioni.md): si paga anche con uno slot di 2° o più; 2024 · Warlock · Patrono Fatato, Fuga Velata e Passi del Fatato · pag. 159; Lanciare senza slot · pag. 235-236",
                    zona="regola:2024/warlock", voce="regola",
                    copre=["carta:2024/classes/warlock.md#Fuga Velata / Misty Escape (Patrono Fatato 6, pag. 159)",
                           "carta:2024/classes/warlock.md#Passi del Fatato / Steps of the Fey (Patrono Fatato 3, pag. 159)",
                           "carta:2024/general.md#Lanciare senza slot / Casting Without Slots (pag. 235-236)",
                           "POST /characters/{char_id}/features/{feature_key}/use"])
async def test_fuga_velata_senza_passi_del_fatato_si_paga_con_uno_slot(client):
    # la Fuga cambia il tempo di lancio di Passo Velato, non lo rende gratuito: senza usi di Passi del Fatato lo paga uno slot di 2°+
    from tests.integration.rules.test_2014_paladin import _new_turn
    from tests.integration.rules.test_2014_warlock import _pact_slots
    from tests.integration.rules.test_2024_warlock_patrons import ESCAPE, STEPS, _make
    cid = await _make(client, "archfey", 6, charisma=10)  # Carisma 10: un solo uso di Passi del Fatato
    use = f"/characters/{cid}/features/{ESCAPE}/use"
    assert (await client.post(use, json={"params": {"effect": "plain"}})).status_code == 200
    assert (await _ability(client, cid, STEPS))["uses"] == 0
    assert (await _ability(client, cid, ESCAPE)).get("spends_left") != 0  # il «Usa» della pagina Turno resta acceso
    await _new_turn(client, cid)
    r = await client.post(use, json={"params": {"effect": "plain", "pay": "slot", "slot_level": "3"}})
    assert r.status_code == 200, r.text
    assert [s["used"] for s in await _pact_slots(client, cid)] == [1]
    assert (await _ability(client, cid, STEPS))["uses"] == 0
