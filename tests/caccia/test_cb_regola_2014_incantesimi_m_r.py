"""Controlli della zona regola:2014/incantesimi-M-R (parte incantesimi-m-r)."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.rules.catalog.spells import spell_effect
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, seed_session
from tests.integration.rules.test_2014_bard_inspiration import _seat

SPELLS_JSON = Path(__file__).resolve().parents[2] / "webapp" / "src" / "data" / "srd" / "spells.json"


async def _pg(client, nome="Incantatore", classe=None, livello=1, edizione="2014", **punteggi) -> int:
    corpo = {"name": nome, "rules_edition": edizione,
             **({"initial_class": {"class_name": classe, "level": livello}} if classe else {})}
    r = await client.post("/characters", json=corpo)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    for nome_car, valore in punteggi.items():
        r = await client.patch(f"/characters/{cid}/ability_scores/{nome_car}", json={"value": valore})
        assert r.status_code == 200, r.text
    return cid


async def _scheda(client, cid) -> dict:
    r = await client.get(f"/characters/{cid}")
    assert r.status_code == 200, r.text
    return r.json()


async def _incantesimo(client, cid, nome, srd, livello, slot=None, **campi) -> int:
    """L'incantesimo con i campi che il catalogo del frontend gli dà; ``slot``: due slot di quel livello."""
    r = await client.post(f"/characters/{cid}/spells", json={"name": nome, "srd_index": srd, "level": livello, "is_prepared": True, **campi})
    assert r.status_code == 201, r.text
    sid = r.json()["id"]
    if slot:
        r = await client.post(f"/characters/{cid}/spell_slots", json={"level": slot, "total": 2})
        assert r.status_code == 201, r.text
    return sid


async def _pf(client, cid, massimo, attuali) -> None:
    for op, valore in (("set_max", massimo), ("set_current", attuali)):
        r = await client.patch(f"/characters/{cid}/hp", json={"op": op, "value": valore})
        assert r.status_code == 200, r.text


async def _serata(client, factory, nome, srd, livello, **campi) -> tuple[int, int, int]:
    """Una serata con un eroe (giocatore) e un incantatore 2014 (GM) seduto: ``(eroe, incantatore, incantesimo)``."""
    _, eroe = await seed_session(factory)
    as_user(GM_ID)
    mago = await _pg(client, "Incantatore")
    sid = await _incantesimo(client, mago, nome, srd, livello, slot=livello, **campi)
    await _seat(factory, mago, GM_ID)
    return eroe, mago, sid


def _stati(scheda: dict, chiave: str) -> list[dict]:
    return [s for s in scheda.get("active_states") or [] if s.get("key") == chiave]


