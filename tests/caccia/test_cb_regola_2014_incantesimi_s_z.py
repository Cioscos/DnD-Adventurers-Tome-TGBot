"""Controlli della zona regola:2014/incantesimi-S-Z (parte incantesimi-s-z)."""
import json
from pathlib import Path

import pytest

from core.rules.catalog.granted_spells import granted_spell
from core.rules.catalog.spells import spell_effect

_SRD = {s["index"]: s for s in json.loads(
    (Path(__file__).resolve().parents[2] / "webapp" / "src" / "data" / "srd" / "spells.json").read_text(encoding="utf-8"))["items"]}


def _dal_catalogo(indice: str, **altro) -> dict:
    """La riga del catalogo SRD 2014 con i campi che il modulo della webapp manda quando il giocatore la aggiunge (spellToForm)."""
    e = _SRD[indice]
    corpo = {"name": e["name"]["it"], "level": e["level"], "casting_time": e["casting_time"]["it"], "duration": e["duration"]["it"],
             "components": ", ".join(e["components"]), "is_concentration": e["concentration"], "is_ritual": e["ritual"],
             "damage_dice": e["damage_dice"], "damage_type": e["damage_type"], "attack_save": e["attack_type"],
             "school": e["school"], "srd_index": indice,
             "higher_levels_dice": e["higher_levels_dice"] if e["damage_dice"] else None,
             "extra_damage_dice": e.get("extra_damage_dice"), "extra_damage_type": e.get("extra_damage_type"),
             "is_prepared": e["level"] > 0, **altro}
    return {k: v for k, v in corpo.items() if v not in (None, "")}


async def _pg(client, classe=None, livello=1) -> int:
    corpo = {"name": "Incantatore", "rules_edition": "2014"}
    if classe:
        corpo["initial_class"] = {"class_name": classe, "level": livello}
    r = await client.post("/characters", json=corpo)
    assert r.status_code == 201, r.text
    return r.json()["id"]


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


async def _slot(client, cid, livello, totale=2) -> None:
    r = await client.post(f"/characters/{cid}/spell_slots", json={"level": livello, "total": totale})
    assert r.status_code == 201, r.text


async def _lancia(client, cid, sid, slot, **altro) -> dict:
    r = await client.post(f"/characters/{cid}/spells/{sid}/use", json={"slot_level": slot, **altro})
    assert r.status_code == 200, r.text
    return r.json()


async def _danno(client, cid, sid, livello, **altro) -> dict:
    r = await client.post(f"/characters/{cid}/spells/{sid}/roll_damage", json={"casting_level": livello, **altro})
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# Difformità
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-3411", fonte="2014 · Incantesimi · Sortilegio · pag. 279", zona="regola:2014/incantesimi-S-Z", voce="limiti",
                    copre=["carta:2014/spells.md#Sortilegio", "POST /characters/{char_id}/spells/{spell_id}/use"])
@pytest.mark.parametrize("livello_warlock, slot, round_attesi", [(5, 3, 4800), (9, 5, 14400)])
@pytest.mark.xfail(strict=True, reason="CB-3411: difforme dal manuale, confermato")
async def test_sortilegio_con_slot_alto_mantiene_la_concentrazione_per_la_durata_dello_slot(client, livello_warlock, slot, round_attesi):
    cid = await _pg(client, "warlock", livello_warlock)  # gli slot del patto sono del 3° (livello 5) e del 5° (livello 9)
    sid = await _impara(client, cid, "hex")
    scheda = await _lancia(client, cid, sid, slot, choices={"ability": "wisdom"})
    assert scheda["concentrating_spell_id"] == sid
    assert scheda["settings"]["concentration_rounds_left"] == round_attesi  # 8 ore con il 3°-4°, 24 ore dal 5°


