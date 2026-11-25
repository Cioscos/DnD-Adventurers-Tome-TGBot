"""Controlli della zona regola:2024/warlock."""
import asyncio
import json
from types import SimpleNamespace

import pytest

from tests.integration.rules.test_2014_barbarian import _weapon
from tests.integration.rules.test_2014_bard import _ability, _full, _use
from tests.integration.rules.test_2014_fighter_eldritch_knight import _hit
from tests.integration.rules.test_2014_paladin import _rest
from tests.integration.rules.test_2014_warlock import _choice, _pact_slots, _resolve, _set_used
from tests.integration.rules.test_2014_warlock_invocations import _cast
from tests.integration.rules.test_2024_warlock import BLADE, TOME, _blade, _caster24, _offered, _warlock24
from tests.integration.rules.test_2024_warlock_patrons import _effect, _hp, _make

CUNNING = "warlock.magical_cunning"
DEFENSES = "warlock.beguiling_defenses"
SMITE = "warlock.eldritch_smite"
VENGEANCE = "warlock.searing_vengeance"


# ---------------------------------------------------------------------------
# Rossi
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-2661", fonte="2024 · Warlock · Suppliche Occulte (sostituzione e prerequisiti) · pag. 153-157", zona="regola:2024/warlock",
                    voce="regola", copre=["carta:2024/classes/warlock.md#Suppliche Occulte / Eldritch Invocations (Warlock 1, pag. 153)",
                                          "carta:2024/classes/warlock.md#Lama Assetata / Thirsting Blade (Suppliche Occulte, livello 5+, Patto della Lama, pag. 157)",
                                          "carta:2024/classes/warlock.md#Fendente Occulto / Eldritch Smite (Suppliche Occulte, livello 5+, Patto della Lama, pag. 155)",
                                          "carta:2024/classes/warlock.md#Succhiavita / Lifedrinker (Suppliche Occulte, livello 9+, Patto della Lama, pag. 156)",
                                          "carta:2024/classes/warlock.md#Investitura del Padrone delle Catene / Investment of the Chain Master (Suppliche Occulte, livello 5+, Patto della Catena, pag. 156)",
                                          "carta:2024/classes/warlock.md#Dono dei Protettori / Gift of the Protectors (Suppliche Occulte, livello 9+, Patto del Tomo, pag. 156)",
                                          "POST /characters/{char_id}/classes/{class_id}/options/replace"])
@pytest.mark.parametrize("nuova", ["thirsting_blade", "eldritch_smite", "lifedrinker", "investment_of_the_chain_master", "gift_of_the_protectors"])
@pytest.mark.xfail(strict=True, reason="CB-2661: difforme dal manuale, confermato")
async def test_la_sostituzione_non_da_una_supplica_senza_il_patto_che_richiede(client, nuova):
    cid = await _caster24(client, 9, "devils_sight", "eldritch_mind", "armor_of_shadows", "misty_visions", "fiendish_vigor",
                          "mask_of_many_faces", "otherworldly_leap")
    klass = (await _full(client, cid))["classes"][0]
    assert not {BLADE, TOME, "pact_of_the_chain"} & set(klass["options"]["invocations"])
    r = await client.post(f"/characters/{cid}/classes/{klass['id']}/options/replace",
                          json={"group": "invocations", "old_key": "eldritch_mind", "new_key": nuova})
    assert r.status_code == 422, r.text
    assert nuova not in (await _full(client, cid))["classes"][0]["options"]["invocations"]


@pytest.mark.caccia(id="CB-2662", fonte="2024 · Warlock · Lezioni dei Primi (Ripetibile) · pag. 156", zona="regola:2024/warlock", voce="regola",
                    copre=["carta:2024/classes/warlock.md#Lezioni dei Primi / Lessons of the First Ones (Suppliche Occulte, livello 2+, pag. 156)",
                           "POST /characters/{char_id}/choices/{choice_id}/resolve", "PATCH /characters/{char_id}/classes/{class_id}"])
