"""Controlli della zona regola:2024/incantesimi-D-F (parte incantesimi-d-f)."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.rules.catalog.spells import SPELL_EFFECTS
from tests.integration._encounter_helpers import GM_ID, as_user, seed_session
from tests.integration.rules.test_2014_bard_inspiration import _seat
from tests.integration.rules.test_2024_druid_circles import _circle
from tests.integration.rules.test_2024_warlock_patrons import _make

_SRD_DIR = Path(__file__).resolve().parents[2] / "webapp" / "src" / "data" / "srd"
_SRD = {ed: {s["index"]: s for s in json.loads((_SRD_DIR / nome).read_text(encoding="utf-8"))["items"]}
        for ed, nome in (("2014", "spells.json"), ("2024", "spells-2024.json"))}


def _dal_catalogo(indice: str, edizione: str = "2024") -> dict:
    """La scheda che la webapp manda aggiungendo l'incantesimo dal catalogo dell'edizione (spellToForm, in italiano)."""
    e = _SRD[edizione][indice]
    materiale = (e.get("material") or {}).get("it", "").rstrip(".")
    corpo = {
        "name": e["name"]["it"], "level": e["level"], "casting_time": e["casting_time"]["it"], "duration": e["duration"]["it"],
        "is_concentration": e["concentration"], "is_ritual": e["ritual"], "school": e["school"], "srd_index": indice,
        "components": ", ".join(e["components"]) + (f" ({materiale})" if materiale and "M" in e["components"] else ""),
        "attack_save": e.get("attack_type"), "damage_dice": e.get("damage_dice"), "damage_type": e.get("damage_type"),
        "higher_levels_dice": e.get("higher_levels_dice") if e.get("damage_dice") and indice != "sleep" else None,
        "is_prepared": True,
    }
    return {k: v for k, v in corpo.items() if v not in (None, "")}


async def _pg(client, classe: str, livello: int, edizione: str = "2024", **punteggi) -> int:
    r = await client.post("/characters", json={"name": "Incantatore", "rules_edition": edizione,
                                               "initial_class": {"class_name": classe, "level": livello}})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    for caratteristica, valore in punteggi.items():
        r = await client.patch(f"/characters/{cid}/ability_scores/{caratteristica}", json={"value": valore})
        assert r.status_code == 200, r.text
    return cid


async def _impara(client, cid: int, indice: str, edizione: str = "2024") -> int:
    r = await client.post(f"/characters/{cid}/spells", json=_dal_catalogo(indice, edizione))
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _scheda(client, cid: int) -> dict:
    r = await client.get(f"/characters/{cid}")
    assert r.status_code == 200, r.text
    return r.json()


async def _concesso(client, cid: int, indice: str) -> dict:
    """La riga dell'incantesimo che un privilegio ha messo sulla scheda (sempre preparato)."""
    return next(s for s in (await _scheda(client, cid))["spells"] if s["srd_index"] == indice)


