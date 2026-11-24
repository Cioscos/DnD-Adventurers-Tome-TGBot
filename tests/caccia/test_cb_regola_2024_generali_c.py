"""Controlli della zona regola:2024/generali (parte generali-c)."""
import pytest

from tests.integration.rules.test_2024_druid import _druid24, _shape
from tests.integration.test_magic_items import _item

UNCANNY = "rogue.uncanny_dodge"


async def _pg(client, classe, livello, edizione="2024", **punteggi) -> int:
    r = await client.post("/characters", json={"name": "Prova", "rules_edition": edizione,
                                               "initial_class": {"class_name": classe, "level": livello}})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    for ab, v in punteggi.items():
        r = await client.patch(f"/characters/{cid}/ability_scores/{ab}", json={"value": v})
        assert r.status_code == 200, r.text
    return cid


async def _scheda(client, cid) -> dict:
    r = await client.get(f"/characters/{cid}")
    assert r.status_code == 200, r.text
    return r.json()


async def _condizioni(client, cid, **cond) -> dict:
    r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": cond})
    assert r.status_code == 200, r.text
    return r.json()


async def _opzioni(client, cid, tiro, **query) -> list[str]:
    r = await client.get(f"/characters/{cid}/roll-options", params={"roll": tiro, **query})
    assert r.status_code == 200, r.text
    return [o["key"] for o in r.json()]


async def _turno(client, cid) -> dict:
    r = await client.get(f"/characters/{cid}/turn-state")
    assert r.status_code == 200, r.text
    return r.json()["turn"]


# ---------------------------------------------------------------------------------------------------------------------
# Rossi
# ---------------------------------------------------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-2961", fonte="2024 · Glossario · Velocità · pag. 374 (le velocità speciali cambiano come la Velocità); Afferrato · pag. 367",
                    zona="regola:2024/generali", voce="regola",
                    copre=["carta:2024/general.md#Speed (Velocità) (pag. 374)",
                           "carta:2024/general.md#Grappled [Condition] (Afferrato) (pag. 367)",
                           "POST /characters/{char_id}/spells/{spell_id}/use", "PATCH /characters/{char_id}/conditions",
                           "POST /characters/{char_id}/items/{item_id}/cast"])
@pytest.mark.parametrize("effetto,terra,volo", [("afferrato", 0, 0), ("esaurimento", 20, 50), ("passo_lungo", 40, 70)])
@pytest.mark.xfail(strict=True, reason="CB-2961: difforme dal manuale, confermato")
async def test_la_velocita_di_volo_fissa_cambia_come_la_velocita(client, effetto, terra, volo):
    cid = await _pg(client, "sorcerer", 5)
    classe = (await _scheda(client, cid))["classes"][0]["id"]
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Volare", "level": 3, "srd_index": "fly", "class_id": classe,
                                                              "is_prepared": True, "is_concentration": True, "casting_time": "1 azione"})
    assert r.status_code == 201, r.text
    r = await client.post(f"/characters/{cid}/spells/{r.json()['id']}/use", json={"slot_level": 3})
    assert r.status_code == 200, r.text
    assert (r.json()["computed"]["speed"], r.json()["computed"]["fly_speed"]) == (30, 60)
    if effetto == "passo_lungo":  # +3 m alla Velocità, senza concentrazione: lo lancia uno stivale magico
        stivali = await _item(client, cid, name="Stivali", granted_spells=[{"name": "Passo Lungo", "level": 1, "srd_index": "longstrider"}])
        r = await client.post(f"/characters/{cid}/items/{stivali}/cast", json={"spell_index": 0})
        assert r.status_code == 200, r.text
        j = await _scheda(client, cid)
    else:
        j = await _condizioni(client, cid, **({"grappled": True} if effetto == "afferrato" else {"exhaustion": 2}))
    assert (j["computed"]["speed"], j["computed"]["fly_speed"] or 0) == (terra, volo)


