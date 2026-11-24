"""Controlli della zona regola:2024/razze."""
import json

import pytest

from core.data.species_2024 import DRAGON_ANCESTRY, SPECIES_2024
from tests.integration.rules.test_2014_fighter_styles import _item

LUCK = "species.2024_halfling_luck"
FIRE_BURN = "species.2024_goliath_giant_ancestry_fire"


async def _pg(client, specie, scelte, classe="fighter", livello=1, **punteggi):
    r = await client.post("/characters", json={"name": "S", "rules_edition": "2024", "species_2024": {"key": specie, "options": scelte},
                                               "initial_class": {"class_name": classe, "level": livello}})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    for abilita, valore in punteggi.items():
        assert (await client.patch(f"/characters/{cid}/ability_scores/{abilita}", json={"value": valore})).status_code == 200
    return cid


async def _scheda(client, cid):
    r = await client.get(f"/characters/{cid}")
    assert r.status_code == 200, r.text
    return r.json()


async def _riga(client, cid, chiave):
    return next((a for a in (await _scheda(client, cid))["abilities"] if a["feature_key"] == chiave), None)


async def _usa(client, cid, chiave, **corpo):
    return await client.post(f"/characters/{cid}/features/{chiave}/use", json=corpo)


async def _incantesimi(client, cid):
    return {s.get("srd_index"): s for s in (await client.get(f"/characters/{cid}/spells")).json() if s.get("srd_index")}


async def _dardo_di_fuoco(client, cid):
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Dardo di fuoco", "level": 0, "attack_save": "ATK",
                                                             "damage_dice": "1d10", "damage_type": "fire", "is_prepared": True})
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ---------------------------------------------------------------------------
# Rossi
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-3511", fonte="2024 · Specie · Halfling · Fortuna · pag. 193", zona="regola:2024/razze", voce="regola",
                    copre=["carta:2024/races.md#Halfling / Halfling (pag. 193)", "POST /characters/{char_id}/items/{item_id}/attack",
                           "POST /characters/{char_id}/last-roll/options"])
@pytest.mark.xfail(strict=True, reason="CB-3511: difforme dal manuale, confermato")
async def test_fortuna_ritira_l_1_naturale_del_tiro_per_colpire_con_un_arma(client):
    cid = await _pg(client, "2024_halfling", {})
    arma = await _item(client, cid, "Spada", damage_dice="1d8", weapon_type="melee", properties=[])
    r = await client.post(f"/characters/{cid}/items/{arma}/attack", json={"die": 1, "confirm_extra_attack": True, "defer_damage": True})
    assert r.status_code == 200, r.text
    assert r.json()["to_hit_die"] == 1
    # il tiro per colpire è un Test d20: l'1 naturale si ritira e vale il nuovo dado
    r = await client.post(f"/characters/{cid}/last-roll/options", json={"options": [LUCK], "dice": [15]})
    assert r.status_code == 200, r.text
    assert r.json()["die"] == 15


@pytest.mark.caccia(id="CB-3512", fonte="2024 · Specie · Halfling · Fortuna · pag. 193; Regole di gioco · Vantaggio e Svantaggio, rilanci · pag. 12-13",
                    zona="regola:2024/razze", voce="interazione",
                    copre=["carta:2024/races.md#Halfling / Halfling (pag. 193)",
                           "carta:2024/general.md#Vantaggio e Svantaggio / Advantage/Disadvantage (pag. 12-13)",
                           "POST /characters/{char_id}/saving_throws/{ability}/roll", "POST /characters/{char_id}/last-roll/options"])
@pytest.mark.xfail(strict=True, reason="CB-3512: difforme dal manuale, confermato")
async def test_fortuna_con_svantaggio_ritira_solo_l_1_e_lo_svantaggio_resta(client):
    cid = await _pg(client, "2024_halfling", {})
    r = await client.post(f"/characters/{cid}/saving_throws/wisdom/roll", json={"mode": "disadvantage", "dice": [1, 15]})
    assert r.status_code == 200, r.text
    assert r.json()["die"] == 1
    r = await client.post(f"/characters/{cid}/last-roll/options", json={"options": [LUCK], "dice": [18]})
    assert r.status_code == 200, r.text
    # si ritira solo il d20 che ha fatto 1: l'altro (15) resta e con lo svantaggio vale il più basso
    assert r.json()["die"] == 15, r.json()