async def _danno(client, cid: int, sid: int, **corpo) -> dict:
    r = await client.post(f"/characters/{cid}/spells/{sid}/roll_damage", json=corpo)
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# Difformità
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-3711", fonte="2024 · Incantesimi · Dardo Incantato · pag. 295", zona="regola:2024/incantesimi-D-F", voce="regola",
                    copre=["carta:2024/spells.md#Dardo Incantato", "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
@pytest.mark.parametrize("slot, dardi", [(1, 3), (3, 5)])
@pytest.mark.xfail(strict=True, reason="CB-3711: difforme dal manuale, confermato")
async def test_dardo_incantato_2024_dal_catalogo_lancia_tre_dardi_piu_uno_per_slot(client, slot, dardi):
    cid = await _pg(client, "sorcerer", 5)
    sid = await _impara(client, cid, "magic-missile")
    r = await _danno(client, cid, sid, casting_level=slot)
    # ogni dardo vale 1d4+1: tre dardi al 1° livello, uno in più per ogni livello di slot oltre
    assert (r["scaled_dice"], r["total"] - sum(r["main_rolls"])) == (f"{dardi}d4", dardi)


@pytest.mark.caccia(id="CB-3712", fonte="2024 · Incantesimi · Esplosione Stregonesca · pag. 318", zona="regola:2024/incantesimi-D-F", voce="regola",
                    copre=["carta:2024/spells.md#Esplosione Stregonesca", "POST /characters/{char_id}/spells/{spell_id}/attack",
                           "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
@pytest.mark.xfail(strict=True, reason="CB-3712: difforme dal manuale, confermato")
async def test_esplosione_stregonesca_dal_catalogo_tira_1d8_del_tipo_scelto(client):
    cid = await _pg(client, "sorcerer", 1)
    sid = await _impara(client, cid, "sorcerous-burst")
    r = await client.post(f"/characters/{cid}/spells/{sid}/attack", json={"choices": {"damage_type": "fire"}, "die": 15})
    assert r.status_code == 200, r.text
    r = await client.post(f"/characters/{cid}/spells/{sid}/roll_damage", json={"damage_type": "fire"})
    assert (r.status_code, r.json().get("scaled_dice")) == (200, "1d8")  # 1d8 del tipo scelto al 1° livello


@pytest.mark.caccia(id="CB-3713", fonte="2024 · Incantesimi · Esplosione Stregonesca · pag. 318", zona="regola:2024/incantesimi-D-F", voce="regola",
                    copre=["carta:2024/spells.md#Esplosione Stregonesca"])
@pytest.mark.xfail(strict=True, reason="CB-3713: difforme dal manuale, confermato")
def test_esplosione_stregonesca_del_catalogo_ha_componenti_verbale_e_somatica():
    assert _SRD["2024"]["sorcerous-burst"]["components"] == ["V", "S"]


@pytest.mark.caccia(id="CB-3714", fonte="2024 · Incantesimi · Evoca Celestiale · pag. 254", zona="regola:2024/incantesimi-D-F", voce="limiti",
                    copre=["carta:2024/spells.md#Evoca Celestiale", "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
@pytest.mark.parametrize("slot, dadi_attesi", [(7, "6d12"), pytest.param(8, "7d12", marks=pytest.mark.xfail(strict=True, reason="CB-3714: difforme dal manuale, confermato")), pytest.param(9, "8d12", marks=pytest.mark.xfail(strict=True, reason="CB-3714: difforme dal manuale, confermato"))])
async def test_evoca_celestiale_2024_luce_ardente_sale_di_1d12_per_slot_oltre_il_settimo(client, slot, dadi_attesi):
    cid = await _pg(client, "cleric", 17)
    sid = await _impara(client, cid, "conjure-celestial")
    assert (await _danno(client, cid, sid, casting_level=slot))["scaled_dice"] == dadi_attesi


@pytest.mark.caccia(id="CB-3715", fonte="2024 · Incantesimi · Evoca Fatato · pag. 255", zona="regola:2024/incantesimi-D-F", voce="limiti",
                    copre=["carta:2024/spells.md#Evoca Fatato", "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
@pytest.mark.parametrize("slot, dadi_attesi", [(6, "3d12"), pytest.param(7, "5d12", marks=pytest.mark.xfail(strict=True, reason="CB-3715: difforme dal manuale, confermato")), pytest.param(9, "9d12", marks=pytest.mark.xfail(strict=True, reason="CB-3715: difforme dal manuale, confermato"))])
async def test_evoca_fatato_2024_sale_di_2d12_per_slot_oltre_il_sesto(client, slot, dadi_attesi):
    cid = await _pg(client, "druid", 17)
    sid = await _impara(client, cid, "conjure-fey")
    assert (await _danno(client, cid, sid, casting_level=slot))["scaled_dice"] == dadi_attesi


@pytest.mark.caccia(id="CB-3716", fonte="2024 · Incantesimi · Forma gassosa · pag. 277", zona="regola:2024/incantesimi-D-F", voce="limiti",
                    copre=["carta:2024/spells.md#Forma gassosa", "POST /characters/{char_id}/spells/{spell_id}/use"])
@pytest.mark.xfail(strict=True, reason="CB-3716: difforme dal manuale, confermato")
async def test_forma_gassosa_2024_un_bersaglio_in_piu_per_slot_oltre_il_terzo(client, test_session_factory):
    _, eroe = await seed_session(test_session_factory)
    as_user(GM_ID)
    cid = await _pg(client, "sorcerer", 7)
    sid = await _impara(client, cid, "gaseous-form")
    await _seat(test_session_factory, cid, GM_ID)
    r = await client.post(f"/characters/{cid}/spells/{sid}/use", json={"slot_level": 4, "targets": [cid, eroe]})
    assert r.status_code == 200, r.text  # slot 4°: due creature consenzienti


@pytest.mark.caccia(id="CB-3717", fonte="2024 · Incantesimi · Dominare bestie, Dominare persone, Dominare mostri · pag. 265-266",
                    zona="regola:2024/incantesimi-D-F", voce="limiti",
                    copre=["carta:2024/spells.md#Dominare bestie", "carta:2024/spells.md#Dominare persone", "carta:2024/spells.md#Dominare mostri",
                           "POST /characters/{char_id}/spells/{spell_id}/use"])
@pytest.mark.parametrize("classe, livello, indice, slot, round_attesi", [
    ("druid", 7, "dominate-beast", 4, 10), pytest.param("druid", 9, "dominate-beast", 5, 100, marks=pytest.mark.xfail(strict=True, reason="CB-3717: difforme dal manuale, confermato")),
    pytest.param("druid", 11, "dominate-beast", 6, 600, marks=pytest.mark.xfail(strict=True, reason="CB-3717: difforme dal manuale, confermato")),
    pytest.param("druid", 13, "dominate-beast", 7, 4800, marks=pytest.mark.xfail(strict=True, reason="CB-3717: difforme dal manuale, confermato")), ("bard", 9, "dominate-person", 5, 10),
    pytest.param("bard", 11, "dominate-person", 6, 100, marks=pytest.mark.xfail(strict=True, reason="CB-3717: difforme dal manuale, confermato")),
    pytest.param("bard", 13, "dominate-person", 7, 600, marks=pytest.mark.xfail(strict=True, reason="CB-3717: difforme dal manuale, confermato")),
    pytest.param("bard", 15, "dominate-person", 8, 4800, marks=pytest.mark.xfail(strict=True, reason="CB-3717: difforme dal manuale, confermato")),
    pytest.param("sorcerer", 17, "dominate-monster", 9, 4800, marks=pytest.mark.xfail(strict=True, reason="CB-3717: difforme dal manuale, confermato")),
])
async def test_dominare_2024_la_concentrazione_dura_di_piu_con_uno_slot_superiore(client, classe, livello, indice, slot, round_attesi):
    cid = await _pg(client, classe, livello)
    sid = await _impara(client, cid, indice)
    r = await client.post(f"/characters/{cid}/spells/{sid}/use", json={"slot_level": slot})
    assert r.status_code == 200, r.text
    assert r.json()["settings"]["concentration_rounds_left"] == round_attesi  # 1 minuto = 10 round, 10 minuti, 1 ora, 8 ore


@pytest.mark.caccia(id="CB-3718", fonte="2024 · Incantesimi · Evoca Elementale · pag. 254; Druido · Incantesimi del Circolo del Mare · pag. 87",
                    zona="regola:2024/incantesimi-D-F", voce="interazione",
                    copre=["carta:2024/spells.md#Evoca Elementale",
                           "carta:2024/classes/druid.md#Incantesimi del Circolo del Mare / Circle of the Sea Spells (Circolo del Mare 3, pag. 87)",
                           "POST /characters/{char_id}/spells/{spell_id}/use"])
async def test_evoca_elementale_del_circolo_del_mare_2024_concentrazione_fino_a_10_minuti(client):
    cid = await _circle(client, "sea", 9, wisdom=16)
    riga = await _concesso(client, cid, "conjure-elemental")
    r = await client.post(f"/characters/{cid}/spells/{riga['id']}/use", json={"slot_level": 5, "choices": {"damage_type": "fire"}})
    assert r.status_code == 200, r.text
    assert r.json()["settings"]["concentration_rounds_left"] == 100  # 10 minuti (il 2014 dura 1 ora)


@pytest.mark.caccia(id="CB-3719", fonte="2024 · Incantesimi · Forza Fantasmatica · pag. 304; Warlock · Incantesimi del Grande Antico · pag. 163",
                    zona="regola:2024/incantesimi-D-F", voce="interazione",
                    copre=["carta:2024/spells.md#Forza Fantasmatica",
                           "carta:2024/classes/warlock.md#Incantesimi del Grande Antico / Great Old One Spells (Patrono Grande Antico 3, pag. 163)",
                           "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
@pytest.mark.xfail(strict=True, reason="CB-3719: difforme dal manuale, confermato")
async def test_forza_fantasmatica_del_grande_antico_2024_fa_2d8_anche_con_slot_superiore(client):
    cid = await _make(client, "great_old_one", 5)
    riga = await _concesso(client, cid, "phantasmal-force")
    assert (await _danno(client, cid, riga["id"], casting_level=3))["scaled_dice"] == "2d8"  # nessuna scalata sulla carta


@pytest.mark.caccia(id="CB-3720", fonte="2024 · Incantesimi · Fame di Hadar · pag. 286", zona="regola:2024/incantesimi-D-F", voce="regola",
                    copre=["carta:2024/spells.md#Fame di Hadar", "POST /characters/{char_id}/spells/{spell_id}/use",
                           "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
@pytest.mark.xfail(strict=True, reason="CB-3720: difforme dal manuale, confermato")
async def test_fame_di_hadar_2024_il_dado_in_piu_scelto_acido_non_va_al_freddo(client):
    cid = await _pg(client, "warlock", 7)
    sid = await _impara(client, cid, "hunger-of-hadar")
    r = await client.post(f"/characters/{cid}/spells/{sid}/use", json={"slot_level": 4, "choices": {"upcast_type": "acid"}})
    assert r.status_code == 200, r.text
    r = await _danno(client, cid, sid, casting_level=4)
    assert (r["damage_type"], r["scaled_dice"]) == ("cold", "2d6")  # il +1d6 dello slot 4° va all'acido scelto


# ---------------------------------------------------------------------------
# Regole giuste da proteggere
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-3721", fonte="2024 · Incantesimi · Dardo di fuoco · pag. 274", zona="regola:2024/incantesimi-D-F", voce="limiti",
                    copre=["carta:2024/spells.md#Dardo di fuoco", "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
@pytest.mark.parametrize("livello, dadi_attesi", [(4, "1d10"), (5, "2d10"), (10, "2d10"), (11, "3d10"), (17, "4d10"), (20, "4d10")])
async def test_dardo_di_fuoco_2024_sale_ai_livelli_5_11_17(client, livello, dadi_attesi):
    cid = await _pg(client, "sorcerer", livello)
    sid = await _impara(client, cid, "fire-bolt")
    assert (await _danno(client, cid, sid))["scaled_dice"] == dadi_attesi


@pytest.mark.caccia(id="CB-3722", fonte="2024 · Incantesimi · Falsa vita · pag. 271", zona="regola:2024/incantesimi-D-F", voce="regola",
                    copre=["carta:2024/spells.md#Falsa vita", "POST /characters/{char_id}/spells/{spell_id}/use"])
@pytest.mark.parametrize("slot, attesi", [(1, 9), (3, 19)])
async def test_falsa_vita_2024_da_2d4_piu_4_e_5_per_slot_oltre_il_primo(client, dadi, slot, attesi):
    cid = await _pg(client, "sorcerer", 5)
    sid = await _impara(client, cid, "false-life")
    dadi(3, 2)
    r = await client.post(f"/characters/{cid}/spells/{sid}/use", json={"slot_level": slot})
    assert r.status_code == 200, r.text
    assert r.json()["temp_hp"] == attesi  # 3 + 2 + 4, più 5 per ogni livello oltre il 1°


@pytest.mark.caccia(id="CB-3723", fonte="2024 · Incantesimi · Favore divino · pag. 265; 2014 · Incantesimi · Favore Divino · pag. 235",
                    zona="regola:2024/incantesimi-D-F", voce="edizioni",
                    copre=["carta:2024/spells.md#Favore divino", "carta:2014/spells.md#Favore Divino", "POST /characters/{char_id}/spells/{spell_id}/use"])
@pytest.mark.parametrize("edizione, concentra", [("2014", True), ("2024", False)])
async def test_favore_divino_concentrazione_solo_nel_2014(client, edizione, concentra):
    cid = await _pg(client, "paladin", 5, edizione=edizione)
    sid = await _impara(client, cid, "divine-favor", edizione)
    r = await client.post(f"/characters/{cid}/spells/{sid}/use", json={"slot_level": 1})
    assert r.status_code == 200, r.text
    assert (r.json()["concentrating_spell_id"] == sid) is concentra


@pytest.mark.caccia(id="CB-3724", fonte="2024 · Incantesimi · Evoca Elementali Minori · pag. 255", zona="regola:2024/incantesimi-D-F", voce="limiti",
                    copre=["carta:2024/spells.md#Evoca Elementali Minori"])
@pytest.mark.parametrize("slot, dadi_attesi", [(4, "2d8"), (5, "4d8"), (9, "12d8")])
def test_evoca_elementali_minori_2024_2d8_piu_2d8_per_slot_oltre_il_quarto(slot, dadi_attesi):
    opzione = next(o for o in SPELL_EFFECTS["conjure_minor_elementals"].variants["2024"].options if o.extra_damage_type == "fire")
    assert opzione.extra_dice(SimpleNamespace(spell_data={"slot_level": slot}), {}) == dadi_attesi


@pytest.mark.caccia(id="CB-3725", fonte="2024 · Incantesimi · Disintegrazione · pag. 263; Dito della morte · pag. 273",
                    zona="regola:2024/incantesimi-D-F", voce="regola",
                    copre=["carta:2024/spells.md#Disintegrazione", "carta:2024/spells.md#Dito della morte",
                           "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
@pytest.mark.parametrize("indice, slot, dimezza, dadi_attesi", [("disintegrate", 6, False, "10d6"), ("disintegrate", 8, False, "16d6"),
                                                                ("finger-of-death", 7, True, "7d8")])
async def test_disintegrazione_non_dimezza_dito_della_morte_si(client, indice, slot, dimezza, dadi_attesi):
    cid = await _pg(client, "sorcerer", 17)
    sid = await _impara(client, cid, indice)
    r = await _danno(client, cid, sid, casting_level=slot)
    assert (r["save_halves"], r["scaled_dice"]) == (dimezza, dadi_attesi)  # più il fisso (+40 / +30) nel totale


@pytest.mark.caccia(id="CB-3726", fonte="2024 · Incantesimi · Eroismo · pag. 285", zona="regola:2024/incantesimi-D-F", voce="limiti",
                    copre=["carta:2024/spells.md#Eroismo", "GET /characters/{char_id}"])
async def test_eroismo_2024_un_bersaglio_in_piu_per_slot_oltre_il_primo(client):
    cid = await _pg(client, "bard", 9)
    await _impara(client, cid, "heroism")
    riga = await _concesso(client, cid, "heroism")
    assert {int(k): v for k, v in riga["effect"]["max_targets_by_slot"].items() if int(k) <= 4} == {1: 1, 2: 2, 3: 3, 4: 4}
