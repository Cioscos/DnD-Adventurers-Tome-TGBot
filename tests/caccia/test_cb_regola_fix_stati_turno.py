"""Controlli scritti dal correttore del gruppo stati-turno per i dubbi risolti come difetti."""
import pytest

from tests.caccia.test_cb_regola_2014_barbarian import _in_ira
from tests.caccia.test_cb_regola_2014_bard import BI, _riga
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, seed_session, setup_full_encounter
from tests.integration._telegram_stub import install_fake_telegram
from tests.integration.rules.test_2014_barbarian import _barbarian, _hit, _rage, _states
from tests.integration.rules.test_2014_bard import _roll_keys, _sword
from tests.integration.rules.test_2014_fighter import _fighter
from tests.integration.rules.test_2014_rogue_thief import _reflexes_encounter


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


@pytest.mark.caccia(id="CB-4193", fonte="2024 · Bardo · Ispirazione Superiore · pag. 61", zona="regola:2024/bard", voce="interazione",
                    copre=["carta:2024/classes/bard.md#Ispirazione Superiore / Superior Inspiration (Bardo 18, pag. 61)",
                           "POST /sessions/{session_id}/encounter/start"])
async def test_ispirazione_superiore_anche_con_l_iniziativa_tirata_dal_master(client, test_session_factory, monkeypatch, come_utente):
    install_fake_telegram(monkeypatch)
    sid, cid = await seed_session(test_session_factory)
    come_utente(PLAYER_ID)
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    assert (await client.patch(f"/characters/{cid}/ability_scores/charisma", json={"value": 16})).status_code == 200
    assert (await client.post(f"/characters/{cid}/classes", json={"class_name": "bard", "level": 18, "hit_die": 8})).status_code == 201
    riga = await _riga(client, cid, BI)
    assert riga["max_uses"] == 3
    assert (await client.patch(f"/characters/{cid}/abilities/{riga['id']}", json={"uses": 0})).status_code == 200
    come_utente(GM_ID)
    assert (await client.post(f"/sessions/{sid}/encounter", json={"mode": "full"})).status_code == 201
    r = await client.post(f"/sessions/{sid}/encounter/combatants",
                          json={"name": "Goblin", "count": 1, "initiative_mod": 2, "max_hp": 7, "ac": 15})
    assert r.status_code in (200, 201), r.text
    r = await client.post(f"/sessions/{sid}/encounter/start", json={"auto_roll_missing": True})
    assert r.status_code == 200, r.text
    come_utente(PLAYER_ID)
    # il tiro d'ufficio è il tiro di iniziativa del bardo: gli usi tornano a due come quando tira lui
    assert (await _riga(client, cid, BI))["uses"] == 2


@pytest.mark.caccia(id="CB-4194", fonte="2014 · Ladro · Azione Scaltra · pag. 78; Combattere · Sorpresa e Azioni Bonus · pag. 189-190",
                    zona="regola:2014/rogue", voce="interazione",
                    copre=["carta:2014/classes/rogue.md#Azione Scaltra / Cunning Action (Ladro 2, pag. 78)",
                           "carta:2014/general.md#Sorpresa / Surprise (pag. 189)",
                           "carta:2014/general.md#Azioni Bonus / Bonus Actions (pag. 189-190)",
                           "PATCH /sessions/{session_id}/encounter/combatants/{combatant_id}",
                           "POST /characters/{char_id}/features/{feature_key}/use"])
async def test_da_sorpreso_il_ladro_non_usa_l_azione_scaltra(client, test_session_factory, come_utente):
    # la sorpresa toglie l'azione nel primo turno, e ciò che impedisce le azioni impedisce anche le azioni bonus
    _sid, cid, _live = await _reflexes_encounter(client, test_session_factory, surprised=True, level=2, subclass=None)
    come_utente(PLAYER_ID)
    r = await client.post(f"/characters/{cid}/features/rogue.cunning_action/use", json={"params": {"action": "dash"}})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "incapacitated", r.text[:200]
    assert (await client.get(f"/characters/{cid}/turn-state")).json()["turn"]["bonus_used"] is False


@pytest.mark.caccia(id="CB-4195", fonte="2014 · Ranger · Sterminatore di Nemici · pag. 105", zona="regola:2014/ranger", voce="interazione",
                    copre=["carta:2014/classes/ranger.md#Sterminatore di Nemici / Foe Slayer (Ranger 20, pag. 105)",
                           "POST /sessions/{session_id}/encounter/next-turn", "POST /sessions/{session_id}/encounter/prev-turn",
                           "GET /characters/{char_id}/roll-options", "POST /characters/{char_id}/items/{item_id}/attack"])
async def test_sterminatore_di_nemici_solo_nei_turni_del_ranger(client, test_session_factory, monkeypatch, come_utente):
    # «una volta per turno, vale per un solo attacco a turno del ranger»: nel turno di un nemico (attacco di opportunità) non c'è
    install_fake_telegram(monkeypatch)
    sid, _ = await setup_full_encounter(client, test_session_factory)  # ordine: PG, goblin, goblin
    come_utente(GM_ID)
    cid = (await client.post(f"/sessions/{sid}/encounter/start", json={})).json()["combatants"][0]["character_id"]
    come_utente(PLAYER_ID)
    assert (await client.patch(f"/characters/{cid}/ability_scores/wisdom", json={"value": 16})).status_code == 200
    assert (await client.post(f"/characters/{cid}/classes", json={"class_name": "ranger", "level": 20, "hit_die": 10})).status_code == 201
    spada = await _sword(client, cid)
    sterminatore = {"ranger.foe_slayer_attack", "ranger.foe_slayer_attack_late", "ranger.foe_slayer_damage"}
    assert sterminatore <= set(await _roll_keys(client, cid, "attack", item_id=spada))  # nel suo turno
    come_utente(GM_ID)
    assert (await client.post(f"/sessions/{sid}/encounter/next-turn")).status_code == 200  # turno del goblin
    come_utente(PLAYER_ID)
    assert not sterminatore & set(await _roll_keys(client, cid, "attack", item_id=spada))
    r = await client.post(f"/characters/{cid}/items/{spada}/attack",
                          json={"die": 10, "options": ["ranger.foe_slayer_attack"], "defer_damage": True, "confirm_extra_attack": True})
    assert r.status_code == 409, r.text[:200]
    come_utente(GM_ID)
    assert (await client.post(f"/sessions/{sid}/encounter/prev-turn")).status_code == 200  # il GM torna al turno del ranger
    come_utente(PLAYER_ID)
    assert sterminatore <= set(await _roll_keys(client, cid, "attack", item_id=spada))
