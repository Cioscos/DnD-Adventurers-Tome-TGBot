"""Controlli della zona regola:2024/incantesimi-A-C (parte incantesimi-a-c)."""
import json
from pathlib import Path

import pytest

from core.rules.catalog.spells import spell_effect
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, seed_session
from tests.integration.rules.test_2014_bard_inspiration import _seat
from tests.integration.rules.test_2014_fighter_eldritch_knight import _sword
from tests.integration.rules.test_2014_paladin_combat import _damage, _deferred, _listed
from tests.integration.rules.test_spell_effects_marks import _in_encounter

CATALOGO = Path(__file__).resolve().parents[2] / "webapp" / "src" / "data" / "srd" / "spells-2024.json"


async def _pg(client, classe, livello, sottoclasse=None, **punteggi) -> int:
    r = await client.post("/characters", json={"name": "Incantatore", "rules_edition": "2024", "initial_class": {
        "class_name": classe, "level": livello, "subclass": sottoclasse}})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    for caratteristica, valore in punteggi.items():
        r = await client.patch(f"/characters/{cid}/ability_scores/{caratteristica}", json={"value": valore})
        assert r.status_code == 200, r.text
    return cid


async def _scheda(client, cid) -> dict:
    r = await client.get(f"/characters/{cid}")
    assert r.status_code == 200, r.text
    return r.json()


def _voce(indice: str) -> dict:
    return next(s for s in json.loads(CATALOGO.read_text(encoding="utf-8"))["items"] if s["index"] == indice)


async def _dal_catalogo(client, cid, indice, preparato=True) -> dict:
    """L'incantesimo aggiunto dal catalogo SRD 2024 con i campi che il client manda (spellToForm, catalog.ts)."""
    e = _voce(indice)
    corpo = {
        "name": e["name"]["it"], "level": e["level"], "casting_time": e["casting_time"]["it"], "duration": e["duration"]["it"],
        "components": ", ".join(e["components"]), "is_concentration": e["concentration"], "is_ritual": e["ritual"],
        "damage_dice": e.get("damage_dice"), "damage_type": e.get("damage_type"), "attack_save": e.get("attack_type"),
        "school": e.get("school"), "srd_index": e["index"],
        "higher_levels_dice": e.get("higher_levels_dice") if e.get("damage_dice") else None,
        "class_id": (await _scheda(client, cid))["classes"][0]["id"], "is_prepared": preparato and e["level"] > 0,
    }
    r = await client.post(f"/characters/{cid}/spells", json={k: v for k, v in corpo.items() if v not in (None, "")})
    assert r.status_code == 201, r.text
    return r.json()


async def _incantesimo(client, cid, indice) -> dict:
    return next(s for s in (await client.get(f"/characters/{cid}/spells")).json() if s["srd_index"] == indice)


async def _stati(client, cid, chiave) -> list[dict]:
    return [s for s in (await _scheda(client, cid))["active_states"] or [] if s["key"] == chiave]


# ---------------------------------------------------------------------------
# Difformità
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-3661", fonte="2024 · Incantesimi · Colpo Accecante · pag. 247", zona="regola:2024/incantesimi-A-C", voce="regola",
                    copre=["carta:2024/spells.md#Colpo Accecante", "POST /characters/{char_id}/attack/{attack_id}/damage",
                           "GET /characters/{char_id}/target-effects/{effect_key}", "POST /characters/{char_id}/target-effects"])
