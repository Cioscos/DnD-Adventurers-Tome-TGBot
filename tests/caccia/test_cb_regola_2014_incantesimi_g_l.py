"""Controlli della zona regola:2014/incantesimi-G-L (parte incantesimi-g-l)."""
import json
from pathlib import Path

import pytest

from core.rules.catalog.granted_spells import GRANTED_SPELLS
from core.rules.catalog.spells import SPELL_EFFECTS
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, setup_full_encounter

_SRD_DIR = Path(__file__).resolve().parents[2] / "webapp" / "src" / "data" / "srd"
_SRD = {ed: {s["index"]: s for s in json.loads((_SRD_DIR / nome).read_text(encoding="utf-8"))["items"]}
        for ed, nome in (("2014", "spells.json"), ("2024", "spells-2024.json"))}


def _dal_catalogo(indice: str, edizione: str = "2014") -> dict:
    """La riga del catalogo SRD dell'edizione come la scrive la webapp quando il giocatore la aggiunge (spellToForm)."""
    e = _SRD[edizione][indice]
    return {"name": e["name"]["it"], "level": e["level"], "casting_time": e["casting_time"]["it"], "duration": e["duration"]["it"],
            "components": ", ".join(e["components"]), "is_concentration": e["concentration"], "is_ritual": e["ritual"],
            "damage_dice": e["damage_dice"], "damage_type": e["damage_type"], "attack_save": e["attack_type"] or None,
            "school": e["school"], "srd_index": indice,
            "higher_levels_dice": e["higher_levels_dice"] if e["damage_dice"] and indice != "sleep" else None,
            "is_prepared": True}


async def _pg(client, classe, livello, nome="Incantatore", sottoclasse=None, edizione="2014") -> int:
    r = await client.post("/characters", json={"name": nome, "rules_edition": edizione, "initial_class": {
        "class_name": classe, "level": livello, "subclass": sottoclasse}})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _impara(client, cid, indice, edizione="2014") -> int:
    r = await client.post(f"/characters/{cid}/spells", json=_dal_catalogo(indice, edizione))
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _scheda(client, cid) -> dict:
    r = await client.get(f"/characters/{cid}")
    assert r.status_code == 200, r.text
    return r.json()


async def _stati(client, cid, chiave) -> list[dict]:
    return [s for s in (await _scheda(client, cid))["active_states"] or [] if s["key"] == chiave]


async def _due_concentrazioni(client, slot):
    """Un bardo concentrato su Immagine Silenziosa lancia Immagine Maggiore con uno slot ``slot``: (risposta, silenziosa, maggiore)."""
    cid = await _pg(client, "bard", 17, "Bardo")
    silenziosa = await _impara(client, cid, "silent-image")
    maggiore = await _impara(client, cid, "major-image")
    assert (await client.post(f"/characters/{cid}/spells/{silenziosa}/use", json={"slot_level": 1})).status_code == 200
    r = await client.post(f"/characters/{cid}/spells/{maggiore}/use", json={"slot_level": slot, "confirm": ["one_slot_per_turn"]})
    assert r.status_code == 200, r.text
    return r.json(), silenziosa, maggiore