@pytest.mark.caccia(id="CB-2962", fonte="2024 · Glossario · Nascondersi · pag. 368 (il tiro per colpire fa finire l'Invisibilità); Mutare forma · pag. 373",
                    zona="regola:2024/generali", voce="interazione",
                    copre=["carta:2024/general.md#Hide [Action] (Nascondersi) (pag. 368)",
                           "carta:2024/general.md#Shape-Shifting (Mutare forma) (pag. 373)",
                           "POST /characters/{char_id}/hide", "POST /characters/{char_id}/companions/{comp_id}/attack"])
async def test_l_attacco_della_forma_selvatica_fa_finire_il_nascondiglio(client):
    cid = await _druid24(client, 2)
    forma = await _shape(client, cid, 0.25)
    bestia = {"size": "Medium", "type": "beast", "challenge_rating": 0.25, "speed": {"walk_ft": 30, "swim_ft": 0, "fly_ft": 0},
              "actions": [{"name": "Morso", "attack_bonus": 4, "damage_dice": "1d6+2", "damage_type": "piercing"}]}
    assert (await client.patch(f"/characters/{cid}/companions/{forma}", json={"statblock": bestia})).status_code == 200
    assert (await client.post(f"/characters/{cid}/skills/stealth/roll", json={"dice": [20]})).status_code == 200
    r = await client.post(f"/characters/{cid}/hide")
    assert r.status_code == 200, r.text
    assert r.json()["conditions"].get("invisible") is True
    r = await client.post(f"/characters/{cid}/companions/{forma}/attack", json={"action_index": 0, "dice": [10]})
    assert r.status_code == 200, r.text
    j = await _scheda(client, cid)
    assert (bool(j["conditions"].get("invisible")), j["hiding_dc"]) == (False, None)


@pytest.mark.caccia(id="CB-2963", fonte="2024 · Glossario · Incapacitato · pag. 369 (niente azioni); Magia · pag. 371",
                    zona="regola:2024/generali", voce="regola",
                    copre=["carta:2024/general.md#Incapacitated [Condition] (Incapacitato) (pag. 369)",
                           "carta:2024/general.md#Magic [Action] (Magia) (pag. 371)",
                           "POST /characters/{char_id}/items/{item_id}/cast"])
@pytest.mark.parametrize("condizione", ["stunned", "incapacitated"])
@pytest.mark.xfail(strict=True, reason="CB-2963: difforme dal manuale, confermato")
async def test_chi_e_incapacitato_non_lancia_da_un_oggetto_magico(client, condizione):
    cid = await _pg(client, "fighter", 3)
    bacchetta = await _item(client, cid, name="Bacchetta", charges={"current": 3, "max": 3},
                            granted_spells=[{"name": "Dardo", "level": 1, "charges_cost": 1}])
    await _condizioni(client, cid, **{condizione: True})
    r = await client.post(f"/characters/{cid}/items/{bacchetta}/cast", json={"spell_index": 0})
    assert r.status_code == 409, r.text[:200]
    oggetto = next(i for i in (await _scheda(client, cid))["items"] if i["id"] == bacchetta)
    assert oggetto["item_metadata"]["charges"]["current"] == 3


@pytest.mark.caccia(id="CB-2964", fonte="2024 · Glossario · Incapacitato · pag. 369 (niente Reazioni); Reazione · pag. 372",
                    zona="regola:2024/generali", voce="regola",
                    copre=["carta:2024/general.md#Incapacitated [Condition] (Incapacitato) (pag. 369)",
                           "carta:2024/general.md#Reaction (Reazione) (pag. 372)",
                           "GET /characters/{char_id}/roll-options", "PATCH /characters/{char_id}/hp"])
@pytest.mark.xfail(strict=True, reason="CB-2964: difforme dal manuale, confermato")
async def test_chi_e_stordito_non_usa_una_reazione_sul_danno(client):
    cid = await _pg(client, "rogue", 5)
    pieni = (await _scheda(client, cid))["current_hit_points"]
    await _condizioni(client, cid, stunned=True)
    assert UNCANNY not in await _opzioni(client, cid, "damage_taken")
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 20, "options": [UNCANNY]})
    assert r.status_code == 409, r.text[:200]
    assert (await _scheda(client, cid))["current_hit_points"] == pieni