@pytest.mark.xfail(strict=True, reason="CB-3661: difforme dal manuale, confermato")
async def test_colpo_accecante_acceca_subito_senza_un_primo_tiro_salvezza(client, test_session_factory, monkeypatch):
    _sid, cid = await _in_encounter(client, test_session_factory, monkeypatch)
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Colpo Accecante", "srd_index": "blinding-smite", "level": 3})
    assert r.status_code == 201, r.text
    assert (await client.post(f"/characters/{cid}/spell_slots", json={"level": 3, "total": 2})).status_code in (200, 201)
    spada = await _sword(client, cid)
    chiave = "spell:blinding_smite:hit"
    r = await _damage(client, cid, await _deferred(client, cid, spada, 15), [chiave], **{chiave: {"slot_level": 3}})
    assert r.status_code == 200, r.text
    anteprima = (await client.get(f"/characters/{cid}/target-effects/{chiave}")).json()
    goblin = next(c["id"] for c in anteprima["combatants"] if c["kind"] == "monster")
    r = await client.post(f"/characters/{cid}/target-effects", json={"combatant_id": goblin, "effect_key": chiave})
    assert r.status_code == 200, r.text
    # 2024: il bersaglio colpito è Accecato; il TS di Costituzione arriva solo alla fine di ogni suo turno
    assert r.json()["applied"] is True and r.json()["pending_save_id"] is None