# ---------------------------------------------------------------------------
# Difformità
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-3311", fonte="2014 · Incantesimi · Lama Infuocata · pag. 247", zona="regola:2014/incantesimi-G-L", voce="limiti",
                    copre=["carta:2014/spells.md#Lama Infuocata", "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
@pytest.mark.parametrize("slot, dadi_attesi", [(3, "3d6"), (4, "4d6"), (6, "5d6"), (9, "6d6")])
async def test_lama_infuocata_sale_di_1d6_ogni_due_livelli_di_slot(client, slot, dadi_attesi):
    cid = await _pg(client, "druid", 17, "Druido")
    sid = await _impara(client, cid, "flame-blade")
    r = await client.post(f"/characters/{cid}/spells/{sid}/roll_damage", json={"casting_level": slot})
    assert r.status_code == 200, r.text
    assert r.json()["scaled_dice"] == dadi_attesi  # 3d6 al 2°, +1d6 al 4°, al 6° e all'8°


@pytest.mark.caccia(id="CB-3312", fonte="2014 · Incantesimi · Guardiani Spirituali · pag. 240; Chierico · Incantesimi del Dominio della Guerra · pag. 63",
                    zona="regola:2014/incantesimi-G-L", voce="regola",
                    copre=["carta:2014/spells.md#Guardiani Spirituali",
                           "carta:2014/classes/cleric.md#Incantesimi del Dominio della Guerra / War Domain Spells (Guerra 1, pag. 60)",
                           "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
async def test_guardiani_spirituali_del_dominio_della_guerra_tirano_i_loro_dadi(client):
    cid = await _pg(client, "cleric", 5, "Chierico", "Dominio della Guerra")
    spell = next(s for s in (await client.get(f"/characters/{cid}/spells")).json() if s["srd_index"] == "spirit-guardians")
    r = await client.post(f"/characters/{cid}/spells/{spell['id']}/use", json={"slot_level": 3, "choices": {"damage_type": "radiant"}})
    assert r.status_code == 200, r.text  # il tipo si sceglie al lancio (D-031)
    r = await client.post(f"/characters/{cid}/spells/{spell['id']}/roll_damage", json={"casting_level": 4})
    assert r.status_code == 200, r.text  # oggi 400: la riga del dominio non ha dadi di danno
    assert r.json()["scaled_dice"] == "4d8"  # 3d8 al 3°, +1d8 per livello di slot


@pytest.mark.caccia(id="CB-3313", fonte="2014 · Incantesimi · Immagine Maggiore · pag. 242", zona="regola:2014/incantesimi-G-L", voce="interazione",
                    copre=["carta:2014/spells.md#Immagine Maggiore", "POST /characters/{char_id}/spells/{spell_id}/use"])
@pytest.mark.parametrize("slot", [6, 9])
async def test_immagine_maggiore_dal_sesto_livello_non_toglie_la_concentrazione_in_corso(client, slot):
    esito, silenziosa, _ = await _due_concentrazioni(client, slot)
    # dal 6° dura finché non è dissolta, senza concentrazione: quella su Immagine Silenziosa resta
    assert esito["concentrating_spell_id"] == silenziosa


@pytest.mark.caccia(id="CB-3314", fonte="2014 · Incantesimi · Interdizione alle Lame · pag. 245", zona="regola:2014/incantesimi-G-L", voce="limiti",
                    copre=["carta:2014/spells.md#Interdizione alle Lame", "POST /characters/{char_id}/spells/{spell_id}/use",
                           "POST /sessions/{session_id}/encounter/next-turn"])
async def test_interdizione_alle_lame_vale_ancora_nel_turno_successivo_di_chi_la_lancia(client, test_session_factory):
    sessione, incontro = await setup_full_encounter(client, test_session_factory)
    eroe = next(c for c in incontro["combatants"] if c["kind"] == "pc")["character_id"]
    as_user(PLAYER_ID)
    sid = await _impara(client, eroe, "blade-ward")
    as_user(GM_ID)
    assert (await client.post(f"/sessions/{sessione}/encounter/start", json={})).status_code == 200
    as_user(PLAYER_ID)  # turno dell'eroe: primo in iniziativa
    r = await client.post(f"/characters/{eroe}/spells/{sid}/use", json={})
    assert r.status_code == 200, r.text
    assert len(await _stati(client, eroe, "spell:blade_ward")) == 1
    as_user(GM_ID)
    for _ in range(3):  # i due goblin, poi di nuovo l'eroe
        assert (await client.post(f"/sessions/{sessione}/encounter/next-turn")).status_code == 200
    as_user(PLAYER_ID)
    # all'inizio del turno successivo la resistenza vale ancora: finisce alla fine di quel turno
    assert len(await _stati(client, eroe, "spell:blade_ward")) == 1


@pytest.mark.caccia(id="CB-3315", fonte="2014 · Incantesimi · Guardiani Spirituali · pag. 240; Guardiano della Fede · pag. 240",
                    zona="regola:2014/incantesimi-G-L", voce="regola",
                    copre=["carta:2014/spells.md#Guardiani Spirituali", "carta:2014/spells.md#Guardiano della Fede",
                           "carta:2014/classes/cleric.md#Incantesimi del Dominio della Guerra / War Domain Spells (Guerra 1, pag. 60)",
                           "carta:2014/classes/cleric.md#Incantesimi del Dominio della Vita / Life Domain Spells (Vita 1, pag. 63)",
                           "carta:2014/classes/cleric.md#Incantesimi del Dominio della Luce / Light Domain Spells (Luce 1, pag. 61)"])
@pytest.mark.parametrize("indice", ["spirit-guardians", "guardian-of-faith"])
def test_gli_incantesimi_di_dominio_con_tiro_salvezza_lo_dichiarano(indice):
    # la riga creata dal dominio dice che il danno si evita con un TS (Saggezza / Destrezza): la scheda mostra CD e metà danni
    assert GRANTED_SPELLS[indice].attack_save == "SAVE"


# ---------------------------------------------------------------------------
# Regole giuste da proteggere
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-3319", fonte="2014 · Incantesimi · Guida · pag. 240", zona="regola:2014/incantesimi-G-L", voce="regola",
                    copre=["carta:2014/spells.md#Guida", "POST /characters/{char_id}/spells/{spell_id}/use",
                           "POST /characters/{char_id}/last-roll/options"])
async def test_guida_aggiunge_un_d4_una_volta_poi_finisce_con_la_concentrazione(client):
    cid = await _pg(client, "cleric", 1, "Chierico")
    sid = await _impara(client, cid, "guidance")
    assert (await client.post(f"/characters/{cid}/spells/{sid}/use", json={})).status_code == 200
    assert (await _scheda(client, cid))["concentrating_spell_id"] == sid
    prima = await client.post(f"/characters/{cid}/skills/athletics/roll", json={"die": 10})
    assert prima.status_code == 200, prima.text
    r = await client.post(f"/characters/{cid}/last-roll/options", json={"options": ["spell:guidance:add"]})
    assert r.status_code == 200, r.text
    assert 1 <= r.json()["total"] - prima.json()["total"] <= 4
    assert await _stati(client, cid, "spell:guidance") == []
    assert (await _scheda(client, cid))["concentrating_spell_id"] is None


@pytest.mark.caccia(id="CB-3320", fonte="2014 · Incantesimi · Guarigione · pag. 240", zona="regola:2014/incantesimi-G-L", voce="limiti",
                    copre=["carta:2014/spells.md#Guarigione", "POST /characters/{char_id}/spells/{spell_id}/roll_healing"])
@pytest.mark.parametrize("slot, pf", [(6, 70), (7, 80), (9, 100)])
async def test_guarigione_ridà_70_pf_e_10_per_livello_di_slot_oltre_il_sesto(client, slot, pf):
    cid = await _pg(client, "cleric", 17, "Chierico")
    sid = await _impara(client, cid, "heal")
    r = await client.post(f"/characters/{cid}/spells/{sid}/roll_healing", json={"casting_level": slot})
    assert r.status_code == 200, r.text
    assert r.json()["total"] == pf and r.json()["rolls"] == []  # PF fissi, nessun dado né modificatore


@pytest.mark.caccia(id="CB-3321", fonte="2014 · Incantesimi · Globo Cromatico · pag. 239", zona="regola:2014/incantesimi-G-L", voce="normale",
                    copre=["carta:2014/spells.md#Globo Cromatico", "POST /characters/{char_id}/spells/{spell_id}/use",
                           "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
async def test_globo_cromatico_tira_3d8_piu_1d8_per_slot_del_tipo_scelto(client):
    assert SPELL_EFFECTS["chromatic_orb"].variants["2014"].choices[0].options("2014") == [
        "acid", "cold", "lightning", "fire", "thunder", "poison"]
    cid = await _pg(client, "sorcerer", 5, "Stregone")
    sid = await _impara(client, cid, "chromatic-orb")
    r = await client.post(f"/characters/{cid}/spells/{sid}/use", json={"slot_level": 3, "choices": {"damage_type": "poison"}})
    assert r.status_code == 200, r.text
    r = await client.post(f"/characters/{cid}/spells/{sid}/roll_damage", json={"casting_level": 3})
    assert r.status_code == 200, r.text
    assert r.json()["scaled_dice"] == "5d8" and r.json()["damage_type"] == "poison"


@pytest.mark.caccia(id="CB-3322", fonte="2014 · Incantesimi · Invisibilità · pag. 246; Invisibilità Superiore · pag. 246",
                    zona="regola:2014/incantesimi-G-L", voce="limiti",
                    copre=["carta:2014/spells.md#Invisibilità", "carta:2014/spells.md#Invisibilità Superiore"])
def test_invisibilita_una_creatura_in_piu_per_slot_oltre_il_secondo_e_la_superiore_una_sola():
    invisibilita, superiore = SPELL_EFFECTS["invisibility"], SPELL_EFFECTS["greater_invisibility"]
    assert [invisibilita.max_targets("2014", s) for s in (2, 3, 9)] == [1, 2, 8]
    assert [superiore.max_targets("2014", s) for s in (4, 9)] == [1, 1]
    assert invisibilita.variants["2014"].ends_on == ("attack", "cast", "manual")  # finisce se attacca o lancia
    assert superiore.variants["2014"].ends_on == ("manual",)  # la superiore no


@pytest.mark.caccia(id="CB-3323", fonte="2014 · Incantesimi · Interdizione alle Lame · pag. 245", zona="regola:2014/incantesimi-G-L", voce="regola",
                    copre=["carta:2014/spells.md#Interdizione alle Lame", "POST /characters/{char_id}/spells/{spell_id}/use",
                           "PATCH /characters/{char_id}/hp"])
async def test_interdizione_alle_lame_dimezza_il_danno_contundente_perforante_tagliente_delle_armi(client):
    cid = await _pg(client, "sorcerer", 1, "Stregone")
    for op, v in (("set_max", 40), ("set_current", 40)):
        assert (await client.patch(f"/characters/{cid}/hp", json={"op": op, "value": v})).status_code == 200
    sid = await _impara(client, cid, "blade-ward")
    assert (await client.post(f"/characters/{cid}/spells/{sid}/use", json={})).status_code == 200
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 11, "damage_type": "slashing",
                                                          "options": ["spell:blade_ward:weapon"]})
    assert r.status_code == 200, r.text
    assert r.json()["current_hit_points"] == 35  # resistenza: 11 -> 5
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 10, "damage_type": "fire"})
    assert r.status_code == 200, r.text
    assert r.json()["current_hit_points"] == 25  # il fuoco non è un danno da arma: intero


