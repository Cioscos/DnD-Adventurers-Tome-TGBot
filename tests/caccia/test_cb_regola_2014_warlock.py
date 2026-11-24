"""Controlli della zona regola:2014/warlock."""
import pytest

from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, setup_full_encounter
from tests.integration._telegram_stub import install_fake_telegram
from tests.integration.conftest import TEST_USER_ID
from tests.integration.rules.test_2014_bard import _ability, _full, _use
from tests.integration.rules.test_2014_paladin import _new_turn, _rest
from tests.integration.rules.test_2014_warlock import _choice, _pact_slots, _resolve, _set_used, _warlock
from tests.integration.rules.test_2014_warlock_invocations import _caster, _spells_by_index
from tests.integration.rules.test_2024_warlock_patrons import _make as _make24

LUCK = "warlock.dark_ones_own_luck"


@pytest.mark.caccia(id="CB-2061", fonte="2014 · Warlock · Fortuna dell'Oscuro · pag. 117", zona="regola:2014/warlock", voce="regola",
                    copre=["carta:2014/classes/warlock.md#Fortuna dell'Oscuro / Dark One's Own Luck (Immondo 6, pag. 117)",
                           "POST /characters/{char_id}/last-roll/options"])
@pytest.mark.parametrize("tiro", ["initiative", "death_save"])
@pytest.mark.xfail(strict=True, reason="CB-2061: difforme dal manuale, confermato")
async def test_fortuna_dell_oscuro_vale_su_iniziativa_e_ts_contro_morte(client, tiro):
    cid = await _warlock(client, 6, "fiend", charisma=16)
    if tiro == "initiative":
        r = await client.post(f"/characters/{cid}/dice/initiative", json={"die": 5})
    else:
        await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 0})
        r = await client.post(f"/characters/{cid}/death_saves/roll", json={"die": 5})
    assert r.status_code == 200, r.text
    r = await client.post(f"/characters/{cid}/last-roll/options", json={"options": [LUCK]})
    assert r.status_code == 200, r.text
    assert (await _ability(client, cid, LUCK))["uses"] == 0


@pytest.mark.caccia(id="CB-2062", fonte="2014 · Warlock · Delirio Oscuro · pag. 117", zona="regola:2014/warlock", voce="regola",
                    copre=["carta:2014/classes/warlock.md#Delirio Oscuro / Dark Delirium (Signore Fatato 14, pag. 117)",
                           "POST /characters/{char_id}/target-effects", "PATCH /characters/{char_id}/concentration"])
@pytest.mark.xfail(strict=True, reason="CB-2062: difforme dal manuale, confermato")
async def test_delirio_oscuro_sul_bersaglio_finisce_con_la_concentrazione(client, test_session_factory, monkeypatch):
    install_fake_telegram(monkeypatch)
    sid, _ = await setup_full_encounter(client, test_session_factory)
    r = await client.post(f"/sessions/{sid}/encounter/start", json={})
    pc, g1, _g2 = r.json()["combatants"]
    cid = pc["character_id"]
    as_user(PLAYER_ID)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "warlock", "level": 14, "subclass": "Il Signore Fatato"})
    assert r.status_code in (200, 201), r.text
    assert (await _use(client, cid, "warlock.dark_delirium", params={"mode": "frightened"})).status_code == 200
    r = await client.post(f"/characters/{cid}/target-effects", json={"combatant_id": g1["id"], "effect_key": "warlock.dark_delirium"})
    assert r.status_code == 200, r.text
    as_user(GM_ID)
    live = (await client.get(f"/sessions/{sid}/live")).json()
    [save] = next(c for c in live["encounter"]["combatants"] if c["id"] == g1["id"])["pending_saves"]
    r = await client.post(f"/sessions/{sid}/encounter/pending-saves/{save['id']}/resolve", json={"passed": False})
    assert r.status_code == 200, r.text
    live = (await client.get(f"/sessions/{sid}/live")).json()
    assert next(c for c in live["encounter"]["combatants"] if c["id"] == g1["id"])["conditions"].get("frightened")
    as_user(PLAYER_ID)
    assert (await client.patch(f"/characters/{cid}/concentration", json={"spell_id": None})).status_code == 200
    as_user(GM_ID)
    live = (await client.get(f"/sessions/{sid}/live")).json()
    assert not next(c for c in live["encounter"]["combatants"] if c["id"] == g1["id"])["conditions"].get("frightened")