@pytest.mark.caccia(id="CB-3662", fonte="2024 · Incantesimi · Colonna di fiamme · pag. 275", zona="regola:2024/incantesimi-A-C", voce="limiti",
                    copre=["carta:2024/spells.md#Colonna di fiamme", "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
@pytest.mark.parametrize("slot, dadi_per_tipo", [(6, 6), (9, 9)])
@pytest.mark.xfail(strict=True, reason="CB-3662: difforme dal manuale, confermato")
async def test_colonna_di_fiamme_con_slot_piu_alto_aggiunge_un_d6_di_ciascun_tipo(client, slot, dadi_per_tipo):
    cid = await _pg(client, "cleric", 9, "Dominio della Luce", wisdom=16)  # Colonna di fiamme sempre preparata dal dominio
    colonna = await _incantesimo(client, cid, "flame-strike")
    r = await client.post(f"/characters/{cid}/spells/{colonna['id']}/roll_damage", json={"casting_level": slot})
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert (len(corpo["main_rolls"]), corpo["damage_type"]) == (dadi_per_tipo, "fire")
    assert (len(corpo["extra_rolls"]), corpo["extra_damage_type"]) == (dadi_per_tipo, "radiant")


@pytest.mark.caccia(id="CB-3663", fonte="2024 · Incantesimi · Arma Spirituale · pag. 319-320", zona="regola:2024/incantesimi-A-C", voce="limiti",
                    copre=["carta:2024/spells.md#Arma Spirituale", "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
@pytest.mark.parametrize("slot, dadi_attesi", [(3, 2), (5, 4), (9, 8)])
async def test_arma_spirituale_del_dominio_della_guerra_aggiunge_un_d8_per_slot_oltre_il_secondo(client, slot, dadi_attesi):
    cid = await _pg(client, "cleric", 3, "Dominio della Guerra", wisdom=16)  # Arma Spirituale sempre preparata dal dominio
    arma = await _incantesimo(client, cid, "spiritual-weapon")
    r = await client.post(f"/characters/{cid}/spells/{arma['id']}/roll_damage", json={"casting_level": slot})
    assert r.status_code == 200, r.text
    assert (len(r.json()["main_rolls"]), r.json()["main_kind"]) == (dadi_attesi, "d8")


@pytest.mark.caccia(id="CB-3664", fonte="2024 · Incantesimi · Arma Spirituale · pag. 319-320", zona="regola:2024/incantesimi-A-C", voce="regola",
                    copre=["carta:2024/spells.md#Arma Spirituale", "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
@pytest.mark.xfail(strict=True, reason="CB-3664: difforme dal manuale, confermato")
async def test_il_danno_di_arma_spirituale_2024_somma_il_modificatore_da_incantatore(client, dadi):
    cid = await _pg(client, "cleric", 3, wisdom=16)  # Saggezza +3
    arma = await _dal_catalogo(client, cid, "spiritual-weapon")
    dadi(5)
    r = await client.post(f"/characters/{cid}/spells/{arma['id']}/roll_damage", json={"casting_level": 2})
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 5 + 3


@pytest.mark.caccia(id="CB-3665", fonte="2024 · Incantesimi · Cerchio Magico · pag. 293", zona="regola:2024/incantesimi-A-C", voce="limiti",
                    copre=["carta:2024/spells.md#Cerchio Magico", "POST /characters/{char_id}/spells/{spell_id}/use"])
@pytest.mark.parametrize("slot, ore", [(3, 1), pytest.param(4, 2, marks=pytest.mark.xfail(strict=True, reason="CB-3665: difforme dal manuale, confermato")), pytest.param(5, 3, marks=pytest.mark.xfail(strict=True, reason="CB-3665: difforme dal manuale, confermato"))])
async def test_cerchio_magico_2024_dura_un_ora_in_piu_per_ogni_slot_oltre_il_terzo(client, slot, ore):
    cid = await _pg(client, "cleric", 9, wisdom=16)
    cerchio = await _dal_catalogo(client, cid, "magic-circle")
    r = await client.post(f"/characters/{cid}/spells/{cerchio['id']}/use", json={"slot_level": slot})
    assert r.status_code == 200, r.text
    (orologio,) = await _stati(client, cid, "spell_cast:magic_circle")
    assert orologio["rounds_left"] == 600 * ore


@pytest.mark.caccia(id="CB-3666", fonte="2024 · Incantesimi · Contattare Altri Piani · pag. 255", zona="regola:2024/incantesimi-A-C", voce="regola",
                    copre=["carta:2024/spells.md#Contattare Altri Piani", "GET /characters/{char_id}/spells"])
@pytest.mark.xfail(strict=True, reason="CB-3666: difforme dal manuale, confermato")
async def test_contattare_altri_piani_2024_non_mostra_la_cd_di_chi_lancia_al_posto_della_cd_15(client):
    cid = await _pg(client, "wizard", 9, intelligence=10)  # CD degli incantesimi 8 + 4 + 0 = 12
    await _dal_catalogo(client, cid, "contact-other-plane", preparato=False)  # nel libro degli incantesimi
    contatto = await _incantesimo(client, cid, "contact-other-plane")
    # la scheda mostra «TS · CD n» per un incantesimo SAVE: il TS di Intelligenza lo fa chi lancia, con CD 15 fissa
    assert not (contatto["attack_save"] == "SAVE" and contatto["save_dc"] != 15)


@pytest.mark.caccia(id="CB-3667", fonte="2024 · Incantesimi · Arma Magica · pag. 295", zona="regola:2024/incantesimi-A-C", voce="interazione",
                    copre=["carta:2024/spells.md#Arma Magica", "POST /characters/{char_id}/spells/{spell_id}/use"])
@pytest.mark.xfail(strict=True, reason="CB-3667: difforme dal manuale, confermato")
async def test_rilanciare_arma_magica_2024_toglie_l_effetto_dall_arma_di_prima(client, test_session_factory):
    _sid, eroe = await seed_session(test_session_factory)
    as_user(PLAYER_ID)
    spada_eroe = await _sword(client, eroe)
    as_user(GM_ID)
    chierico = await _pg(client, "cleric", 3, "Dominio della Guerra", wisdom=16)  # Arma Magica sempre preparata dal dominio
    await _seat(test_session_factory, chierico)
    spada_chierico = await _sword(client, chierico)
    arma = (await _incantesimo(client, chierico, "magic-weapon"))["id"]
    r = await client.post(f"/characters/{chierico}/spells/{arma}/use",
                          json={"slot_level": 2, "targets": [eroe], "choices": {"item_id": str(spada_eroe)}})
    assert r.status_code == 200, r.text
    r = await client.post(f"/characters/{chierico}/spells/{arma}/use",
                          json={"slot_level": 2, "targets": [chierico], "choices": {"item_id": str(spada_chierico)},
                                "confirm": ["one_slot_per_turn"]})
    assert r.status_code == 200, r.text
    as_user(PLAYER_ID)
    # 2024: l'incantesimo finisce prima se lo lanci di nuovo
    assert await _stati(client, eroe, "spell:magic_weapon") == []


@pytest.mark.caccia(id="CB-3668", fonte="2024 · Incantesimi · Colpo dell'Esilio · pag. 245", zona="regola:2024/incantesimi-A-C", voce="regola",
                    copre=["carta:2024/spells.md#Colpo dell'Esilio", "POST /characters/{char_id}/spells/{spell_id}/use",
                           "GET /characters/{char_id}/roll-options"])
async def test_colpo_dell_esilio_2024_lanciato_prima_non_vale_con_un_arma_a_distanza(client):
    cid = await _pg(client, "paladin", 17, charisma=16)
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Colpo dell'Esilio", "srd_index": "banishing-smite", "level": 5,
                                                            "is_concentration": True})
    assert r.status_code == 201, r.text
    r = await client.post(f"/characters/{cid}/spells/{r.json()['id']}/use", json={"slot_level": 5})
    assert r.status_code == 200, r.text
    arco = await _sword(client, cid, weapon_type="ranged", damage_dice="1d8")
    # la carta 2024: dopo aver colpito con un'arma da mischia o un Colpo Senz'Armi
    assert "spell:banishing_smite:hit" not in [o["key"] for o in await _listed(client, cid, arco)]


@pytest.mark.caccia(id="CB-3669", fonte="2024 · Incantesimi · Arma Magica · pag. 295", zona="regola:2024/incantesimi-A-C", voce="interazione",
                    copre=["carta:2024/spells.md#Arma Magica", "POST /characters/{char_id}/spells/{spell_id}/use"])
async def test_arma_magica_del_dominio_2024_non_toglie_la_concentrazione_di_scudo_della_fede(client):
    cid = await _pg(client, "cleric", 3, "Dominio della Guerra", wisdom=16)  # entrambi sempre preparati dal dominio
    scudo = (await _incantesimo(client, cid, "shield-of-faith"))["id"]
    arma = (await _incantesimo(client, cid, "magic-weapon"))["id"]
    spada = await _sword(client, cid)
    assert (await client.post(f"/characters/{cid}/spells/{scudo}/use", json={"slot_level": 1})).status_code == 200
    r = await client.post(f"/characters/{cid}/spells/{arma}/use", json={"slot_level": 2, "choices": {"item_id": str(spada)},
                                                                       "confirm": ["one_slot_per_turn"]})
    assert r.status_code == 200, r.text
    # 2024: Arma Magica dura 1 ora senza concentrazione, Scudo della Fede resta
    assert r.json()["concentrating_spell_id"] == scudo


# ---------------------------------------------------------------------------
# Regole che restano giuste
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-3672", fonte="2024 · Incantesimi · Armatura di Agathys · pag. 243", zona="regola:2024/incantesimi-A-C", voce="regola",
                    copre=["carta:2024/spells.md#Armatura di Agathys", "POST /characters/{char_id}/spells/{spell_id}/use",
                           "PATCH /characters/{char_id}/hp"])
async def test_armatura_di_agathys_2024_da_5_pf_temporanei_per_slot_e_finisce_quando_sono_esauriti(client):
    cid = await _pg(client, "warlock", 3, charisma=16)  # slot del patto di 2° livello
    armatura = await _dal_catalogo(client, cid, "armor-of-agathys")
    patto = next(s for s in (await _scheda(client, cid))["spell_slots"] if s["is_pact"])
    r = await client.post(f"/characters/{cid}/spells/{armatura['id']}/use", json={"slot_id": patto["id"]})
    assert r.status_code == 200, r.text
    assert (await _scheda(client, cid))["temp_hp"] == 10
    assert len(await _stati(client, cid, "spell:armor_of_agathys")) == 1
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 10})
    assert r.status_code == 200, r.text
    assert await _stati(client, cid, "spell:armor_of_agathys") == []


@pytest.mark.caccia(id="CB-3673", fonte="2024 · Incantesimi · Armatura di Agathys · pag. 243", zona="regola:2024/incantesimi-A-C", voce="annullamento",
                    copre=["carta:2024/spells.md#Armatura di Agathys", "PATCH /characters/{char_id}/hp", "POST /characters/{char_id}/hp/undo"])
async def test_annullare_il_danno_che_ha_esaurito_l_armatura_di_agathys_la_ridà_con_i_pf_temporanei(client):
    cid = await _pg(client, "warlock", 3, charisma=16)
    armatura = await _dal_catalogo(client, cid, "armor-of-agathys")
    patto = next(s for s in (await _scheda(client, cid))["spell_slots"] if s["is_pact"])
    assert (await client.post(f"/characters/{cid}/spells/{armatura['id']}/use", json={"slot_id": patto["id"]})).status_code == 200
    danno = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 12})
    assert danno.status_code == 200, danno.text
    r = await client.post(f"/characters/{cid}/hp/undo", json={"op_id": danno.json()["hp_undo_id"]})
    assert r.status_code == 200, r.text
    assert r.json()["temp_hp"] == 10
    assert len(await _stati(client, cid, "spell:armor_of_agathys")) == 1


