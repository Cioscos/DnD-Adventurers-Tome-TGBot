"""Controlli della zona regola:2024/incantesimi-S-Z (parte incantesimi-s-z)."""
import json
from pathlib import Path

import pytest

from core.rules.catalog.granted_spells import granted_spell
from core.rules.catalog.spells import spell_effect
from core.rules.spellcasting import casting_kind

_SRD24 = {s["index"]: s for s in json.loads(
    (Path(__file__).resolve().parents[2] / "webapp" / "src" / "data" / "srd" / "spells-2024.json").read_text(encoding="utf-8"))["items"]}


def _dal_catalogo(indice: str, **altro) -> dict:
    """La riga del catalogo SRD 2024 con i campi che il modulo della webapp manda quando il giocatore la aggiunge (spellToForm)."""
    e = _SRD24[indice]
    materiale = (e.get("material") or {}).get("it") if e.get("material") else None
    componenti = ", ".join(e["components"]) + (f" ({materiale})" if materiale and "M" in e["components"] else "")
    corpo = {"name": e["name"]["it"], "level": e["level"], "casting_time": e["casting_time"]["it"], "duration": e["duration"]["it"],
             "components": componenti, "is_concentration": e["concentration"], "is_ritual": e["ritual"],
             "damage_dice": e["damage_dice"], "damage_type": e["damage_type"], "attack_save": e["attack_type"],
             "school": e["school"], "srd_index": indice,
             "higher_levels_dice": e["higher_levels_dice"] if e["damage_dice"] and indice != "sleep" else None,
             "extra_damage_dice": e.get("extra_damage_dice"), "extra_damage_type": e.get("extra_damage_type"),
             "is_prepared": e["level"] > 0, **altro}
    return {k: v for k, v in corpo.items() if v not in (None, "")}


async def _pg(client, classe=None, livello=1, sottoclasse=None) -> int:
    corpo = {"name": "Incantatore", "rules_edition": "2024"}
    if classe:
        corpo["initial_class"] = {"class_name": classe, "level": livello, "subclass": sottoclasse}
    r = await client.post("/characters", json=corpo)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert (await _scheda(client, cid))["rules_edition"] == "2024"
    return cid


async def _scheda(client, cid) -> dict:
    r = await client.get(f"/characters/{cid}")
    assert r.status_code == 200, r.text
    return r.json()


async def _impara(client, cid, indice, **altro) -> int:
    classi = (await _scheda(client, cid))["classes"]
    corpo = _dal_catalogo(indice, **({"class_id": classi[0]["id"]} if classi else {}), **altro)
    r = await client.post(f"/characters/{cid}/spells", json=corpo)
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _concesso(client, cid, indice) -> dict:
    """La riga che un privilegio ha messo fra gli incantesimi (sempre preparata)."""
    righe = (await client.get(f"/characters/{cid}/spells")).json()
    return next(s for s in righe if s["srd_index"] == indice and s.get("always_prepared"))


async def _lancia(client, cid, sid, slot=None, **altro) -> dict:
    r = await client.post(f"/characters/{cid}/spells/{sid}/use", json={**({"slot_level": slot} if slot else {}), **altro})
    assert r.status_code == 200, r.text
    return r.json()