@pytest.mark.caccia(id="CB-3513", fonte="2024 · Specie · Goliath · Ascendenza gigante, Ardore del fuoco · pag. 192", zona="regola:2024/razze",
                    voce="regola", copre=["carta:2024/races.md#Goliath / Goliath (pag. 192)", "POST /characters/{char_id}/spells/{spell_id}/attack",
                                          "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
@pytest.mark.xfail(strict=True, reason="CB-3513: difforme dal manuale, confermato")
async def test_ardore_del_fuoco_vale_anche_quando_colpisci_con_un_attacco_con_incantesimo(client):
    cid = await _pg(client, "2024_goliath", {"giant": "fire"}, classe="wizard")
    dardo = await _dardo_di_fuoco(client, cid)
    r = await client.post(f"/characters/{cid}/spells/{dardo}/attack", json={"die": 15})
    assert r.status_code == 200, r.text
    # Dardo di fuoco è un attacco: colpito il bersaglio, l'Ardore aggiunge 1d10 di fuoco e spende un uso
    r = await client.post(f"/characters/{cid}/spells/{dardo}/roll_damage", json={"options": [FIRE_BURN]})
    assert r.status_code == 200, r.text
    assert (await _riga(client, cid, FIRE_BURN))["uses"] == 1


@pytest.mark.caccia(id="CB-3514", fonte="2024 · Specie · Aasimar · Rivelazione celeste · pag. 186", zona="regola:2024/razze", voce="regola",
                    copre=["carta:2024/races.md#Aasimar / Aasimar (pag. 186)", "POST /characters/{char_id}/features/{feature_key}/use",
                           "POST /characters/{char_id}/attack/{attack_id}/damage"])
@pytest.mark.parametrize("forma,tipo", [("wings", "radiant"), ("shroud", "necrotic")])
@pytest.mark.xfail(strict=True, reason="CB-3514: difforme dal manuale, confermato")
async def test_i_danni_extra_della_rivelazione_celeste_hanno_il_tipo_della_forma(client, forma, tipo):
    cid = await _pg(client, "2024_aasimar", {"size": "medium"}, livello=3)
    assert (await _usa(client, cid, "species.2024_aasimar_celestial_revelation", params={"form": forma})).status_code == 200
    arma = await _item(client, cid, "Spada", damage_dice="1d8", weapon_type="melee", properties=[])
    r = await client.post(f"/characters/{cid}/items/{arma}/attack", json={"die": 15, "confirm_extra_attack": True, "defer_damage": True})
    assert r.status_code == 200, r.text
    r = await client.post(f"/characters/{cid}/attack/{r.json()['attack_id']}/damage",
                          json={"options": ["species.2024_aasimar_revelation_damage"], "option_inputs": {}})
    assert r.status_code == 200, r.text
    esito = r.json()["option_result"]
    assert esito["keys"] == ["species.2024_aasimar_revelation_damage"]
    # i danni pari alla competenza sono necrotici col Manto, radianti con le altre forme: non del tipo dell'arma
    assert tipo in json.dumps(esito), esito


@pytest.mark.caccia(id="CB-3515", fonte="2024 · Specie · Regole comuni · pag. 177: le specie non danno aumenti di caratteristica", zona="regola:2024/razze",
                    voce="edizioni", copre=["carta:2024/races.md#Nano / Dwarf (pag. 188)", "POST /characters"])
async def test_un_personaggio_2024_non_riceve_aumenti_di_caratteristica_dalla_razza(client):
    r = await client.post("/characters", json={"name": "B", "rules_edition": "2024", "ability_scores": {"constitution": 14},
                                               "species": {"name": "Nano", "ability_bonuses": {"con": 2}},
                                               "initial_class": {"class_name": "fighter"}})
    if r.status_code == 422:
        return
    assert r.status_code == 201, r.text
    costituzione = next(a["value"] for a in r.json()["ability_scores"] if a["name"] == "constitution")
    assert costituzione == 14


# ---------------------------------------------------------------------------
# Verdi
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-3517", fonte="2024 · Specie · Dragonide · Arma a soffio e Volo draconico · pag. 187", zona="regola:2024/razze",
                    voce="interazione", copre=["carta:2024/races.md#Dragonide / Dragonborn (pag. 187)", "POST /characters/{char_id}/classes",
                                               "POST /characters/{char_id}/features/{feature_key}/use"])
async def test_soffio_e_volo_del_dragonide_seguono_il_livello_del_personaggio_in_multiclasse(client):
    cid = await _pg(client, "2024_dragonborn", {"ancestry": "white"}, livello=3, constitution=14)
    assert await _riga(client, cid, "species.2024_dragonborn_draconic_flight") is None
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "wizard", "level": 2})
    assert r.status_code in (200, 201), r.text
    soffio = await _riga(client, cid, "species.2024_dragonborn_breath_weapon")
    assert (soffio["max_uses"], soffio["restoration_type"]) == (3, "long_rest")  # competenza 3 al livello 5
    r = await _usa(client, cid, "species.2024_dragonborn_breath_weapon")
    assert r.status_code == 200, r.text
    assert len(r.json()["rolls"]) == 2  # 2d10 dal livello 5 del personaggio
    assert "CD 13" in r.json()["message"]["it"] and "cold" in r.json()["message"]["it"]  # 8 + Cos 2 + competenza 3
    assert await _riga(client, cid, "species.2024_dragonborn_draconic_flight") is not None
    assert (await _scheda(client, cid))["computed"]["resistances"] == ["cold"]