@pytest.mark.caccia(id="CB-2063", fonte="2014 · Warlock · Arcanum Mistico · pag. 116", zona="regola:2014/warlock", voce="regola",
                    copre=["carta:2014/classes/warlock.md#Arcanum Mistico / Mystic Arcanum (Warlock 11, pag. 116)",
                           "GET /characters/{char_id}"])
@pytest.mark.xfail(strict=True, reason="CB-2063: difforme dal manuale, confermato")
async def test_arcanum_mistico_si_sceglie_dalla_lista_del_warlock(client):
    full = await _full(client, await _warlock(client, 17))
    liste = {grado: _choice(full, f"arcanum_{grado}")["spell_pick"]["list"] for grado in (6, 7, 8, 9)}
    assert liste == {6: "warlock", 7: "warlock", 8: "warlock", 9: "warlock"}


@pytest.mark.caccia(id="CB-2064", fonte="2014 · Warlock · Patto della Catena · pag. 115", zona="regola:2014/warlock", voce="regola",
                    copre=["carta:2014/classes/warlock.md#Patto della Catena / Pact of the Chain (Warlock 3, pag. 115)",
                           "POST /characters/{char_id}/spells/{spell_id}/use"])
@pytest.mark.xfail(strict=True, reason="CB-2064: difforme dal manuale, confermato")
async def test_patto_della_catena_lancia_trova_famiglio_come_rituale(client):
    cid = await _warlock(client, 3)
    assert (await _resolve(client, cid, "pact_boon", ["chain"])).status_code == 200
    famiglio = (await _spells_by_index(client, cid))["find-familiar"]
    prima = await _pact_slots(client, cid)
    r = await client.post(f"/characters/{cid}/spells/{famiglio['id']}/use", json={"as_ritual": True})
    assert r.status_code == 200, r.text
    assert await _pact_slots(client, cid) == prima


@pytest.mark.caccia(id="CB-2065", fonte="2014 · Warlock · Libro degli Antichi Segreti · pag. 118", zona="regola:2014/warlock", voce="regola",
                    copre=["carta:2014/classes/warlock.md#Libro degli Antichi Segreti / Book of Ancient Secrets (Suppliche Occulte, Patto del Tomo, pag. 118)",
                           "POST /characters/{char_id}/spells/{spell_id}/use"])
@pytest.mark.xfail(strict=True, reason="CB-2065: difforme dal manuale, confermato")
async def test_i_rituali_del_libro_si_lanciano_solo_come_rituali(client):
    cid = await _caster(client, 3, "book_of_ancient_secrets", boon="tome")
    pick = _choice(await _full(client, cid), "book_rituals")
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Individuazione del magico", "level": 1, "is_ritual": True,
                                                            "pick_id": pick["id"], "casting_time": "1 azione"})
    assert r.status_code == 201, r.text
    [patto] = await _pact_slots(client, cid)
    r = await client.post(f"/characters/{cid}/spells/{r.json()['id']}/use", json={"slot_id": patto["id"]})
    assert r.status_code >= 400
    assert (await _pact_slots(client, cid))[0]["used"] == 0


@pytest.mark.caccia(id="CB-2066", fonte="2014 · Warlock · Tutt'Uno con le Ombre · pag. 119", zona="regola:2014/warlock", voce="regola",
                    copre=["carta:2014/classes/warlock.md#Tutt'Uno con le Ombre / One with Shadows (Suppliche Occulte, livello 5, pag. 119)",
                           "POST /characters/{char_id}/features/{feature_key}/use"])
@pytest.mark.xfail(strict=True, reason="CB-2066: difforme dal manuale, confermato")
async def test_tutt_uno_con_le_ombre_finisce_quando_compi_un_azione(client):
    cid = await _caster(client, 5, "one_with_shadows", "fiendish_vigor")
    assert (await _use(client, cid, "warlock.one_with_shadows", params={"light": "dark"})).status_code == 200
    await _new_turn(client, cid)
    assert (await _full(client, cid))["conditions"]["invisible"] is True
    assert (await _use(client, cid, "warlock.fiendish_vigor")).status_code == 200
    assert not (await _full(client, cid))["conditions"].get("invisible")


