"""Controlli della zona regola:2014/incantesimi-A-C (parte incantesimi-a-c)."""
import json
from pathlib import Path

import pytest

from core.rules.catalog.spells import spell_effect

CATALOGO = Path(__file__).resolve().parents[2] / "webapp" / "src" / "data" / "srd" / "spells.json"


async def _pg(client, classe, livello, sottoclasse=None, **punteggi) -> int:
    r = await client.post("/characters", json={"name": "Incantatore", "rules_edition": "2014", "initial_class": {
        "class_name": classe, "level": livello, "subclass": sottoclasse}})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    for caratteristica, valore in punteggi.items():
        r = await client.patch(f"/characters/{cid}/ability_scores/{caratteristica}", json={"value": valore})
        assert r.status_code == 200, r.text
    return cid


async def _scheda(client, cid) -> dict:
    return (await client.get(f"/characters/{cid}")).json()


def _voce(indice: str) -> dict:
    return next(s for s in json.loads(CATALOGO.read_text(encoding="utf-8"))["items"] if s["index"] == indice)


async def _dal_catalogo(client, cid, indice) -> dict:
    """L'incantesimo aggiunto dal catalogo SRD 2014 con i campi che il client manda (spellToForm, catalog.ts)."""
    e = _voce(indice)
    corpo = {
        "name": e["name"]["it"], "level": e["level"], "casting_time": e["casting_time"]["it"], "duration": e["duration"]["it"],
        "components": ", ".join(e["components"]), "is_concentration": e["concentration"], "is_ritual": e["ritual"],
        "damage_dice": e.get("damage_dice"), "damage_type": e.get("damage_type"), "attack_save": e.get("attack_type"),
        "school": e.get("school"), "srd_index": e["index"],
        "higher_levels_dice": e.get("higher_levels_dice") if e.get("damage_dice") else None,
        "extra_damage_dice": e.get("extra_damage_dice"), "extra_damage_type": e.get("extra_damage_type"),
        "class_id": (await _scheda(client, cid))["classes"][0]["id"], "is_prepared": e["level"] > 0,
    }
    r = await client.post(f"/characters/{cid}/spells", json={k: v for k, v in corpo.items() if v not in (None, "")})
    assert r.status_code == 201, r.text
    return r.json()


async def _incantesimo(client, cid, indice) -> dict:
    return next(s for s in (await client.get(f"/characters/{cid}/spells")).json() if s["srd_index"] == indice)


async def _opzioni(client, cid, tiro) -> list[str]:
    r = await client.get(f"/characters/{cid}/roll-options", params={"roll": tiro})
    assert r.status_code == 200, r.text
    return [o["key"] for o in r.json()]