@pytest.mark.xfail(strict=True, reason="CB-2662: difforme dal manuale, confermato")
async def test_lezioni_dei_primi_si_riprende_salendo_di_livello(client):
    cid = await _warlock24(client, 2, charisma=16)
    r = await _resolve(client, cid, "invocations", ["lessons_of_the_first_ones", "devils_sight", "eldritch_mind"])
    assert r.status_code == 200, r.text
    klass = (await _full(client, cid))["classes"][0]
    r = await client.patch(f"/characters/{cid}/classes/{klass['id']}", json={"level": 5})
    assert r.status_code == 200, r.text
    offerte = await _offered(client, cid)
    assert "ascendant_step" in offerte  # la scelta del 5° livello è aperta
    assert any(k.startswith("lessons_of_the_first_ones") for k in offerte)


@pytest.mark.caccia(id="CB-2663", fonte="2024 · Warlock · Patto della Lama (arma legata) · pag. 156", zona="regola:2024/warlock", voce="regola",
                    copre=["carta:2024/classes/warlock.md#Patto della Lama / Pact of the Blade (Suppliche Occulte, pag. 156)",
                           "POST /characters/{char_id}/features/{feature_key}/use", "POST /characters/{char_id}/items/{item_id}/attack"])
@pytest.mark.xfail(strict=True, reason="CB-2663: difforme dal manuale, confermato")
async def test_l_arma_magica_da_guerra_legata_al_patto_ha_la_competenza(client):
    cid = await _caster24(client, 3, BLADE, charisma=18, strength=10, dexterity=10)
    spada = await _weapon(client, cid, "Spada lunga +1", "main_hand", damage_dice="1d8", magic_bonus=1, weapon_category="martial")
    assert (await _use(client, cid, f"warlock.{BLADE}", params={"weapon": f"bind:{spada}"})).status_code == 200
    r = await client.post(f"/characters/{cid}/items/{spada}/attack", json={"die": 10, "confirm_extra_attack": True})
    assert r.status_code == 200, r.text
    assert r.json()["to_hit_bonus"] == 4 + 2 + 1  # Carisma, competenza del 3° livello, +1 dell'arma


@pytest.mark.caccia(id="CB-2664", fonte="2024 · Warlock · Patto del Tomo · pag. 157", zona="regola:2024/warlock", voce="regola",
                    copre=["carta:2024/classes/warlock.md#Patto del Tomo / Pact of the Tome (Suppliche Occulte, pag. 157)",
                           "POST /characters/{char_id}/spells", "POST /characters/{char_id}/spells/{spell_id}/use"])
@pytest.mark.xfail(strict=True, reason="CB-2664: difforme dal manuale, confermato")
async def test_il_rituale_del_libro_delle_ombre_e_preparato(client):
    cid = await _caster24(client, 3, TOME)
    rituali = _choice(await _full(client, cid), "tome_rituals")
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Allarme", "level": 1, "is_ritual": True, "pick_id": rituali["id"],
                                                            "casting_time": "1 minuto"})
    assert r.status_code == 201, r.text
    allarme = next(s for s in (await _full(client, cid))["spells"] if s["name"] == "Allarme")
    r = await _cast(client, cid, allarme["id"], as_ritual=True)
    assert r.status_code == 200, r.text


@pytest.mark.caccia(id="CB-2665", fonte="2024 · Warlock · Astuzia Magica pag. 154 e Resilienza Celestiale pag. 161", zona="regola:2024/warlock",
                    voce="interazione", copre=["carta:2024/classes/warlock.md#Astuzia Magica / Magical Cunning (Warlock 2, pag. 154)",
                                               "carta:2024/classes/warlock.md#Resilienza Celestiale / Celestial Resilience (Patrono Celestiale 10, pag. 161)",
                                               "POST /characters/{char_id}/features/{feature_key}/use"])
@pytest.mark.xfail(strict=True, reason="CB-2665: difforme dal manuale, confermato")
async def test_astuzia_magica_a_slot_pieni_da_i_pf_della_resilienza_celestiale(client):
    cid = await _make(client, "celestial", 10, charisma=16)
    assert all(s["used"] == 0 for s in await _pact_slots(client, cid))
    r = await _use(client, cid, CUNNING)
    assert r.status_code == 200, r.text
    assert (await _full(client, cid))["temp_hp"] == 10 + 3


@pytest.mark.caccia(id="CB-2666", fonte="2024 · Warlock · Vendetta Ardente · pag. 161", zona="regola:2024/warlock", voce="limiti",
                    copre=["carta:2024/classes/warlock.md#Vendetta Ardente / Searing Vengeance (Patrono Celestiale 14, pag. 161)",
                           "POST /characters/{char_id}/features/{feature_key}/use", "GET /characters/{char_id}/target-effects/{effect_key}"])