# ---------------------------------------------------------------------------
# Difformità
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-3361", fonte="2014 · Incantesimi · Raffica di Spine (slot superiori, massimo 6d10) · pag. 266", zona="regola:2014/incantesimi-M-R",
                    voce="limiti", copre=["carta:2014/spells.md#Raffica di Spine", "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
@pytest.mark.parametrize("livello_slot", [7, 9])
@pytest.mark.xfail(strict=True, reason="CB-3361: difforme dal manuale, confermato")
async def test_raffica_di_spine_non_supera_sei_d10_con_slot_alti(client, livello_slot):
    cid = await _pg(client, "Ranger")
    sid = await _incantesimo(client, cid, "Raffica di Spine", "hail-of-thorns", 1, damage_dice="1d10", damage_type="piercing",
                             attack_save="SAVE", higher_levels_dice="1d10", is_concentration=True)
    r = await client.post(f"/characters/{cid}/spells/{sid}/roll_damage", json={"casting_level": livello_slot})
    assert r.status_code == 200, r.text
    assert len(r.json()["main_rolls"]) == 6


@pytest.mark.caccia(id="CB-3362", fonte="2014 · Incantesimi · Previsione (termina se lanciato di nuovo) · pag. 264", zona="regola:2014/incantesimi-M-R",
                    voce="regola", copre=["carta:2014/spells.md#Previsione", "POST /characters/{char_id}/spells/{spell_id}/use"])
async def test_previsione_lanciata_di_nuovo_finisce_sul_primo_bersaglio(client, test_session_factory):
    eroe, mago, sid = await _serata(client, test_session_factory, "Previsione", "foresight", 9)
    r = await client.post(f"/characters/{mago}/spells/{sid}/use", json={"slot_level": 9, "targets": [eroe]})
    assert r.status_code == 200, r.text
    as_user(PLAYER_ID)
    assert _stati(await _scheda(client, eroe), "spell:foresight")
    as_user(GM_ID)
    r = await client.post(f"/characters/{mago}/spells/{sid}/use", json={"slot_level": 9, "targets": [mago]})
    assert r.status_code == 200, r.text
    assert _stati(await _scheda(client, mago), "spell:foresight")
    as_user(PLAYER_ID)
    assert not _stati(await _scheda(client, eroe), "spell:foresight")


@pytest.mark.caccia(id="CB-3363", fonte="2014 · Incantesimi · Rigenerazione (4d8 + 15 PF una volta, poi 1 PF a turno) · pag. 270", zona="regola:2014/incantesimi-M-R",
                    voce="interazione", copre=["carta:2014/spells.md#Rigenerazione", "POST /characters/{char_id}/spells/{spell_id}/use",
                                               "POST /characters/{char_id}/spells/{spell_id}/roll_healing"])
@pytest.mark.xfail(strict=True, reason="CB-3363: difforme dal manuale, confermato")
async def test_rigenerazione_lanciata_dal_client_cura_una_volta_sola(client, test_session_factory, dadi):
    eroe, mago, sid = await _serata(client, test_session_factory, "Rigenerazione", "regenerate", 7)
    as_user(PLAYER_ID)
    await _pf(client, eroe, 200, 100)
    as_user(GM_ID)
    dadi(*[5] * 8)
    # Il foglio di cura del client: prima il lancio con il bersaglio scelto, poi il tiro di cura sullo stesso bersaglio
    r = await client.post(f"/characters/{mago}/spells/{sid}/use", json={"slot_level": 7, "targets": [eroe]})
    assert r.status_code == 200, r.text
    await client.post(f"/characters/{mago}/spells/{sid}/roll_healing", json={"casting_level": 7, "target_character_ids": [eroe]})
    as_user(PLAYER_ID)
    assert (await _scheda(client, eroe))["current_hit_points"] == 100 + 4 * 5 + 15


@pytest.mark.caccia(id="CB-3364", fonte="2014 · Incantesimi · Rinascita e Rianimare Morti (solo una creatura morta) · pag. 270, 271", zona="regola:2014/incantesimi-M-R",
                    voce="regola", copre=["carta:2014/spells.md#Rinascita", "carta:2014/spells.md#Rianimare Morti",
                                          "POST /characters/{char_id}/spells/{spell_id}/roll_healing"])
@pytest.mark.parametrize("nome,srd,livello", [("Rinascita", "revivify", 3), ("Rianimare Morti", "raise-dead", 5)])
@pytest.mark.xfail(strict=True, reason="CB-3364: difforme dal manuale, confermato")
async def test_incantesimi_di_ritorno_in_vita_non_curano_una_creatura_viva(client, nome, srd, livello):
    cid = await _pg(client, "Chierico", "cleric", 9, wisdom=16)
    sid = await _incantesimo(client, cid, nome, srd, livello)
    await _pf(client, cid, 60, 5)
    await client.post(f"/characters/{cid}/spells/{sid}/roll_healing", json={"casting_level": livello, "apply_to_self": True})
    assert (await _scheda(client, cid))["current_hit_points"] == 5


@pytest.mark.caccia(id="CB-3365", fonte="2014 · Incantesimi · Manto del Crociato (1d4 radiosi agli attacchi con arma, nessun danno al lancio) · pag. 250",
                    zona="regola:2014/incantesimi-M-R", voce="regola",
                    copre=["carta:2014/spells.md#Manto del Crociato", "GET /characters/{char_id}/spells"])
async def test_manto_del_crociato_non_tira_danni_al_lancio(client):
    cid = await _pg(client, "Paladino", "paladin", 9)
    catalogo = json.loads(SPELLS_JSON.read_text(encoding="utf-8"))["items"]
    voce = next(e for e in catalogo if e["index"] == "crusaders-mantle")  # i campi che il client copia dal catalogo
    await _incantesimo(client, cid, "Manto del Crociato", "crusaders-mantle", voce["level"], damage_dice=voce["damage_dice"] or None,
                       damage_type=voce["damage_type"], is_concentration=voce["concentration"])
    r = await client.get(f"/characters/{cid}/spells")
    assert r.status_code == 200, r.text
    manto = next(s for s in r.json() if s["srd_index"] == "crusaders-mantle")
    # la regola del client (rollsDamageOnCast): dadi dell'incantesimo e nessun danno «al colpo» -> il lancio apre il tiro di danno
    assert not (manto["damage_dice"] and not (manto["effect"] or {}).get("hit_damage"))


# ---------------------------------------------------------------------------
# Regole giuste da proteggere
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-3366", fonte="2014 · Incantesimi · Punizioni del Paladino (dadi extra e slot superiori) · pag. 265-266", zona="regola:2014/incantesimi-M-R",
                    voce="limiti", copre=["carta:2014/spells.md#Punizione Accecante", "carta:2014/spells.md#Punizione Marchiante",
                                          "carta:2014/spells.md#Punizione Incandescente", "carta:2014/spells.md#Punizione Collerica",
                                          "carta:2014/spells.md#Punizione Tonante", "carta:2014/spells.md#Punizione Demoralizzante",
                                          "carta:2014/spells.md#Punizione Esiliante"])