@pytest.mark.caccia(id="CB-3674", fonte="2014 · Incantesimi · Banchetto degli Eroi · pag. 217; 2024 · Incantesimi · Banchetto degli eroi · pag. 284",
                    zona="regola:2024/incantesimi-A-C", voce="edizioni",
                    copre=["carta:2014/spells.md#Banchetto degli Eroi", "carta:2024/spells.md#Banchetto degli eroi"])
@pytest.mark.parametrize("edizione, difesa", [("2014", "immunity:poison"), ("2024", "resistance:poison")])
def test_banchetto_degli_eroi_immunita_al_veleno_nel_2014_resistenza_nel_2024(edizione, difesa):
    effetto, variante = spell_effect(edizione, "heroes-feast")
    bersagli = {m.target for m in variante.modifiers({"feast_hp": 7})}
    altra = ({"immunity:poison", "resistance:poison"} - {difesa}).pop()
    assert difesa in bersagli and altra not in bersagli
    assert set(variante.immune_conditions) == {"frightened", "poisoned"} and variante.rounds == 14400  # 24 ore
    assert effetto.max_targets(edizione, 6) == 12


@pytest.mark.caccia(id="CB-3675", fonte="2024 · Incantesimi · Cura Ferite di Massa · pag. 296", zona="regola:2024/incantesimi-A-C", voce="limiti",
                    copre=["carta:2024/spells.md#Cura Ferite di Massa", "POST /characters/{char_id}/spells/{spell_id}/roll_healing"])