@pytest.mark.xfail(strict=True, reason="CB-2666: difforme dal manuale, confermato")
async def test_vendetta_ardente_somma_anche_un_carisma_negativo(client):
    cid = await _make(client, "celestial", 14, charisma=8)
    await _hp(client, cid, op="set_max", value=80)
    await _hp(client, cid, op="set_current", value=0)
    assert (await _use(client, cid, VENGEANCE, params={"mode": "self"})).status_code == 200
    assert (await _effect(client, cid, VENGEANCE))["damage_dice"] == "2d8-1"


@pytest.mark.caccia(id="CB-2677", fonte="2024 · Warlock · Arcanum Mistico · pag. 155", zona="regola:2024/warlock", voce="regola",
                    copre=["carta:2024/classes/warlock.md#Arcanum Mistico / Mystic Arcanum (Warlock 11, pag. 155)", "GET /characters/{char_id}"])
@pytest.mark.xfail(strict=True, reason="CB-2677: difforme dal manuale, confermato")
async def test_arcanum_mistico_2024_si_sceglie_dalla_lista_del_warlock(client):
    full = await _full(client, await _warlock24(client, 17))
    liste = {grado: _choice(full, f"arcanum_{grado}")["spell_pick"]["list"] for grado in (6, 7, 8, 9)}
    assert liste == {6: "warlock", 7: "warlock", 8: "warlock", 9: "warlock"}


@pytest.mark.caccia(id="CB-2678", fonte="2024 · Warlock · Patto della Lama · pag. 156; Equipaggiamento · Armi · pag. 215", zona="regola:2024/warlock",
                    voce="edizioni", copre=["carta:2024/classes/warlock.md#Patto della Lama / Pact of the Blade (Suppliche Occulte, pag. 156)",
                                            "POST /characters/{char_id}/features/{feature_key}/use"])
@pytest.mark.parametrize("forma,dado,versatile", [("trident", "1d8", "1d10"), ("lance", "1d10", None), ("war_pick", "1d8", "1d10")])
async def test_l_arma_evocata_dal_patto_2024_ha_i_dadi_delle_armi_2024(client, forma, dado, versatile):
    cid = await _caster24(client, 3, BLADE)
    arma = await _blade(client, cid, forma)
    item = next(i for i in (await _full(client, cid))["items"] if i["id"] == arma)
    meta = item["item_metadata"] if isinstance(item["item_metadata"], dict) else json.loads(item["item_metadata"])
    assert (meta["damage_dice"], meta.get("versatile_dice")) == (dado, versatile)


# ---------------------------------------------------------------------------
# Verdi: i numeri giusti restano protetti
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-2667", fonte="2024 · Warlock · Astuzia Magica pag. 154 e Maestro dell'Occulto pag. 155", zona="regola:2024/warlock",
                    voce="limiti", copre=["carta:2024/classes/warlock.md#Astuzia Magica / Magical Cunning (Warlock 2, pag. 154)",
                                          "carta:2024/classes/warlock.md#Maestro dell'Occulto / Eldritch Master (Warlock 20, pag. 155)",
                                          "POST /characters/{char_id}/features/{feature_key}/use"])
@pytest.mark.parametrize("livello,spesi,tornano", [(2, 2, 1), (10, 2, 1), (11, 3, 2), (16, 3, 2), (17, 4, 2), (19, 4, 2), (20, 4, 4)])
async def test_astuzia_magica_rende_meta_degli_slot_per_eccesso_e_tutti_al_20(client, livello, spesi, tornano):
    cid = await _warlock24(client, livello)
    [patto] = await _pact_slots(client, cid)
    await _set_used(client, cid, patto["id"], spesi)
    assert (await _use(client, cid, CUNNING)).status_code == 200
    assert (await _pact_slots(client, cid))[0]["used"] == spesi - tornano


@pytest.mark.caccia(id="CB-2668", fonte="2024 · Warlock · Tabella di classe · pag. 153", zona="regola:2024/warlock", voce="limiti",
                    copre=["carta:2024/classes/warlock.md#Magia del Patto / Pact Magic (Warlock 1, pag. 153)",
                           "carta:2024/classes/warlock.md#Suppliche Occulte / Eldritch Invocations (Warlock 1, pag. 153)"])