async def _goblin(client, sid, gid) -> dict:
    as_user(GM_ID)
    live = (await client.get(f"/sessions/{sid}/live")).json()
    return next(c for c in live["encounter"]["combatants"] if c["id"] == gid)


@pytest.mark.caccia(id="CB-2067", fonte="2014 · Warlock · Creare Servitore · pag. 118", zona="regola:2014/warlock", voce="regola",
                    copre=["carta:2014/classes/warlock.md#Creare Servitore / Create Thrall (Grande Antico 14, pag. 118)",
                           "POST /characters/{char_id}/target-effects", "POST /characters/{char_id}/features/{feature_key}/use"])
@pytest.mark.xfail(strict=True, reason="CB-2067: difforme dal manuale, confermato")
async def test_un_nuovo_servitore_libera_il_precedente(client, test_session_factory, monkeypatch):
    install_fake_telegram(monkeypatch)
    sid, _ = await setup_full_encounter(client, test_session_factory)
    pc, g1, g2 = (await client.post(f"/sessions/{sid}/encounter/start", json={})).json()["combatants"]
    cid = pc["character_id"]
    as_user(PLAYER_ID)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "warlock", "level": 14, "subclass": "Il Grande Antico"})
    assert r.status_code in (200, 201), r.text
    for goblin in (g1, g2):
        as_user(PLAYER_ID)
        assert (await client.post(f"/characters/{cid}/turn/use", json={"slot": "action", "used": False})).status_code == 200
        assert (await _use(client, cid, "warlock.create_thrall")).status_code == 200
        r = await client.post(f"/characters/{cid}/target-effects", json={"combatant_id": goblin["id"], "effect_key": "warlock.create_thrall"})
        assert r.status_code == 200 and r.json()["applied"] is True, r.text
    assert (await _goblin(client, sid, g2["id"]))["conditions"].get("charmed")
    assert not (await _goblin(client, sid, g1["id"]))["conditions"].get("charmed")


@pytest.mark.caccia(id="CB-2068", fonte="2014 · Warlock · Patto del Tomo · pag. 116", zona="regola:2014/warlock", voce="edizioni",
                    copre=["carta:2014/classes/warlock.md#Patto del Tomo / Pact of the Tome (Warlock 3, pag. 116)",
                           "POST /characters/{char_id}/rest"])
@pytest.mark.xfail(strict=True, reason="CB-2068: difforme dal manuale, confermato")
async def test_i_trucchetti_del_libro_2014_non_si_rifanno_a_ogni_riposo(client):
    cid = await _warlock(client, 3)
    assert (await _resolve(client, cid, "pact_boon", ["tome"])).status_code == 200
    pick = _choice(await _full(client, cid), "tome_cantrips")
    for nome in ("Mano magica", "Luce", "Prestidigitazione"):
        r = await client.post(f"/characters/{cid}/spells", json={"name": nome, "level": 0, "pick_id": pick["id"]})
        assert r.status_code == 201, r.text
    await client.post(f"/characters/{cid}/rest", json={"rest_type": "long", "confirm_early": True, "reopen_tome": True})
    nomi = {s["name"] for s in (await client.get(f"/characters/{cid}/spells")).json()}
    assert {"Mano magica", "Luce", "Prestidigitazione"} <= nomi
    assert _choice(await _full(client, cid), "tome_cantrips") is None


# ---------------------------------------------------------------------------
# Verdi: i numeri giusti restano protetti
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-2069", fonte="2014 · Warlock · Magia del Patto · pag. 115", zona="regola:2014/warlock", voce="limiti",
                    copre=["carta:2014/classes/warlock.md#Magia del Patto / Pact Magic (Warlock 1, pag. 115)"])