@pytest.mark.caccia(id="CB-3324", fonte="2014 · Incantesimi · Immagine Maggiore · pag. 242", zona="regola:2014/incantesimi-G-L", voce="limiti",
                    copre=["carta:2014/spells.md#Immagine Maggiore", "POST /characters/{char_id}/spells/{spell_id}/use"])
async def test_immagine_maggiore_al_quinto_livello_richiede_ancora_concentrazione(client):
    esito, _, maggiore = await _due_concentrazioni(client, 5)
    assert esito["concentrating_spell_id"] == maggiore


@pytest.mark.caccia(id="CB-3325", fonte="2024 · Incantesimi · Lama infuocata · pag. 275", zona="regola:2014/incantesimi-G-L", voce="edizioni",
                    copre=["carta:2024/spells.md#Lama infuocata", "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
@pytest.mark.parametrize("slot, dadi_attesi", [(3, "4d6"), (4, "5d6"), (9, "10d6")])
async def test_lama_infuocata_2024_sale_di_1d6_per_ogni_livello_di_slot(client, slot, dadi_attesi):
    cid = await _pg(client, "druid", 17, "Druido", edizione="2024")
    sid = await _impara(client, cid, "flame-blade", "2024")
    r = await client.post(f"/characters/{cid}/spells/{sid}/roll_damage", json={"casting_level": slot})
    assert r.status_code == 200, r.text
    assert r.json()["scaled_dice"] == dadi_attesi