def test_suppliche_trucchetti_preparati_e_slot_seguono_la_tabella_2024():
    from core.data.spell_slots import WARLOCK_PACT
    from core.rules.catalog.y2024.warlock_invocations import INVOCATION_CHOICE
    from core.rules.spellcasting import known_limits, prepared_limit
    slot = [(1, 1), (2, 1), (2, 2), (2, 2), (2, 3), (2, 3), (2, 4), (2, 4), (2, 5), (2, 5),
            (3, 5), (3, 5), (3, 5), (3, 5), (3, 5), (3, 5), (4, 5), (4, 5), (4, 5), (4, 5)]
    trucchetti = [2, 2, 2, 3, 3, 3, 3, 3, 3, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4]
    preparati = [2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 11, 11, 12, 12, 13, 13, 14, 14, 15, 15]
    nessuno = SimpleNamespace(classes=[])
    assert list(WARLOCK_PACT) == slot
    assert [known_limits("2024", "warlock", lv).cantrips for lv in range(1, 21)] == trucchetti
    assert [prepared_limit("2024", "warlock", lv, nessuno) for lv in range(1, 21)] == preparati
    assert INVOCATION_CHOICE.levels == {1: 1, 2: 3, 5: 5, 7: 6, 9: 7, 12: 8, 15: 9, 18: 10}


@pytest.mark.caccia(id="CB-2669", fonte="2024 · Warlock · Fendente Occulto · pag. 155", zona="regola:2024/warlock", voce="normale",
                    copre=["carta:2024/classes/warlock.md#Fendente Occulto / Eldritch Smite (Suppliche Occulte, livello 5+, Patto della Lama, pag. 155)",
                           "GET /characters/{char_id}/roll-options", "POST /characters/{char_id}/attack/{attack_id}/damage"])
async def test_fendente_occulto_al_9_spende_lo_slot_di_patto_per_6d8(client):
    cid = await _caster24(client, 9, BLADE, "eldritch_smite")
    lama = await _blade(client, cid)
    opzioni = (await client.get(f"/characters/{cid}/roll-options", params={"roll": "attack", "item_id": lama})).json()
    fendente = next(o for o in opzioni if o["key"] == SMITE)
    assert [(s["level"], s["dice"]) for s in fendente["input_options"]] == [(5, "6d8")]
    colpo = await _hit(client, cid, lama)
    r = await client.post(f"/characters/{cid}/attack/{colpo['attack_id']}/damage",
                          json={"options": [SMITE], "option_inputs": {SMITE: {"slot_level": 5}}, "main_rolls": [4], "extra_rolls": [[1] * 6]})
    assert r.status_code == 200, r.text
    assert (await _pact_slots(client, cid))[0]["used"] == 1


@pytest.mark.caccia(id="CB-2670", fonte="2024 · Warlock · Difese Seducenti · pag. 159", zona="regola:2024/warlock", voce="annullamento",
                    copre=["carta:2024/classes/warlock.md#Difese Seducenti / Beguiling Defenses (Patrono Fatato 10, pag. 159)",
                           "PATCH /characters/{char_id}/hp", "POST /characters/{char_id}/hp/undo"])
async def test_annullare_il_colpo_dimezzato_rende_lo_slot_di_patto(client):
    cid = await _make(client, "archfey", 10, charisma=18)
    await _hp(client, cid, op="set_max", value=100)
    await _hp(client, cid, op="set_current", value=100)
    livello = (await _pact_slots(client, cid))[0]["level"]
    pieno = await _hp(client, cid, op="damage", value=10, damage_type="slashing", options=[DEFENSES + "_slot"],
                      option_inputs={DEFENSES + "_slot": {"slot_level": livello}})
    assert pieno["current_hit_points"] == 95 and (await _pact_slots(client, cid))[0]["used"] == 1
    r = await client.post(f"/characters/{cid}/hp/undo", json={"op_id": (await _full(client, cid))["hp_undo_id"]})
    assert r.status_code == 200, r.text
    assert r.json()["current_hit_points"] == 100 and (await _pact_slots(client, cid))[0]["used"] == 0
    assert (await _ability(client, cid, DEFENSES))["uses"] == 1