@pytest.mark.caccia(id="CB-3412", fonte="2014 · Incantesimi · Scagliare Maledizione · pag. 273", zona="regola:2014/incantesimi-S-Z", voce="limiti",
                    copre=["carta:2014/spells.md#Scagliare Maledizione", "POST /characters/{char_id}/spells/{spell_id}/use"])
@pytest.mark.xfail(strict=True, reason="CB-3412: difforme dal manuale, confermato")
async def test_scagliare_maledizione_dallo_slot_quinto_non_richiede_concentrazione(client):
    cid = await _pg(client, "cleric", 9)
    sid = await _impara(client, cid, "bestow-curse")
    scheda = await _lancia(client, cid, sid, 5)
    assert scheda["concentrating_spell_id"] is None


@pytest.mark.caccia(id="CB-3413", fonte="2014 · Incantesimi · Scagliare Maledizione · pag. 273", zona="regola:2014/incantesimi-S-Z", voce="limiti",
                    copre=["carta:2014/spells.md#Scagliare Maledizione", "POST /characters/{char_id}/spells/{spell_id}/use"])
@pytest.mark.xfail(strict=True, reason="CB-3413: difforme dal manuale, confermato")
async def test_scagliare_maledizione_con_slot_quarto_dura_dieci_minuti_di_concentrazione(client):
    cid = await _pg(client, "cleric", 9)
    sid = await _impara(client, cid, "bestow-curse")
    scheda = await _lancia(client, cid, sid, 4)
    assert scheda["concentrating_spell_id"] == sid
    assert scheda["settings"]["concentration_rounds_left"] == 100