@pytest.mark.caccia(id="CB-2965", fonte="2024 · Glossario · Ispirazione Eroica · pag. 368 (si spende per rilanciare)",
                    zona="regola:2024/generali", voce="regola",
                    copre=["carta:2024/general.md#Heroic Inspiration (Ispirazione Eroica) (pag. 368)",
                           "POST /characters/{char_id}/death_saves/roll"])
@pytest.mark.xfail(strict=True, reason="CB-2965: difforme dal manuale, confermato")
async def test_il_rilancio_del_ts_contro_la_morte_chiede_l_ispirazione(client):
    cid = await _pg(client, "fighter", 1)
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 0})
    assert r.status_code == 200, r.text
    assert r.json()["heroic_inspiration"] is False
    r = await client.post(f"/characters/{cid}/death_saves/roll", json={"with_inspiration": True, "dice": [15]})
    assert r.status_code == 409, r.text[:200]
    assert (await _scheda(client, cid))["death_saves"]["successes"] == 0


# ---------------------------------------------------------------------------------------------------------------------
# Verdi
# ---------------------------------------------------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-2966", fonte="2024 · Glossario · Percezione Passiva · pag. 372 (esempio: 14, -5 con Svantaggio); Avvelenato · pag. 372",
                    zona="regola:2024/generali", voce="regola",
                    copre=["carta:2024/general.md#Passive Perception (Percezione Passiva) (pag. 372)",
                           "carta:2024/general.md#Poisoned [Condition] (Avvelenato) (pag. 372)",
                           "PATCH /characters/{char_id}/skills", "GET /characters/{char_id}"])
async def test_percezione_passiva_dell_esempio_del_manuale(client):
    cid = await _pg(client, "fighter", 1, wisdom=15)
    r = await client.patch(f"/characters/{cid}/skills", json={"skills": {"perception": True}})
    assert r.status_code == 200, r.text
    assert (await _scheda(client, cid))["passives"]["perception"] == 14
    assert (await _condizioni(client, cid, poisoned=True))["passives"]["perception"] == 9


@pytest.mark.caccia(id="CB-2967", fonte="2024 · Glossario · Stordito · pag. 376 (nessuna Velocità 0); 2014 · Condizioni · Stordito · pag. 292 (non può muoversi)",
                    zona="regola:2024/generali", voce="edizioni",
                    copre=["carta:2024/general.md#Stunned [Condition] (Stordito) (pag. 376)",
                           "carta:2014/general.md#Stordito / Stunned (pag. 292)",
                           "PATCH /characters/{char_id}/conditions"])
@pytest.mark.parametrize("edizione,velocita", [("2024", 30), ("2014", 0)])
async def test_lo_stordito_ha_velocita_zero_solo_nel_2014(client, edizione, velocita):
    cid = await _pg(client, "fighter", 3, edizione)
    j = await _condizioni(client, cid, stunned=True)
    assert (j["computed"]["speed"], j["computed"]["incapacitated"]) == (velocita, True)


@pytest.mark.caccia(id="CB-2968", fonte="2024 · Glossario · Incapacitato · pag. 369 e Invisibile · pag. 370 (Iniziativa); Svantaggio · pag. 366",
                    zona="regola:2024/generali", voce="regola",
                    copre=["carta:2024/general.md#Initiative (Iniziativa) (pag. 369-370)",
                           "carta:2024/general.md#Invisible [Condition] (Invisibile) (pag. 370)",
                           "carta:2024/general.md#Incapacitated [Condition] (Incapacitato) (pag. 369)",
                           "POST /characters/{char_id}/dice/initiative"])
@pytest.mark.parametrize("condizioni,modo", [({"incapacitated": True}, "disadvantage"), ({"invisible": True}, "advantage"),
                                             ({"incapacitated": True, "invisible": True}, "normal")])
async def test_iniziativa_da_incapacitato_e_da_invisibile(client, condizioni, modo):
    cid = await _pg(client, "fighter", 3)
    await _condizioni(client, cid, **condizioni)
    r = await client.post(f"/characters/{cid}/dice/initiative", json={"dice": [5, 15]})
    assert r.status_code == 200, r.text
    assert r.json()["mode_applied"] == modo