@pytest.mark.parametrize("srd,slot,atteso", [
    ("blinding-smite", 3, "3d8"), ("blinding-smite", 5, "3d8"),
    ("branding-smite", 2, "2d6"), ("branding-smite", 4, "4d6"),
    ("searing-smite", 1, "1d6"), ("searing-smite", 3, "3d6"),
    ("wrathful-smite", 3, "1d6"), ("thunderous-smite", 3, "2d6"),
    ("staggering-smite", 5, "4d6"), ("banishing-smite", 5, "5d10"),
])
def test_dadi_delle_punizioni_2014_per_slot(srd, slot, atteso):
    _effetto, variante = spell_effect("2014", srd)
    colpo = next(o for o in variante.options if o.phase == "after_hit")
    assert variante.concentration is True and variante.rounds == 10
    assert colpo.extra_dice(SimpleNamespace(spell_data={"slot_level": slot}), {}) == atteso


@pytest.mark.caccia(id="CB-3367", fonte="2014 · Incantesimi · Marchio del Cacciatore (durata secondo lo slot) · pag. 251", zona="regola:2014/incantesimi-M-R",
                    voce="limiti", copre=["carta:2014/spells.md#Marchio del Cacciatore"])
@pytest.mark.parametrize("slot,round_attesi", [(1, 600), (2, 600), (3, 4800), (4, 4800), (5, 14400), (9, 14400)])
def test_durata_del_marchio_del_cacciatore_per_slot(slot, round_attesi):
    _effetto, variante = spell_effect("2014", "hunters-mark")
    assert variante.concentration is True
    assert variante.duration(slot) == round_attesi


@pytest.mark.caccia(id="CB-3368", fonte="2014 · Incantesimi · Parola Guaritrice (1d4 + modificatore, +1d4 per slot) · pag. 259", zona="regola:2014/incantesimi-M-R",
                    voce="regola", copre=["carta:2014/spells.md#Parola Guaritrice", "POST /characters/{char_id}/spells/{spell_id}/roll_healing"])