@pytest.mark.caccia(id="CB-3414", fonte="2014 · Incantesimi · Tempesta di Vendetta · pag. 284", zona="regola:2014/incantesimi-S-Z", voce="regola",
                    copre=["carta:2014/spells.md#Tempesta di Vendetta", "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
async def test_tempesta_di_vendetta_il_ts_superato_non_dimezza_il_tuono_iniziale(client):
    cid = await _pg(client, "druid", 17)
    sid = await _impara(client, cid, "storm-of-vengeance")
    corpo = await _danno(client, cid, sid, 9)
    assert (len(corpo["main_rolls"]), corpo["damage_type"]) == (2, "thunder")
    assert corpo["save_halves"] is False  # chi supera il TS non subisce i 2d6 né resta assordato


@pytest.mark.caccia(id="CB-3415", fonte="2014 · Incantesimi · Sonno · pag. 279", zona="regola:2014/incantesimi-S-Z", voce="limiti",
                    copre=["carta:2014/spells.md#Sonno", "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
@pytest.mark.parametrize("slot, dadi_attesi", [(1, 5), (2, 7), (3, 9)])
async def test_sonno_somma_due_d8_alla_riserva_per_ogni_slot_oltre_il_primo(client, slot, dadi_attesi):
    cid = await _pg(client, "bard", 5)
    sid = await _impara(client, cid, "sleep")  # 5d8, +2d8 per slot dalla riga del catalogo
    corpo = await _danno(client, cid, sid, slot)
    assert len(corpo["main_rolls"]) == dadi_attesi and corpo["main_kind"] == "d8"


@pytest.mark.caccia(id="CB-3416", fonte="2014 · Incantesimi · Tempesta di Ghiaccio · pag. 284; Sciame di Meteore · pag. 273",
                    zona="regola:2014/incantesimi-S-Z", voce="regola",
                    copre=["carta:2014/spells.md#Tempesta di Ghiaccio", "carta:2014/spells.md#Sciame di Meteore",
                           "POST /characters/{char_id}/spells", "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
@pytest.mark.parametrize("classe, livello, indice, slot, prima, seconda", [
    ("druid", 7, "ice-storm", 4, (2, "bludgeoning"), (4, "d6", "cold")),
    ("sorcerer", 17, "meteor-swarm", 9, (20, "fire"), (20, "d6", "bludgeoning")),
])
@pytest.mark.xfail(strict=True, reason="CB-3416: difforme dal manuale, confermato")
async def test_incantesimo_preso_dal_catalogo_infligge_anche_la_seconda_parte_del_danno(client, classe, livello, indice, slot, prima, seconda):
    cid = await _pg(client, classe, livello)
    sid = await _impara(client, cid, indice)
    corpo = await _danno(client, cid, sid, slot)
    assert (len(corpo["main_rolls"]), corpo["damage_type"]) == prima
    assert (len(corpo["extra_rolls"]), corpo["extra_kind"], corpo["extra_damage_type"]) == seconda


@pytest.mark.caccia(id="CB-3417", fonte="2014 · Incantesimi · Scudo di Fuoco · pag. 275", zona="regola:2014/incantesimi-S-Z", voce="regola",
                    copre=["carta:2014/spells.md#Scudo di Fuoco", "POST /characters/{char_id}/spells/{spell_id}/use",
                           "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
@pytest.mark.xfail(strict=True, reason="CB-3417: difforme dal manuale, confermato")
async def test_scudo_di_fuoco_gelido_infligge_danni_da_freddo(client):
    cid = await _pg(client)
    await _slot(client, cid, 4)
    sid = await _impara(client, cid, "fire-shield")
    scheda = await _lancia(client, cid, sid, 4, choices={"shield": "cold"})
    assert any(s["key"] == "spell:fire_shield" for s in scheda["active_states"])
    corpo = await _danno(client, cid, sid, 4)
    assert len(corpo["main_rolls"]) == 2 and corpo["damage_type"] == "cold"


@pytest.mark.caccia(id="CB-3418", fonte="2014 · Incantesimi · Sogno · pag. 279; Tempesta di Nevischio · pag. 284; Druido · Incantesimi del Circolo · pag. 68; Chierico · Dominio della Tempesta · pag. 62",
                    zona="regola:2014/incantesimi-S-Z", voce="regola",
                    copre=["carta:2014/spells.md#Sogno", "carta:2014/spells.md#Tempesta di Nevischio"])
@pytest.mark.parametrize("indice", ["dream", "sleet-storm"])
@pytest.mark.xfail(strict=True, reason="CB-3418: difforme dal manuale, confermato")
def test_incantesimi_concessi_2014_con_un_ts_nella_carta_sono_segnati_come_ts(indice):
    assert granted_spell(indice, "2014").attack_save == "SAVE"


@pytest.mark.caccia(id="CB-3419", fonte="2014 · Incantesimi · Sogno · pag. 279; Druido · Incantesimi del Circolo (Prateria) · pag. 68",
                    zona="regola:2014/incantesimi-S-Z", voce="regola", copre=["carta:2014/spells.md#Sogno"])
@pytest.mark.xfail(strict=True, reason="CB-3419: difforme dal manuale, confermato")
def test_sogno_concesso_dal_circolo_ha_i_3d6_psichici_dell_incubo():
    sogno = granted_spell("dream", "2014")
    assert (sogno.damage_dice, sogno.damage_type) == ("3d6", "psychic")


# ---------------------------------------------------------------------------
# Verdi: i numeri giusti restano protetti
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-3420", fonte="2014 · Incantesimi · Vita Falsata · pag. 289", zona="regola:2014/incantesimi-S-Z", voce="regola",
                    copre=["carta:2014/spells.md#Vita Falsata", "POST /characters/{char_id}/spells/{spell_id}/use"])
@pytest.mark.parametrize("slot, dado, temporanei", [(1, 1, 5), (1, 4, 8), (3, 2, 16)])
async def test_vita_falsata_da_1d4_piu_4_e_5_per_slot_oltre_il_primo(client, dadi, slot, dado, temporanei):
    cid = await _pg(client, "sorcerer", 5)
    sid = await _impara(client, cid, "false-life")
    dadi(dado)
    assert (await _lancia(client, cid, sid, slot))["temp_hp"] == temporanei


@pytest.mark.caccia(id="CB-3421", fonte="2014 · Incantesimi · Tocco Gelido · pag. 286", zona="regola:2014/incantesimi-S-Z", voce="limiti",
                    copre=["carta:2014/spells.md#Tocco Gelido", "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
@pytest.mark.parametrize("livello, dadi_attesi", [(1, 1), (4, 1), (5, 2), (10, 2), (11, 3), (16, 3), (17, 4), (20, 4)])
async def test_tocco_gelido_cresce_ai_livelli_5_11_e_17(client, livello, dadi_attesi):
    cid = await _pg(client, "warlock", livello)
    sid = await _impara(client, cid, "chill-touch")
    corpo = await _danno(client, cid, sid, 0)
    assert (len(corpo["main_rolls"]), corpo["main_kind"], corpo["damage_type"]) == (dadi_attesi, "d8", "necrotic")


@pytest.mark.caccia(id="CB-3422", fonte="2014 · Incantesimi · Scudo · pag. 275; Scudo della Fede · pag. 275", zona="regola:2014/incantesimi-S-Z",
                    voce="interazione",
                    copre=["carta:2014/spells.md#Scudo", "carta:2014/spells.md#Scudo della Fede",
                           "POST /characters/{char_id}/spells/{spell_id}/use"])
async def test_scudo_e_scudo_della_fede_si_sommano_e_usano_reazione_e_azione_bonus(client):
    cid = await _pg(client)
    await _slot(client, cid, 1, 3)
    fede, scudo = await _impara(client, cid, "shield-of-faith"), await _impara(client, cid, "shield")
    base = (await _scheda(client, cid))["ac"]
    assert (await _lancia(client, cid, fede, 1))["ac"] == base + 2
    scheda = await _lancia(client, cid, scudo, 1)
    assert scheda["ac"] == base + 7
    turno = (await client.get(f"/characters/{cid}/turn-state")).json()["turn"]
    assert turno["bonus_used"] and turno["reaction_used"] and not turno["action_used"]
    assert scheda["concentrating_spell_id"] == fede  # Scudo non chiede concentrazione: quella di Scudo della Fede resta


@pytest.mark.caccia(id="CB-3423", fonte="2014 · Incantesimi · Scurovisione · pag. 275; 2024 · Incantesimi · Scurovisione · pag. 260",
                    zona="regola:2014/incantesimi-S-Z", voce="edizioni",
                    copre=["carta:2014/spells.md#Scurovisione", "carta:2024/spells.md#Scurovisione"])
@pytest.mark.parametrize("edizione, piedi", [("2014", 60), ("2024", 150)])
def test_scurovisione_da_18_metri_nel_2014_e_45_nel_2024(edizione, piedi):
    _effetto, variante = spell_effect(edizione, "darkvision")
    assert [(m.target, m.value) for m in variante.modifiers({})] == [("sense:darkvision", piedi)]
    assert variante.duration(2) == 4800 and not variante.concentration  # 8 ore senza concentrazione in entrambe


@pytest.mark.caccia(id="CB-3424", fonte="2014 · Incantesimi · Sussurri Dissonanti · pag. 282", zona="regola:2014/incantesimi-S-Z", voce="regola",
                    copre=["carta:2014/spells.md#Sussurri Dissonanti", "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
@pytest.mark.parametrize("slot, dadi_attesi", [(1, 3), (3, 5)])
async def test_sussurri_dissonanti_3d6_psichici_piu_1d6_per_slot_e_meta_al_ts(client, slot, dadi_attesi):
    cid = await _pg(client, "bard", 5)
    sid = await _impara(client, cid, "dissonant-whispers")
    corpo = await _danno(client, cid, sid, slot)
    assert (len(corpo["main_rolls"]), corpo["main_kind"], corpo["damage_type"]) == (dadi_attesi, "d6", "psychic")
    assert corpo["save_halves"] is True