# ---------------------------------------------------------------------------
# Difformità
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-3211", fonte="2014 · Incantesimi · Arma Spirituale · pag. 215", zona="regola:2014/incantesimi-A-C", voce="limiti",
                    copre=["carta:2014/spells.md#Arma Spirituale", "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
@pytest.mark.parametrize("slot, dadi_attesi", [(4, 2), (6, 3), (8, 4), (9, 4)])
@pytest.mark.xfail(strict=True, reason="CB-3211: difforme dal manuale, confermato")
async def test_arma_spirituale_aggiunge_un_d8_ogni_due_livelli_di_slot_oltre_il_secondo(client, slot, dadi_attesi):
    cid = await _pg(client, "cleric", 3, "Dominio della Vita", wisdom=16)  # Arma Spirituale sempre preparata dal dominio
    arma = await _incantesimo(client, cid, "spiritual-weapon")
    r = await client.post(f"/characters/{cid}/spells/{arma['id']}/roll_damage", json={"casting_level": slot})
    assert r.status_code == 200, r.text
    assert len(r.json()["main_rolls"]) == dadi_attesi


@pytest.mark.caccia(id="CB-3212", fonte="2014 · Incantesimi · Arma Spirituale · pag. 215", zona="regola:2014/incantesimi-A-C", voce="regola",
                    copre=["carta:2014/spells.md#Arma Spirituale", "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
@pytest.mark.xfail(strict=True, reason="CB-3212: difforme dal manuale, confermato")
async def test_il_danno_di_arma_spirituale_somma_il_modificatore_da_incantatore(client, dadi):
    cid = await _pg(client, "cleric", 3, "Dominio della Vita", wisdom=16)  # Saggezza +3
    arma = await _incantesimo(client, cid, "spiritual-weapon")
    dadi(5)
    r = await client.post(f"/characters/{cid}/spells/{arma['id']}/roll_damage", json={"casting_level": 2})
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 5 + 3


@pytest.mark.caccia(id="CB-3213", fonte="2014 · Incantesimi · Colpo Infuocato · pag. 222", zona="regola:2014/incantesimi-A-C", voce="regola",
                    copre=["carta:2014/spells.md#Colpo Infuocato", "POST /characters/{char_id}/spells",
                           "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
@pytest.mark.xfail(strict=True, reason="CB-3213: difforme dal manuale, confermato")
async def test_colpo_infuocato_preso_dal_catalogo_infligge_anche_4d6_radiosi(client):
    cid = await _pg(client, "cleric", 9, wisdom=16)
    colpo = await _dal_catalogo(client, cid, "flame-strike")
    r = await client.post(f"/characters/{cid}/spells/{colpo['id']}/roll_damage", json={"casting_level": 5})
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert (len(corpo["main_rolls"]), corpo["damage_type"]) == (4, "fire")
    assert len(corpo["extra_rolls"]) == 4 and corpo["extra_kind"] == "d6"


@pytest.mark.caccia(id="CB-3214", fonte="2014 · Incantesimi · Cerchio Magico · pag. 221", zona="regola:2014/incantesimi-A-C", voce="limiti",
                    copre=["carta:2014/spells.md#Cerchio Magico", "POST /characters/{char_id}/spells/{spell_id}/use"])
@pytest.mark.parametrize("slot, ore", [(4, 2), (5, 3)])
async def test_cerchio_magico_dura_un_ora_in_piu_per_ogni_slot_oltre_il_terzo(client, slot, ore):
    cid = await _pg(client, "cleric", 9, wisdom=16)
    cerchio = await _dal_catalogo(client, cid, "magic-circle")
    r = await client.post(f"/characters/{cid}/spells/{cerchio['id']}/use", json={"slot_level": slot})
    assert r.status_code == 200, r.text
    orologio = next(s for s in (await _scheda(client, cid))["active_states"] if s["key"] == "spell_cast:magic_circle")
    assert orologio["rounds_left"] == 600 * ore


@pytest.mark.caccia(id="CB-3215", fonte="2014 · Incantesimi · Colpo Accurato · pag. 222", zona="regola:2014/incantesimi-A-C", voce="regola",
                    copre=["carta:2014/spells.md#Colpo Accurato", "POST /characters/{char_id}/spells/{spell_id}/use",
                           "POST /characters/{char_id}/rounds/tick", "GET /characters/{char_id}/roll-options"])
@pytest.mark.xfail(strict=True, reason="CB-3215: difforme dal manuale, confermato")
async def test_il_vantaggio_di_colpo_accurato_vale_ancora_nel_turno_successivo(client):
    cid = await _pg(client, "wizard", 1, intelligence=16)
    colpo = await _dal_catalogo(client, cid, "true-strike")
    r = await client.post(f"/characters/{cid}/spells/{colpo['id']}/use", json={})
    assert r.status_code == 200, r.text
    assert "spell:true_strike:advantage" in await _opzioni(client, cid, "attack")
    r = await client.post(f"/characters/{cid}/rounds/tick")  # passa il round: è il turno successivo di chi l'ha lanciato
    assert r.status_code == 200, r.text
    assert "spell:true_strike:advantage" in await _opzioni(client, cid, "attack")


@pytest.mark.caccia(id="CB-3216", fonte="2014 · Incantesimi · Contattare Altri Piani · pag. 224", zona="regola:2014/incantesimi-A-C", voce="regola",
                    copre=["carta:2014/spells.md#Contattare Altri Piani", "GET /characters/{char_id}/spells"])
async def test_contattare_altri_piani_non_mostra_la_cd_di_chi_lancia_al_posto_della_cd_15(client):
    cid = await _pg(client, "warlock", 9, charisma=10)  # CD degli incantesimi 8 + 4 + 0 = 12
    await _dal_catalogo(client, cid, "contact-other-plane")
    contatto = await _incantesimo(client, cid, "contact-other-plane")
    # la scheda mostra «TS · CD n» per un incantesimo SAVE: il TS di Intelligenza di questo incantesimo ha CD 15 fissa
    assert not (contatto["attack_save"] == "SAVE" and contatto["save_dc"] != 15)


@pytest.mark.caccia(id="CB-3217", fonte="2014 · Incantesimi · Colpo Infuocato · pag. 222", zona="regola:2014/incantesimi-A-C", voce="persistenza",
                    copre=["carta:2014/spells.md#Colpo Infuocato", "POST /characters/{char_id}/spells", "GET /characters/{char_id}/spells"])
@pytest.mark.xfail(strict=True, reason="CB-3217: difforme dal manuale, confermato")
async def test_la_seconda_parte_del_danno_di_colpo_infuocato_scritta_all_aggiunta_resta_salvata(client):
    cid = await _pg(client, "cleric", 9, wisdom=16)
    classe = (await _scheda(client, cid))["classes"][0]["id"]
    r = await client.post(f"/characters/{cid}/spells", json={
        "name": "Colpo Infuocato", "level": 5, "class_id": classe, "is_prepared": True, "attack_save": "SAVE",
        "damage_dice": "4d6", "damage_type": "fire", "higher_levels_dice": "1d6",
        "extra_damage_dice": "4d6", "extra_damage_type": "radiant"})
    assert r.status_code == 201, r.text
    salvato = next(s for s in (await client.get(f"/characters/{cid}/spells")).json() if s["id"] == r.json()["id"])
    assert (salvato["extra_damage_dice"], salvato["extra_damage_type"]) == ("4d6", "radiant")


# ---------------------------------------------------------------------------
# Regole che restano giuste
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-3218", fonte="2014 · Incantesimi · Aiuto · pag. 211", zona="regola:2014/incantesimi-A-C", voce="regola",
                    copre=["carta:2014/spells.md#Aiuto", "POST /characters/{char_id}/spells/{spell_id}/use"])
async def test_aiuto_con_slot_di_terzo_alza_massimo_e_attuali_di_10(client):
    cid = await _pg(client, "cleric", 5, wisdom=16)
    aiuto = await _dal_catalogo(client, cid, "aid")
    prima = await _scheda(client, cid)
    r = await client.post(f"/characters/{cid}/spells/{aiuto['id']}/use", json={"slot_level": 3})
    assert r.status_code == 200, r.text
    dopo = await _scheda(client, cid)
    assert dopo["computed"]["hp_max_effective"] == prima["computed"]["hp_max_effective"] + 10
    assert dopo["current_hit_points"] == prima["current_hit_points"] + 10


@pytest.mark.caccia(id="CB-3219", fonte="2014 · Incantesimi · Armatura di Agathys · pag. 215", zona="regola:2014/incantesimi-A-C", voce="interazione",
                    copre=["carta:2014/spells.md#Armatura di Agathys", "POST /characters/{char_id}/spells/{spell_id}/use"])
async def test_armatura_di_agathys_con_lo_slot_del_patto_di_terzo_da_15_pf_temporanei(client):
    cid = await _pg(client, "warlock", 5, charisma=16)  # slot del patto di 3° livello
    armatura = await _dal_catalogo(client, cid, "armor-of-agathys")
    patto = next(s for s in (await _scheda(client, cid))["spell_slots"] if s["is_pact"])
    assert patto["level"] == 3
    r = await client.post(f"/characters/{cid}/spells/{armatura['id']}/use", json={"slot_id": patto["id"]})
    assert r.status_code == 200, r.text
    assert (await _scheda(client, cid))["temp_hp"] == 15


@pytest.mark.caccia(id="CB-3220", fonte="2014 · Incantesimi · Cura Ferite e Cura Ferite di Massa · pag. 228", zona="regola:2014/incantesimi-A-C",
                    voce="limiti",
                    copre=["carta:2014/spells.md#Cura Ferite", "carta:2014/spells.md#Cura Ferite di Massa",
                           "POST /characters/{char_id}/spells/{spell_id}/roll_healing"])
@pytest.mark.parametrize("indice, slot, dadi_attesi", [
    ("cure-wounds", 1, 1), ("cure-wounds", 3, 3), ("mass-cure-wounds", 5, 3), ("mass-cure-wounds", 7, 5)])
async def test_le_cure_ferite_tirano_i_d8_dello_slot_piu_il_modificatore(client, indice, slot, dadi_attesi):
    cid = await _pg(client, "druid", 9, wisdom=16)  # Saggezza +3
    cura = await _dal_catalogo(client, cid, indice)
    r = await client.post(f"/characters/{cid}/spells/{cura['id']}/roll_healing", json={"casting_level": slot})
    assert r.status_code == 200, r.text
    assert (len(r.json()["main_rolls"]), r.json()["main_kind"], r.json()["modifier"]) == (dadi_attesi, "d8", 3)


@pytest.mark.caccia(id="CB-3221", fonte="2014 · Incantesimi · Beffa Crudele · pag. 217", zona="regola:2014/incantesimi-A-C", voce="limiti",
                    copre=["carta:2014/spells.md#Beffa Crudele", "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
@pytest.mark.parametrize("livello, dadi_attesi", [(1, 1), (4, 1), (5, 2), (10, 2), (11, 3), (16, 3), (17, 4), (20, 4)])
async def test_beffa_crudele_cresce_al_5_11_e_17_livello(client, livello, dadi_attesi):
    cid = await _pg(client, "bard", livello, charisma=16)
    beffa = await _dal_catalogo(client, cid, "vicious-mockery")
    r = await client.post(f"/characters/{cid}/spells/{beffa['id']}/roll_damage", json={})
    assert r.status_code == 200, r.text
    assert (len(r.json()["main_rolls"]), r.json()["main_kind"]) == (dadi_attesi, "d4")


@pytest.mark.caccia(id="CB-3222", fonte="2014 · Incantesimi · Benedizione · pag. 217", zona="regola:2014/incantesimi-A-C", voce="regola",
                    copre=["carta:2014/spells.md#Benedizione"])
def test_benedizione_tre_bersagli_piu_uno_per_slot_e_d4_su_attacchi_e_tiri_salvezza():
    effetto, variante = spell_effect("2014", "bless")
    assert [effetto.max_targets("2014", slot) for slot in (1, 2, 3)] == [3, 4, 5]
    (opzione,) = variante.options
    assert set(opzione.rolls) >= {"attack", "save", "death_save"} and not {"skill", "ability"} & set(opzione.rolls)
    assert opzione.extra_dice(None, {}) == "1d4" and (variante.concentration, variante.rounds) == (True, 10)


@pytest.mark.caccia(id="CB-3223", fonte="2014 · Incantesimi · Arma Magica · pag. 215", zona="regola:2014/incantesimi-A-C", voce="limiti",
                    copre=["carta:2014/spells.md#Arma Magica"])
@pytest.mark.parametrize("slot, bonus", [(2, 1), (3, 1), (4, 2), (5, 2), (6, 3), (9, 3)])
def test_arma_magica_da_piu_uno_piu_due_dal_quarto_piu_tre_dal_sesto(slot, bonus):
    _effetto, variante = spell_effect("2014", "magic-weapon")
    dati = {"slot_level": slot, "choices": {"item_id": "7"}}
    valori = {m.target: m.value for m in variante.modifiers(dati)}
    assert (valori["attack"], valori["damage"]) == (bonus, bonus)
    assert variante.concentration is True and variante.rounds == 600


@pytest.mark.caccia(id="CB-3224", fonte="2014 · Incantesimi · Cura Ferite · pag. 228; 2024 · Incantesimi · Cura Ferite · pag. 259",
                    zona="regola:2014/incantesimi-A-C", voce="edizioni",
                    copre=["carta:2014/spells.md#Cura Ferite", "carta:2024/spells.md#Cura Ferite",
                           "POST /characters/{char_id}/spells/{spell_id}/roll_healing"])
@pytest.mark.parametrize("edizione, dadi_attesi", [("2014", 2), ("2024", 4)])
async def test_cura_ferite_con_slot_di_secondo_segue_l_edizione_di_chi_lancia(client, edizione, dadi_attesi):
    r = await client.post("/characters", json={"name": "Druido", "rules_edition": edizione,
                                               "initial_class": {"class_name": "druid", "level": 3}})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    classe = (await _scheda(client, cid))["classes"][0]["id"]
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Cura Ferite", "level": 1, "srd_index": "cure-wounds",
                                                            "class_id": classe, "is_prepared": True})
    assert r.status_code == 201, r.text
    r = await client.post(f"/characters/{cid}/spells/{r.json()['id']}/roll_healing", json={"casting_level": 2})
    assert r.status_code == 200, r.text
    assert (len(r.json()["main_rolls"]), r.json()["main_kind"]) == (dadi_attesi, "d8")