async def test_parola_guaritrice_cura_un_d4_per_slot_piu_il_modificatore(client, dadi):
    cid = await _pg(client, "Chierico", "cleric", 5, wisdom=16)
    classe = (await _scheda(client, cid))["classes"][0]["id"]
    sid = await _incantesimo(client, cid, "Parola Guaritrice", "healing-word", 1, class_id=classe)
    await _pf(client, cid, 40, 10)
    dadi(1, 2, 3)
    r = await client.post(f"/characters/{cid}/spells/{sid}/roll_healing", json={"casting_level": 3, "apply_to_self": True})
    assert r.status_code == 200, r.text
    assert r.json()["main_rolls"] == [1, 2, 3] and r.json()["total"] == 6 + 3
    assert (await _scheda(client, cid))["current_hit_points"] == 19


@pytest.mark.caccia(id="CB-3369", fonte="2014 · Incantesimi · Pelle Coriacea (CA minima 16, concentrazione) · pag. 260; 2024 · Incantesimi · Pelle d'Albero (CA minima 17) · pag. 245",
                    zona="regola:2014/incantesimi-M-R", voce="edizioni",
                    copre=["carta:2014/spells.md#Pelle Coriacea", "carta:2024/spells.md#Pelle d'Albero", "POST /characters/{char_id}/spells/{spell_id}/use"])
@pytest.mark.parametrize("edizione,ca,concentrazione", [("2014", 16, True), ("2024", 17, False)])
async def test_pelle_coriacea_ca_minima_per_edizione(client, edizione, ca, concentrazione):
    cid = await _pg(client, "Druido", edizione=edizione)
    sid = await _incantesimo(client, cid, "Pelle Coriacea", "barkskin", 2, slot=2, is_concentration=concentrazione)
    assert (await _scheda(client, cid))["ac"] == 10
    r = await client.post(f"/characters/{cid}/spells/{sid}/use", json={"slot_level": 2})
    assert r.status_code == 200, r.text
    scheda = await _scheda(client, cid)
    assert scheda["ac"] == ca
    assert (scheda["concentrating_spell_id"] == sid) is concentrazione


@pytest.mark.caccia(id="CB-3370", fonte="2014 · Incantesimi · Palla di Fuoco (8d6, +1d6 per slot, metà se superato) · pag. 257", zona="regola:2014/incantesimi-M-R",
                    voce="regola", copre=["carta:2014/spells.md#Palla di Fuoco", "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
async def test_palla_di_fuoco_al_quinto_tira_dieci_d6_e_dimezza_al_ts(client):
    cid = await _pg(client, "Mago")
    sid = await _incantesimo(client, cid, "Palla di Fuoco", "fireball", 3, damage_dice="8d6", damage_type="fire", attack_save="SAVE",
                             higher_levels_dice="1d6")
    r = await client.post(f"/characters/{cid}/spells/{sid}/roll_damage", json={"casting_level": 5})
    assert r.status_code == 200, r.text
    esito = r.json()
    assert len(esito["main_rolls"]) == 10 and esito["damage_type"] == "fire"
    assert esito["save_halves"] is True and esito["half_damage"] == esito["total"] // 2


@pytest.mark.caccia(id="CB-3371", fonte="2014 · Incantesimi · Raggio di Gelo (1d8, 2d8/3d8/4d8 ai livelli 5/11/17) · pag. 266", zona="regola:2014/incantesimi-M-R",
                    voce="limiti", copre=["carta:2014/spells.md#Raggio di Gelo", "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
@pytest.mark.parametrize("livello,dadi_attesi", [(1, 1), (4, 1), (5, 2), (10, 2), (11, 3), (16, 3), (17, 4), (20, 4)])
async def test_raggio_di_gelo_cresce_con_il_livello_del_personaggio(client, livello, dadi_attesi):
    cid = await _pg(client, "Mago", "wizard", livello)
    sid = await _incantesimo(client, cid, "Raggio di Gelo", "ray-of-frost", 0, damage_dice="1d8", damage_type="cold", attack_save="ATK")
    r = await client.post(f"/characters/{cid}/spells/{sid}/roll_damage", json={})
    assert r.status_code == 200, r.text
    assert len(r.json()["main_rolls"]) == dadi_attesi