@pytest.mark.caccia(id="CB-2969", fonte="2024 · Glossario · Pietrificato · pag. 372 (Resistenza a tutti i danni, immune solo alla condizione Avvelenato); 2014 · Condizioni · Pietrificato · pag. 291",
                    zona="regola:2024/generali", voce="edizioni",
                    copre=["carta:2024/general.md#Petrified [Condition] (Pietrificato) (pag. 372)",
                           "carta:2024/general.md#Resistance (Resistenza) (pag. 373)",
                           "PATCH /characters/{char_id}/hp", "PATCH /characters/{char_id}/conditions"])
@pytest.mark.parametrize("edizione,persi", [("2024", 5), ("2014", 0)])
async def test_pietrificato_dimezza_il_veleno_nel_2024(client, edizione, persi):
    cid = await _pg(client, "fighter", 3, edizione)
    pieni = (await _scheda(client, cid))["current_hit_points"]
    await _condizioni(client, cid, petrified=True)
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 11, "damage_type": "poison"})
    assert r.status_code == 200, r.text
    assert pieni - r.json()["current_hit_points"] == persi


@pytest.mark.caccia(id="CB-2970", fonte="2024 · Glossario · Reazione · pag. 372 (una sola fino all'inizio del tuo turno)",
                    zona="regola:2024/generali", voce="ripetizione",
                    copre=["carta:2024/general.md#Reaction (Reazione) (pag. 372)", "PATCH /characters/{char_id}/hp",
                           "GET /characters/{character_id}/turn-state"])
async def test_una_sola_reazione_fino_al_prossimo_turno(client):
    cid = await _pg(client, "rogue", 5)
    pieni = (await _scheda(client, cid))["current_hit_points"]
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 10, "options": [UNCANNY]})
    assert r.status_code == 200, r.text
    assert r.json()["current_hit_points"] == pieni - 5
    assert (await _turno(client, cid))["reaction_used"] is True
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 10, "options": [UNCANNY]})
    assert r.status_code == 409, r.text[:200]
    assert (await _scheda(client, cid))["current_hit_points"] == pieni - 5


@pytest.mark.caccia(id="CB-2972", fonte="2024 · Glossario · Reazione · pag. 372; annullare il danno rimborsa la reazione spesa per ridurlo",
                    zona="regola:2024/generali", voce="annullamento",
                    copre=["carta:2024/general.md#Reaction (Reazione) (pag. 372)", "POST /characters/{char_id}/hp/undo",
                           "PATCH /characters/{char_id}/hp"])
async def test_annullare_il_danno_rende_la_reazione(client):
    cid = await _pg(client, "rogue", 5)
    pieni = (await _scheda(client, cid))["current_hit_points"]
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 10, "options": [UNCANNY]})
    assert r.status_code == 200, r.text
    assert (await _turno(client, cid))["reaction_used"] is True
    assert (await client.post(f"/characters/{cid}/hp/undo", json={"op_id": r.json()["hp_undo_id"]})).status_code == 200
    assert (await _scheda(client, cid))["current_hit_points"] == pieni
    assert (await _turno(client, cid))["reaction_used"] is False


@pytest.mark.caccia(id="CB-2971", fonte="2024 · Glossario · Riposo Breve · pag. 373 (Dado Ferita + Costituzione, minimo 1)",
                    zona="regola:2024/generali", voce="limiti",
                    copre=["carta:2024/general.md#Short Rest (Riposo Breve) (pag. 373)",
                           "carta:2024/general.md#Hit Point Dice (Dadi Ferita) (pag. 368)",
                           "POST /characters/{char_id}/hit_dice/spend"])
@pytest.mark.parametrize("dado,curati", [(1, 1), (10, 8)])
async def test_il_dado_ferita_cura_almeno_1_con_costituzione_negativa(client, dado, curati):
    cid = await _pg(client, "fighter", 3, constitution=6)
    j = await _scheda(client, cid)
    assert (await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 1})).status_code == 200
    r = await client.post(f"/characters/{cid}/hit_dice/spend", json={"class_id": j["classes"][0]["id"], "count": 1, "rolls": [dado]})
    assert r.status_code == 200, r.text
    assert (r.json()["con_bonus"], r.json()["healed"]) == (-2, curati)