def test_slot_del_patto_seguono_la_tabella_dal_1_al_20():
    from core.data.spell_slots import WARLOCK_PACT
    tabella = [(1, 1), (2, 1), (2, 2), (2, 2), (2, 3), (2, 3), (2, 4), (2, 4), (2, 5), (2, 5),
               (3, 5), (3, 5), (3, 5), (3, 5), (3, 5), (3, 5), (4, 5), (4, 5), (4, 5), (4, 5)]
    assert list(WARLOCK_PACT) == tabella


@pytest.mark.caccia(id="CB-2070", fonte="2014 · Warlock · Suppliche Occulte e Magia del Patto · pag. 115", zona="regola:2014/warlock",
                    voce="regola", copre=["carta:2014/classes/warlock.md#Suppliche Occulte / Eldritch Invocations (Warlock 2, pag. 115)",
                                          "carta:2014/classes/warlock.md#Magia del Patto / Pact Magic (Warlock 1, pag. 115)"])
def test_trucchetti_conosciuti_e_suppliche_seguono_la_tabella():
    from core.rules.catalog.y2014.warlock import INVOCATION_CHOICE
    from core.rules.spellcasting import known_limits
    trucchetti = [2, 2, 2, 3, 3, 3, 3, 3, 3, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4]
    conosciuti = [2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 11, 11, 12, 12, 13, 13, 14, 14, 15, 15]
    assert [(known_limits("2014", "warlock", lv).cantrips, known_limits("2014", "warlock", lv).spells) for lv in range(1, 21)] \
        == list(zip(trucchetti, conosciuti))
    assert INVOCATION_CHOICE.levels == {2: 2, 5: 3, 7: 4, 9: 5, 12: 6, 15: 7, 18: 8}


@pytest.mark.caccia(id="CB-2071", fonte="2014 · Warlock · Magia del Patto · pag. 115", zona="regola:2014/warlock", voce="normale",
                    copre=["carta:2014/classes/warlock.md#Magia del Patto / Pact Magic (Warlock 1, pag. 115)", "POST /characters/{char_id}/rest"])
@pytest.mark.parametrize("riposo", ["short", "long"])
async def test_gli_slot_del_patto_tornano_con_un_riposo_breve_o_lungo(client, riposo):
    cid = await _warlock(client, 9)
    [patto] = await _pact_slots(client, cid)
    await _set_used(client, cid, patto["id"], 2)
    await _rest(client, cid, riposo)
    assert [(s["level"], s["total"], s["used"]) for s in await _pact_slots(client, cid)] == [(5, 2, 0)]


@pytest.mark.caccia(id="CB-2072", fonte="2014 · Warlock · Benedizione dell'Oscuro · pag. 117", zona="regola:2014/warlock", voce="interazione",
                    copre=["carta:2014/classes/warlock.md#Benedizione dell'Oscuro / Dark One's Blessing (Immondo 1, pag. 117)",
                           "carta:2014/classes/warlock.md#Multiclasse: Warlock / Multiclassing: Warlock (Manuale 2014, pag. 163)",
                           "POST /characters/{char_id}/features/{feature_key}/use"])
async def test_benedizione_dell_oscuro_conta_solo_il_livello_da_warlock(client):
    cid = await _warlock(client, 2, "fiend", charisma=16)
    assert (await client.post(f"/characters/{cid}/classes", json={"class_name": "fighter", "level": 6})).status_code in (200, 201)
    r = await _use(client, cid, "warlock.dark_ones_blessing")
    assert r.status_code == 200, r.text
    assert r.json()["temp_hp"] == 3 + 2


@pytest.mark.caccia(id="CB-2073", fonte="2014 · Warlock · Patto del Tomo · pag. 116", zona="regola:2014/warlock", voce="interazione",
                    copre=["carta:2014/classes/warlock.md#Patto del Tomo / Pact of the Tome (Warlock 3, pag. 116)",
                           "GET /characters/{char_id}/spells"])
async def test_i_trucchetti_del_tomo_usano_il_carisma_anche_in_multiclasse(client):
    cid = await _warlock(client, 3, charisma=16, intelligence=8)
    assert (await client.post(f"/characters/{cid}/classes", json={"class_name": "wizard", "level": 2})).status_code in (200, 201)
    assert (await _resolve(client, cid, "pact_boon", ["tome"])).status_code == 200
    pick = _choice(await _full(client, cid), "tome_cantrips")
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Spruzzo velenoso", "level": 0, "pick_id": pick["id"],
                                                            "attack_save": "CON"})
    assert r.status_code == 201, r.text
    trucchetto = next(s for s in (await client.get(f"/characters/{cid}/spells")).json() if s["id"] == r.json()["id"])
    assert trucchetto["save_dc"] == 8 + 3 + 3