async def _danno(client, cid, sid, livello, **altro) -> dict:
    r = await client.post(f"/characters/{cid}/spells/{sid}/roll_damage", json={"casting_level": livello, **altro})
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# Difformità
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-3861", fonte="2024 · Incantesimi · Tempesta di Ghiaccio · pag. 287; Sciame di Meteore · pag. 298; Tempesta di Radiosità di Jallarzi · pag. 289",
                    zona="regola:2024/incantesimi-S-Z", voce="regola",
                    copre=["carta:2024/spells.md#Tempesta di ghiaccio", "carta:2024/spells.md#Sciame di Meteore",
                           "carta:2024/spells.md#Tempesta di radiosità di Jallarzi",
                           "POST /characters/{char_id}/spells", "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
@pytest.mark.parametrize("classe, livello, indice, slot, prima, seconda", [
    ("druid", 7, "ice-storm", 4, (2, "d10", "bludgeoning"), (4, "d6", "cold")),
    ("sorcerer", 17, "meteor-swarm", 9, (20, "d6", "fire"), (20, "d6", "bludgeoning")),
    ("warlock", 9, "jallarzis-storm-of-radiance", 5, (2, "d10", "radiant"), (2, "d10", "thunder")),
])
@pytest.mark.xfail(strict=True, reason="CB-3861: dati del catalogo corretti; resta CB-3217 (SpellCreate scarta extra_damage_*)")
async def test_incantesimo_2024_preso_dal_catalogo_infligge_anche_il_secondo_tipo_di_danno(client, classe, livello, indice, slot, prima, seconda):
    cid = await _pg(client, classe, livello)
    sid = await _impara(client, cid, indice)
    corpo = await _danno(client, cid, sid, slot)
    assert (len(corpo["main_rolls"]), corpo["main_kind"], corpo["damage_type"]) == prima
    assert (len(corpo["extra_rolls"]), corpo["extra_kind"], corpo["extra_damage_type"]) == seconda


@pytest.mark.caccia(id="CB-3862", fonte="2024 · Incantesimi · Tempesta di Radiosità di Jallarzi · pag. 289", zona="regola:2024/incantesimi-S-Z",
                    voce="limiti",
                    copre=["carta:2024/spells.md#Tempesta di radiosità di Jallarzi", "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
@pytest.mark.xfail(strict=True, reason="CB-3862: difforme dal manuale, confermato")
async def test_tempesta_di_radiosita_con_slot_alto_aggiunge_un_d10_di_ciascun_tipo(client):
    cid = await _pg(client, "warlock", 13)
    sid = await _impara(client, cid, "jallarzis-storm-of-radiance")
    corpo = await _danno(client, cid, sid, 7)
    assert (corpo["scaled_dice"], corpo["damage_type"]) == ("4d10", "radiant")
    assert (len(corpo["extra_rolls"]), corpo["extra_kind"], corpo["extra_damage_type"]) == (4, "d10", "thunder")  # 2d10 +1d10 per slot oltre il 5°


@pytest.mark.caccia(id="CB-3863", fonte="2024 · Incantesimi · Soffio del Drago · pag. 266", zona="regola:2024/incantesimi-S-Z", voce="regola",
                    copre=["carta:2024/spells.md#Soffio del drago", "POST /characters/{char_id}/spells/{spell_id}/use",
                           "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
async def test_soffio_del_drago_tira_3d6_del_tipo_scelto_piu_1d6_per_slot(client):
    cid = await _pg(client, "sorcerer", 5)
    sid = await _impara(client, cid, "dragons-breath")
    await _lancia(client, cid, sid, 3, choices={"damage_type": "fire"})
    r = await client.post(f"/characters/{cid}/spells/{sid}/roll_damage", json={"casting_level": 3})
    assert r.status_code == 200, r.text  # oggi 400: la riga del catalogo 2024 non ha dadi di danno
    assert (r.json()["scaled_dice"], r.json()["damage_type"], r.json()["save_halves"]) == ("4d6", "fire", True)


@pytest.mark.caccia(id="CB-3864", fonte="2024 · Incantesimi · Tempesta di Ghiaccio · pag. 287; Druido · Circolo del Mare · Incantesimi del Circolo",
                    zona="regola:2024/incantesimi-S-Z", voce="edizioni",
                    copre=["carta:2024/spells.md#Tempesta di ghiaccio", "POST /characters",
                           "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
@pytest.mark.parametrize("slot, dadi_attesi", [(4, "2d10"), (5, "3d10")])
async def test_tempesta_di_ghiaccio_concessa_nel_2024_usa_i_d10_del_manuale_2024(client, slot, dadi_attesi):
    cid = await _pg(client, "druid", 9, "Circolo del Mare")
    riga = await _concesso(client, cid, "ice-storm")
    corpo = await _danno(client, cid, riga["id"], slot)
    assert (corpo["scaled_dice"], corpo["damage_type"]) == (dadi_attesi, "bludgeoning")  # oggi 2d8 e +1d8: i valori 2014


@pytest.mark.caccia(id="CB-3865", fonte="2024 · Incantesimi · Spiriti Guardiani · pag. 319; Soffio del Drago · pag. 266; Tempesta di Nevischio · pag. 317; Scudo di Fuoco · pag. 274",
                    zona="regola:2024/incantesimi-S-Z", voce="regola",
                    copre=["carta:2024/spells.md#Spiriti Guardiani", "carta:2024/spells.md#Soffio del drago",
                           "carta:2024/spells.md#Tempesta di Nevischio", "carta:2024/spells.md#Scudo di fuoco"])
@pytest.mark.parametrize("indice, attesi", [
    ("spirit-guardians", {"attack_save": "SAVE", "damage_dice": "3d8", "higher_levels_dice": "1d8"}),  # Dominio della Guerra 2024
    ("dragons-breath", {"attack_save": "SAVE", "damage_dice": "3d6", "higher_levels_dice": "1d6"}),  # Stregoneria Draconica 2024
    ("sleet-storm", {"attack_save": "SAVE"}),  # Circolo della Terra polare 2024
    ("fire-shield", {"damage_dice": "2d8"}),  # Dominio della Guerra e Patrono Immondo 2024
])
def test_incantesimo_concesso_nel_2024_ha_ts_e_dadi_della_carta(indice, attesi):
    riga = granted_spell(indice, "2024")
    assert {campo: getattr(riga, campo) for campo in attesi} == attesi


@pytest.mark.caccia(id="CB-3866", fonte="2024 · Incantesimi · Saltare · pag. 290; Warlock · Balzo Ultraterreno · pag. 156", zona="regola:2024/incantesimi-S-Z",
                    voce="edizioni", copre=["carta:2024/spells.md#Saltare"])
def test_saltare_concesso_nel_2024_si_lancia_con_un_azione_bonus():
    assert casting_kind(granted_spell("jump", "2024")) == "bonus"  # oggi «1 azione», il tempo di lancio 2014


@pytest.mark.caccia(id="CB-3867", fonte="2024 · Incantesimi · Tentacoli Neri di Evard · pag. 270; Stregone · Incantesimi Psionici · pag. 145",
                    zona="regola:2024/incantesimi-S-Z", voce="interazione",
                    copre=["carta:2024/spells.md#Tentacoli neri di Evard", "POST /characters",
                           "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
async def test_tentacoli_neri_concessi_allo_stregone_aberrante_non_dimezzano_al_ts_superato(client):
    cid = await _pg(client, "sorcerer", 7, "Stregoneria Aberrante")
    riga = await _concesso(client, cid, "evards-black-tentacles")
    corpo = await _danno(client, cid, riga["id"], 4)
    assert (corpo["scaled_dice"], corpo["damage_type"]) == ("3d6", "bludgeoning")
    assert corpo["save_halves"] is False  # il danno arriva solo a chi fallisce il TS di Forza


@pytest.mark.caccia(id="CB-3868", fonte="2024 · Incantesimi · Tempesta di Vendetta · pag. 321", zona="regola:2024/incantesimi-S-Z", voce="regola",
                    copre=["carta:2024/spells.md#Tempesta di Vendetta", "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
async def test_tempesta_di_vendetta_2024_il_ts_superato_non_dimezza_il_tuono(client):
    cid = await _pg(client, "druid", 17)
    sid = await _impara(client, cid, "storm-of-vengeance")
    corpo = await _danno(client, cid, sid, 9)
    assert (len(corpo["main_rolls"]), corpo["damage_type"]) == (2, "thunder")
    assert corpo["save_halves"] is False  # chi supera il TS di Costituzione non subisce i 2d6 né resta Assordato


@pytest.mark.caccia(id="CB-3869", fonte="2024 · Incantesimi · Scudo di Fuoco · pag. 274", zona="regola:2024/incantesimi-S-Z", voce="regola",
                    copre=["carta:2024/spells.md#Scudo di fuoco", "POST /characters/{char_id}/spells/{spell_id}/use",
                           "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
async def test_scudo_di_fuoco_2024_freddo_infligge_danni_da_freddo(client):
    cid = await _pg(client, "sorcerer", 7)
    sid = await _impara(client, cid, "fire-shield")
    scheda = await _lancia(client, cid, sid, 4, choices={"shield": "cold"})
    assert any(s["key"] == "spell:fire_shield" for s in scheda["active_states"])
    corpo = await _danno(client, cid, sid, 4)
    assert (len(corpo["main_rolls"]), corpo["damage_type"]) == (2, "cold")


@pytest.mark.caccia(id="CB-3870", fonte="2024 · Incantesimi · Santuario · pag. 313", zona="regola:2024/incantesimi-S-Z", voce="interazione",
                    copre=["carta:2024/spells.md#Santuario", "POST /characters/{char_id}/spells/{spell_id}/use"])
async def test_santuario_2024_finisce_quando_il_protetto_lancia_un_incantesimo(client):
    cid = await _pg(client, "cleric", 1)
    santuario = await _impara(client, cid, "sanctuary")
    trucchetto = await _impara(client, cid, "thaumaturgy")
    scheda = await _lancia(client, cid, santuario, 1)
    assert any(s["key"] == "spell:sanctuary" for s in scheda["active_states"])
    scheda = await _lancia(client, cid, trucchetto)
    assert not any(s["key"] == "spell:sanctuary" for s in scheda["active_states"])


@pytest.mark.caccia(id="CB-3871", fonte="2024 · Incantesimi · Serratura Arcana · pag. 242; Santificare · pag. 283; Simulacro · pag. 317; Simbolo · pag. 329; Vera Resurrezione · pag. 336; Visione del Vero · pag. 336",
                    zona="regola:2024/incantesimi-S-Z", voce="regola",
                    copre=["carta:2024/spells.md#Serratura Arcana", "carta:2024/spells.md#Santificare", "carta:2024/spells.md#Simulacro",
                           "carta:2024/spells.md#Simbolo", "carta:2024/spells.md#Vera Resurrezione", "carta:2024/spells.md#Visione del Vero",
                           "GET /characters/{char_id}/spells/{spell_id}/cast-check"])
@pytest.mark.parametrize("indice", ["arcane-lock", "hallow", "simulacrum", "symbol", "true-resurrection", "true-seeing"])
@pytest.mark.xfail(strict=True, reason="CB-3871: difforme dal manuale, confermato")
async def test_componente_costosa_consumata_del_catalogo_2024_chiede_conferma(client, indice):
    cid = await _pg(client, "sorcerer", 20)
    sid = await _impara(client, cid, indice)
    r = await client.get(f"/characters/{cid}/spells/{sid}/cast-check")
    assert r.status_code == 200, r.text
    assert "material_consumed" in r.json()  # «25+ mo ... che l'incantesimo consuma»: oggi nessuna conferma


# ---------------------------------------------------------------------------
# Verdi: i numeri giusti restano protetti
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-3873", fonte="2024 · Incantesimi · Tocco Gelido · pag. 249", zona="regola:2024/incantesimi-S-Z", voce="limiti",
                    copre=["carta:2024/spells.md#Tocco Gelido", "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
@pytest.mark.parametrize("livello, dadi_attesi", [(1, 1), (4, 1), (5, 2), (10, 2), (11, 3), (16, 3), (17, 4), (20, 4)])
async def test_tocco_gelido_2024_d10_necrotico_che_cresce_ai_livelli_5_11_e_17(client, livello, dadi_attesi):
    cid = await _pg(client, "warlock", livello)
    sid = await _impara(client, cid, "chill-touch")
    corpo = await _danno(client, cid, sid, 0)
    assert (len(corpo["main_rolls"]), corpo["main_kind"], corpo["damage_type"]) == (dadi_attesi, "d10", "necrotic")


@pytest.mark.caccia(id="CB-3874", fonte="2024 · Incantesimi · Spuntone Mentale · pag. 298", zona="regola:2024/incantesimi-S-Z", voce="regola",
                    copre=["carta:2024/spells.md#Spuntone Mentale", "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
@pytest.mark.parametrize("slot, dadi_attesi", [(2, "3d8"), (3, "4d8"), (9, "10d8")])
async def test_spuntone_mentale_3d8_psichici_piu_1d8_per_slot_e_meta_al_ts(client, slot, dadi_attesi):
    cid = await _pg(client, "sorcerer", 17)
    sid = await _impara(client, cid, "mind-spike")
    corpo = await _danno(client, cid, sid, slot)
    assert (corpo["scaled_dice"], corpo["damage_type"], corpo["save_halves"]) == (dadi_attesi, "psychic", True)


@pytest.mark.caccia(id="CB-3875", fonte="2024 · Incantesimi · Spiriti Guardiani · pag. 319", zona="regola:2024/incantesimi-S-Z", voce="regola",
                    copre=["carta:2024/spells.md#Spiriti Guardiani", "POST /characters/{char_id}/spells/{spell_id}/use",
                           "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
async def test_spiriti_guardiani_dal_catalogo_2024_concentrazione_e_3d8_piu_1d8_per_slot(client):
    cid = await _pg(client, "cleric", 7)
    sid = await _impara(client, cid, "spirit-guardians")
    scheda = await _lancia(client, cid, sid, 4)
    assert (scheda["concentrating_spell_id"], scheda["settings"]["concentration_rounds_left"]) == (sid, 100)  # 10 minuti
    corpo = await _danno(client, cid, sid, 4)
    assert (corpo["scaled_dice"], corpo["damage_type"], corpo["save_halves"]) == ("4d8", "radiant", True)


@pytest.mark.caccia(id="CB-3876", fonte="2024 · Incantesimi · Volare · pag. 276", zona="regola:2024/incantesimi-S-Z", voce="limiti",
                    copre=["carta:2024/spells.md#Volare"])
@pytest.mark.parametrize("slot, bersagli", [(3, 1), (4, 2), (9, 7)])
def test_volare_2024_volo_18_metri_e_un_bersaglio_in_piu_per_slot(slot, bersagli):
    effetto, variante = spell_effect("2024", "fly")
    assert effetto.max_targets("2024", slot) == bersagli
    assert [(m.target, m.value) for m in variante.modifiers({})] == [("fly_speed_value", 60)]
    assert (variante.concentration, variante.duration(slot)) == (True, 100)


@pytest.mark.caccia(id="CB-3877", fonte="2024 · Incantesimi · Velocità · pag. 284", zona="regola:2024/incantesimi-S-Z", voce="edizioni",
                    copre=["carta:2024/spells.md#Velocità"])
def test_velocita_2024_ca_piu_2_velocita_doppia_e_alla_fine_incapacitato():
    _effetto, variante = spell_effect("2024", "haste")
    assert {m.target for m in variante.modifiers({})} == {"ac", "speed_double", "advantage"}
    assert next(m.value for m in variante.modifiers({}) if m.target == "ac") == 2
    letargia = variante.on_close({"edition": "2024", "caster_id": 1})
    assert letargia["condition"] == "incapacitated" and letargia["data"]["skip_new_turns"] == 1
    assert (variante.concentration, variante.duration(3), variante.extra_action) == (True, 10, True)


@pytest.mark.caccia(id="CB-3878", fonte="2024 · Incantesimi · Sfera Cromatica · pag. 249", zona="regola:2024/incantesimi-S-Z", voce="regola",
                    copre=["carta:2024/spells.md#Sfera Cromatica", "POST /characters/{char_id}/spells/{spell_id}/use",
                           "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
@pytest.mark.parametrize("slot, dadi_attesi", [(1, "3d8"), (3, "5d8")])
async def test_sfera_cromatica_2024_3d8_del_tipo_scelto_piu_1d8_per_slot(client, slot, dadi_attesi):
    cid = await _pg(client, "sorcerer", 5)
    sid = await _impara(client, cid, "chromatic-orb")
    await _lancia(client, cid, sid, slot, choices={"damage_type": "cold"})
    corpo = await _danno(client, cid, sid, slot)
    assert (corpo["scaled_dice"], corpo["damage_type"]) == (dadi_attesi, "cold")