@pytest.mark.caccia(id="CB-2671", fonte="2024 · Warlock · Astuzia Magica · pag. 154", zona="regola:2024/warlock", voce="ripetizione",
                    copre=["carta:2024/classes/warlock.md#Astuzia Magica / Magical Cunning (Warlock 2, pag. 154)",
                           "POST /characters/{char_id}/features/{feature_key}/use"])
async def test_due_astuzie_magiche_insieme_rendono_gli_slot_una_volta(client):
    cid = await _warlock24(client, 11)
    [patto] = await _pact_slots(client, cid)
    await _set_used(client, cid, patto["id"], 3)
    risposte = await asyncio.gather(*(_use(client, cid, CUNNING) for _ in range(2)))
    assert sorted(r.status_code for r in risposte) == [200, 409]
    assert (await _pact_slots(client, cid))[0]["used"] == 1


@pytest.mark.caccia(id="CB-2672", fonte="2024 · Warlock · Lama Assetata pag. 157; Multiclasse pag. 44", zona="regola:2024/warlock", voce="interazione",
                    copre=["carta:2024/classes/warlock.md#Lama Assetata / Thirsting Blade (Suppliche Occulte, livello 5+, Patto della Lama, pag. 157)",
                           "carta:2024/classes/warlock.md#Multiclasse: Warlock / Multiclassing: Warlock (Manuale 2024, pag. 44)",
                           "POST /characters/{char_id}/classes", "GET /characters/{character_id}/turn-state"])
async def test_lama_assetata_non_si_somma_all_attacco_extra_del_guerriero(client):
    cid = await _caster24(client, 5, BLADE, "thirsting_blade")
    assert (await client.post(f"/characters/{cid}/classes", json={"class_name": "fighter", "level": 5})).status_code == 201
    stato = (await client.get(f"/characters/{cid}/turn-state")).json()
    assert (stato["attacks_allowed"], stato["attacks_allowed_pact"]) == (2, 2)


@pytest.mark.caccia(id="CB-2673", fonte="2024 · Warlock · Scagliare all'Inferno · pag. 162; 2014 · Warlock · Scagliare all'Inferno · pag. 117",
                    zona="regola:2024/warlock", voce="edizioni",
                    copre=["carta:2024/classes/warlock.md#Scagliare all'Inferno / Hurl Through Hell (Patrono Immondo 14, pag. 162)",
                           "carta:2014/classes/warlock.md#Scagliare all'Inferno / Hurl Through Hell (Immondo 14, pag. 117)"])
def test_scagliare_all_inferno_8d10_una_volta_per_turno_nel_2024_e_10d10_nel_2014():
    from core.rules.catalog import features_for
    vecchio = {f.key: f for f in features_for("2014", "warlock")}["warlock.hurl_through_hell"]
    nuovo = {f.key: f for f in features_for("2024", "warlock")}["warlock.hurl_through_hell"]
    [opzione14] = [o for o in vecchio.roll_options if o.key == "warlock.hurl_through_hell"]
    [opzione24] = [o for o in nuovo.roll_options if o.key == "warlock.hurl_through_hell"]
    assert opzione14.extra_dice(None, {}) == "10d10" and opzione24.extra_dice(None, {}) == "8d10"
    assert opzione24.once_per_turn is True and opzione24.target_effect is not None


@pytest.mark.caccia(id="CB-2674", fonte="2024 · Warlock · Resilienza Immonda · pag. 162", zona="regola:2024/warlock", voce="persistenza",
                    copre=["carta:2024/classes/warlock.md#Resilienza Immonda / Fiendish Resilience (Patrono Immondo 10, pag. 162)",
                           "POST /characters/{char_id}/rest", "PATCH /characters/{char_id}/hp"])
async def test_la_resistenza_immonda_resta_finche_non_se_ne_sceglie_un_altra(client):
    cid = await _make(client, "fiend", 10)
    await _hp(client, cid, op="set_max", value=100)
    await _hp(client, cid, op="set_current", value=100)
    r = await client.post(f"/characters/{cid}/rest", json={"rest_type": "short", "fiendish_resilience": "fire"})
    assert r.status_code == 200, r.text
    await _rest(client, cid, "long")
    assert (await _hp(client, cid, op="damage", value=10, damage_type="fire"))["current_hit_points"] == 95