@pytest.mark.caccia(id="CB-2074", fonte="2014 · Warlock · Fortuna dell'Oscuro · pag. 117", zona="regola:2014/warlock", voce="edizioni",
                    copre=["carta:2014/classes/warlock.md#Fortuna dell'Oscuro / Dark One's Own Luck (Immondo 6, pag. 117)",
                           "carta:2024/classes/warlock.md#Fortuna dell'Oscuro / Dark One's Own Luck (Patrono Immondo 6, pag. 162)"])
async def test_fortuna_dell_oscuro_usi_e_ricarica_per_edizione(client):
    vecchio = await _ability(client, await _warlock(client, 6, "fiend", charisma=18), LUCK)
    nuovo = await _ability(client, await _make24(client, "fiend", 6, charisma=18), LUCK)
    assert (vecchio["max_uses"], vecchio["restoration_type"]) == (1, "short_rest")
    assert (nuovo["max_uses"], nuovo["restoration_type"]) == (4, "long_rest")


@pytest.mark.caccia(id="CB-2075", fonte="2014 · Warlock · Presenza Fatata · pag. 116", zona="regola:2014/warlock", voce="ripetizione",
                    copre=["carta:2014/classes/warlock.md#Presenza Fatata / Fey Presence (Signore Fatato 1, pag. 116)",
                           "POST /characters/{char_id}/features/{feature_key}/use"])
async def test_due_presenze_fatate_insieme_spendono_un_solo_uso(client):
    import asyncio
    cid = await _warlock(client, 1, "archfey", charisma=16)
    risposte = await asyncio.gather(*(_use(client, cid, "warlock.fey_presence", params={"mode": "charmed"}) for _ in range(2)))
    assert sorted(r.status_code for r in risposte) == [200, 409]
    assert (await _ability(client, cid, "warlock.fey_presence"))["uses"] == 0


@pytest.mark.caccia(id="CB-2076", fonte="2014 · Warlock · Resilienza Immonda · pag. 117", zona="regola:2014/warlock", voce="persistenza",
                    copre=["carta:2014/classes/warlock.md#Resilienza Immonda / Fiendish Resilience (Immondo 10, pag. 117)",
                           "POST /characters/{char_id}/rest", "PATCH /characters/{char_id}/hp"])
async def test_la_resistenza_scelta_resta_dopo_un_riposo_lungo_senza_scelta(client):
    cid = await _warlock(client, 10, "fiend", charisma=16)
    for op in ("set_max", "set_current"):
        await client.patch(f"/characters/{cid}/hp", json={"op": op, "value": 100})
    r = await client.post(f"/characters/{cid}/rest", json={"rest_type": "short", "fiendish_resilience": "fire"})
    assert r.status_code == 200, r.text
    await _rest(client, cid, "long")
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 10, "damage_type": "fire"})
    assert r.json()["current_hit_points"] == 95


@pytest.mark.caccia(id="CB-2077", fonte="2014 · Warlock · Maestro dell'Occulto · pag. 116", zona="regola:2014/warlock", voce="permessi",
                    copre=["carta:2014/classes/warlock.md#Maestro dell'Occulto / Eldritch Master (Warlock 20, pag. 116)",
                           "POST /characters/{char_id}/features/{feature_key}/use"])
async def test_un_altro_utente_non_usa_il_maestro_dell_occulto(client, come_utente):
    cid = await _warlock(client, 20)
    [patto] = await _pact_slots(client, cid)
    await _set_used(client, cid, patto["id"], 4)
    come_utente(9002)
    assert (await _use(client, cid, "warlock.eldritch_master")).status_code in (403, 404)
    come_utente(TEST_USER_ID)
    assert (await _ability(client, cid, "warlock.eldritch_master"))["uses"] == 1
    assert (await _pact_slots(client, cid))[0]["used"] == 4