@pytest.mark.caccia(id="CB-3518", fonte="2024 · Specie · Nano · Robustezza nanica, Resilienza nanica, Scurovisione · pag. 188", zona="regola:2024/razze",
                    voce="regola", copre=["carta:2024/races.md#Nano / Dwarf (pag. 188)", "POST /characters/{char_id}/classes", "GET /characters/{char_id}"])
async def test_robustezza_nanica_aggiunge_un_pf_per_ogni_livello_anche_in_multiclasse(client):
    cid = await _pg(client, "2024_dwarf", {})
    scheda = await _scheda(client, cid)
    assert scheda["computed"]["hp_max_effective"] == scheda["hit_points"] + 1
    assert {"type": "darkvision", "range_ft": 120} in scheda["computed"]["senses"]
    assert "poison" in scheda["computed"]["resistances"]
    assert (await client.post(f"/characters/{cid}/classes", json={"class_name": "wizard", "level": 1})).status_code in (200, 201)
    scheda = await _scheda(client, cid)
    assert scheda["computed"]["hp_max_effective"] == scheda["hit_points"] + 2


@pytest.mark.caccia(id="CB-3519", fonte="2024 · Specie · Orco · Scarica di adrenalina · pag. 195", zona="regola:2024/razze", voce="regola",
                    copre=["carta:2024/races.md#Orco / Orc (pag. 195)", "POST /characters/{char_id}/features/{feature_key}/use", "POST /characters/{char_id}/rest"])
async def test_scarica_di_adrenalina_da_pf_temporanei_pari_alla_competenza_e_torna_col_riposo_breve(client):
    cid = await _pg(client, "2024_orc", {}, livello=5)
    chiave = "species.2024_orc_adrenaline_rush"
    assert (await _riga(client, cid, chiave))["max_uses"] == 3
    r = await _usa(client, cid, chiave)
    assert r.status_code == 200, r.text
    assert (await _scheda(client, cid))["temp_hp"] == 3
    assert (await _riga(client, cid, chiave))["uses"] == 2
    assert (await client.post(f"/characters/{cid}/rest", json={"rest_type": "short"})).status_code == 200
    assert (await _riga(client, cid, chiave))["uses"] == 3


@pytest.mark.caccia(id="CB-3520", fonte="2024 · Specie · Tiefling · Eredità infernale e Presenza ultraterrena · pag. 196-197; Infernale · pag. 197",
                    zona="regola:2024/razze", voce="regola",
                    copre=["carta:2024/races.md#Tiefling / Tiefling (pag. 196-197)", "carta:2024/races.md#Infernale (eredità infernale) / Infernal (pag. 197)",
                           "POST /characters/{char_id}/spells/{spell_id}/use", "POST /characters/{char_id}/rest"])
async def test_incantesimo_di_eredita_gratis_una_volta_per_riposo_lungo_con_la_caratteristica_scelta(client):
    cid = await _pg(client, "2024_tiefling", {"size": "small", "legacy": "infernal", "spell_ability": "wisdom"}, livello=3, wisdom=16)
    incantesimi = await _incantesimi(client, cid)
    assert incantesimi["hellish-rebuke"]["save_dc"] == 13 and incantesimi["thaumaturgy"]["save_dc"] == 13  # 8 + Sag 3 + competenza 2
    assert incantesimi["hellish-rebuke"]["pact_cast"]["uses_left"] == 1
    r = await client.post(f"/characters/{cid}/spells/{incantesimi['hellish-rebuke']['id']}/use", json={"free_cast": True})
    assert r.status_code == 200, r.text
    assert (await client.post(f"/characters/{cid}/rest", json={"rest_type": "short"})).status_code == 200
    assert (await _incantesimi(client, cid))["hellish-rebuke"]["pact_cast"]["uses_left"] == 0
    assert (await client.post(f"/characters/{cid}/rest", json={"rest_type": "long"})).status_code == 200
    assert (await _incantesimi(client, cid))["hellish-rebuke"]["pact_cast"]["uses_left"] == 1
    assert (await _scheda(client, cid))["computed"]["resistances"] == ["fire"]


@pytest.mark.caccia(id="CB-3521", fonte="2024 · Specie · Elfo · Stirpe elfica · pag. 189-190; Drow · pag. 190", zona="regola:2024/razze", voce="limiti",
                    copre=["carta:2024/races.md#Elfo / Elf (pag. 189-190)", "carta:2024/races.md#Drow (lignaggio elfico) / Drow (pag. 190)",
                           "POST /characters", "GET /characters/{char_id}/spells"])