@pytest.mark.parametrize("slot, dadi_attesi", [(5, 5), (6, 6), (9, 9)])
async def test_cura_ferite_di_massa_2024_tira_5d8_piu_uno_per_slot_e_il_modificatore(client, slot, dadi_attesi):
    cid = await _pg(client, "druid", 9, wisdom=16)  # Saggezza +3
    cura = await _dal_catalogo(client, cid, "mass-cure-wounds")
    r = await client.post(f"/characters/{cid}/spells/{cura['id']}/roll_healing", json={"casting_level": slot})
    assert r.status_code == 200, r.text
    assert (len(r.json()["main_rolls"]), r.json()["main_kind"], r.json()["modifier"]) == (dadi_attesi, "d8", 3)


@pytest.mark.caccia(id="CB-3676", fonte="2024 · Incantesimi · Arma Magica · pag. 295", zona="regola:2024/incantesimi-A-C", voce="limiti",
                    copre=["carta:2024/spells.md#Arma Magica"])
@pytest.mark.parametrize("slot, bonus", [(2, 1), (3, 2), (5, 2), (6, 3), (9, 3)])
def test_arma_magica_2024_da_piu_uno_piu_due_dal_terzo_piu_tre_dal_sesto_senza_concentrazione(slot, bonus):
    _effetto, variante = spell_effect("2024", "magic-weapon")
    valori = {m.target: m.value for m in variante.modifiers({"slot_level": slot, "choices": {"item_id": "7"}})}
    assert (valori["attack"], valori["damage"]) == (bonus, bonus)
    assert variante.concentration is False and variante.rounds == 600