@pytest.mark.parametrize("livello,attesi", [(2, {"dancing-lights"}), (3, {"dancing-lights", "faerie-fire"}),
                                            (4, {"dancing-lights", "faerie-fire"}), (5, {"dancing-lights", "faerie-fire", "darkness"})])
async def test_incantesimi_del_lignaggio_drow_ai_livelli_3_e_5(client, livello, attesi):
    cid = await _pg(client, "2024_elf", {"lineage": "drow", "spell_ability": "charisma", "skill": "perception"}, livello=livello)
    assert set(await _incantesimi(client, cid)) & {"dancing-lights", "faerie-fire", "darkness"} == attesi
    assert {"type": "darkvision", "range_ft": 120} in (await _scheda(client, cid))["computed"]["senses"]


@pytest.mark.caccia(id="CB-3522", fonte="2024 · Specie · Halfling · Fortuna · pag. 193; Regole di gioco · Tiri salvezza contro morte · pag. 28-29",
                    zona="regola:2024/razze", voce="interazione",
                    copre=["carta:2024/races.md#Halfling / Halfling (pag. 193)", "carta:2024/general.md#Tiri salvezza contro morte / Death Saving Throws (pag. 28-29)",
                           "POST /characters/{char_id}/death_saves/roll",
                           "POST /characters/{char_id}/last-roll/options"])
async def test_fortuna_sull_1_del_tiro_contro_la_morte_toglie_i_due_fallimenti(client):
    cid = await _pg(client, "2024_halfling", {})
    assert (await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 0})).status_code == 200
    r = await client.post(f"/characters/{cid}/death_saves/roll", json={"die": 1})
    assert r.status_code == 200 and r.json()["failures"] == 2, r.text
    r = await client.post(f"/characters/{cid}/last-roll/options", json={"options": [LUCK], "dice": [15]})
    assert r.status_code == 200, r.text
    assert (await _scheda(client, cid))["death_saves"] == {"successes": 1, "failures": 0, "stable": False}


@pytest.mark.caccia(id="CB-3523", fonte="2024 · Specie · Goliath · Forma grande e velocità 35 piedi · pag. 192", zona="regola:2024/razze", voce="limiti",
                    copre=["carta:2024/races.md#Goliath / Goliath (pag. 192)", "POST /characters/{char_id}/features/{feature_key}/use",
                           "POST /characters/{char_id}/skills/{skill_name}/roll"])
async def test_forma_grande_dal_livello_5_vantaggio_alle_prove_di_forza_e_dieci_piedi_in_piu(client):
    basso = await _pg(client, "2024_goliath", {"giant": "hill"}, livello=4)
    assert await _riga(client, basso, "species.2024_goliath_large_form") is None
    cid = await _pg(client, "2024_goliath", {"giant": "hill"}, livello=5)
    assert (await _scheda(client, cid))["computed"]["speed"] == 35
    assert (await _usa(client, cid, "species.2024_goliath_large_form")).status_code == 200
    assert (await _scheda(client, cid))["computed"]["speed"] == 45
    r = await client.post(f"/characters/{cid}/skills/athletics/roll", json={"dice": [3, 15]})
    assert r.status_code == 200 and r.json()["mode_applied"] == "advantage", r.text
    r = await client.post(f"/characters/{cid}/skills/acrobatics/roll", json={"dice": [3]})
    assert r.status_code == 200 and r.json()["mode_applied"] == "normal", r.text


@pytest.mark.caccia(id="CB-3524", fonte="2024 · Specie · Dragonide, Stirpe draconica · pag. 187; taglie delle specie · pag. 186-197", zona="regola:2024/razze",
                    voce="regola", copre=["carta:2024/races.md#Dragonide / Dragonborn (pag. 187)", "carta:2024/races.md#Gnomo / Gnome (pag. 191)",
                                          "carta:2024/races.md#Umano / Human (pag. 194)"])
def test_tabella_delle_stirpi_draconiche_e_taglie_delle_specie():
    assert {k: v[2] for k, v in DRAGON_ANCESTRY.items()} == {
        "black": "acid", "blue": "lightning", "brass": "fire", "bronze": "lightning", "copper": "acid",
        "gold": "fire", "green": "poison", "red": "fire", "silver": "cold", "white": "cold"}
    taglie = {k: set(d.size) for k, d in SPECIES_2024.items()}
    assert taglie == {
        "2024_aasimar": {"medium", "small"}, "2024_dragonborn": {"medium"}, "2024_dwarf": {"medium"}, "2024_elf": {"medium"},
        "2024_gnome": {"small"}, "2024_goliath": {"medium"}, "2024_halfling": {"small"}, "2024_human": {"medium", "small"},
        "2024_orc": {"medium"}, "2024_tiefling": {"medium", "small"}}