@pytest.mark.caccia(id="CB-3677", fonte="2024 · Incantesimi · Arma elementale · pag. 268", zona="regola:2024/incantesimi-A-C", voce="limiti",
                    copre=["carta:2024/spells.md#Arma elementale"])
@pytest.mark.parametrize("slot, bonus, dadi", [(3, 1, "1d4"), (4, 1, "1d4"), (5, 2, "2d4"), (6, 2, "2d4"), (7, 3, "3d4"), (9, 3, "3d4")])
def test_arma_elementale_2024_cresce_con_slot_di_quinto_e_settimo(slot, bonus, dadi):
    from types import SimpleNamespace
    _effetto, variante = spell_effect("2024", "elemental-weapon")
    dati = {"slot_level": slot, "choices": {"item_id": "7", "damage_type": "fire"}}
    assert {m.target: m.value for m in variante.modifiers(dati)}["attack"] == bonus
    fuoco = next(o for o in variante.options if o.key == "spell:elemental_weapon:damage:fire")
    assert fuoco.extra_dice(SimpleNamespace(spell_data=dati), {}) == dadi
    assert [c.options("2024") for c in variante.choices] == [["acid", "cold", "fire", "lightning", "thunder"]]
    assert variante.concentration is True and variante.rounds == 600


@pytest.mark.caccia(id="CB-3678", fonte="2024 · Incantesimi · Colpo Accecante · pag. 247", zona="regola:2024/incantesimi-A-C", voce="limiti",
                    copre=["carta:2024/spells.md#Colpo Accecante", "GET /characters/{char_id}/roll-options"])
async def test_colpo_accecante_2024_si_offre_dopo_il_colpo_con_3d8_piu_uno_per_slot(client):
    cid = await _pg(client, "paladin", 17, charisma=16)  # slot fino al 5°
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Colpo Accecante", "srd_index": "blinding-smite", "level": 3})
    assert r.status_code == 201, r.text
    spada = await _sword(client, cid)
    opzione = next(o for o in await _listed(client, cid, spada) if o["key"] == "spell:blinding_smite:hit")
    assert {s["level"]: s["dice"] for s in opzione["input_options"]} == {3: "3d8", 4: "4d8", 5: "5d8"}
    assert opzione["slot"] == "bonus"


@pytest.mark.caccia(id="CB-3679", fonte="2024 · Incantesimi · Aiuto · pag. 239", zona="regola:2024/incantesimi-A-C", voce="regola",
                    copre=["carta:2024/spells.md#Aiuto", "POST /characters/{char_id}/spells/{spell_id}/use"])
async def test_aiuto_2024_con_slot_di_quarto_alza_massimo_e_attuali_di_15(client):
    cid = await _pg(client, "cleric", 7, wisdom=16)
    aiuto = await _dal_catalogo(client, cid, "aid")
    prima = await _scheda(client, cid)
    r = await client.post(f"/characters/{cid}/spells/{aiuto['id']}/use", json={"slot_level": 4})
    assert r.status_code == 200, r.text
    dopo = await _scheda(client, cid)
    assert dopo["computed"]["hp_max_effective"] == prima["computed"]["hp_max_effective"] + 15
    assert dopo["current_hit_points"] == prima["current_hit_points"] + 15
