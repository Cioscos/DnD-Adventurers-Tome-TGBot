"""Controlli della zona regola:2024/incantesimi-M-R (parte incantesimi-m-r)."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.rules.catalog.spells import spell_effect
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, seed_session
from tests.integration.rules.test_2014_bard_inspiration import _seat

SPELLS_2024 = Path(__file__).resolve().parents[2] / "webapp" / "src" / "data" / "srd" / "spells-2024.json"
CATALOGO = {e["index"]: e for e in json.loads(SPELLS_2024.read_text(encoding="utf-8"))["items"]}


async def _pg(client, nome="Incantatore", classe=None, livello=1, **punteggi) -> int:
    corpo = {"name": nome, "rules_edition": "2024",
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


async def _dal_catalogo(client, cid, indice, slot=None, **campi) -> int:
    """L'incantesimo con i campi che il client copia dal catalogo 2024 (``spellToForm``); ``slot``: due slot di quel livello."""
    e = CATALOGO[indice]
    corpo = {"name": e["name"]["it"], "srd_index": indice, "level": e["level"], "is_prepared": True,
             "casting_time": e["casting_time"]["it"], "duration": e["duration"]["it"], "components": ", ".join(e["components"]),
             "is_concentration": e["concentration"], "is_ritual": e["ritual"], "damage_dice": e.get("damage_dice"),
             "damage_type": e.get("damage_type"), "attack_save": e.get("attack_type"),
             "higher_levels_dice": e.get("higher_levels_dice") if e.get("damage_dice") else None, **campi}
    r = await client.post(f"/characters/{cid}/spells", json=corpo)
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


def _stati(scheda: dict, chiave: str) -> list[dict]:
    return [s for s in scheda.get("active_states") or [] if s.get("key") == chiave]


# ---------------------------------------------------------------------------
# Difformità
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-3811", fonte="2024 · Incantesimi · Protezione dal Male e dal Bene (concentrazione, fino a 10 minuti) · pag. 309-310",
                    zona="regola:2024/incantesimi-M-R", voce="regola",
                    copre=["carta:2024/spells.md#Protezione dal Male e dal Bene", "POST /characters/{char_id}/spells/{spell_id}/use"])
@pytest.mark.xfail(strict=True, reason="CB-3811: difforme dal manuale, confermato")
async def test_protezione_dal_male_e_dal_bene_dal_catalogo_avvia_la_concentrazione(client):
    cid = await _pg(client)
    sid = await _dal_catalogo(client, cid, "protection-from-evil-and-good", slot=1)
    r = await client.post(f"/characters/{cid}/spells/{sid}/use", json={"slot_level": 1})
    assert r.status_code == 200, r.text
    assert r.json()["concentrating_spell_id"] == sid


@pytest.mark.caccia(id="CB-3812", fonte="2024 · Incantesimi · componenti di Punizione Divina, Parole del Potere, Resistenza e Punizione Infuocata · pag. 265, 306, 312, 314",
                    zona="regola:2024/incantesimi-M-R", voce="regola",
                    copre=["carta:2024/spells.md#Punizione divina", "carta:2024/spells.md#Parola del Potere: Guarire",
                           "carta:2024/spells.md#Parola del Potere: Uccidere", "carta:2024/spells.md#Resistenza",
                           "carta:2024/spells.md#Punizione Infuocata"])
@pytest.mark.parametrize("indice,componenti", [
    ("divine-smite", ["V"]), ("power-word-heal", ["V"]), ("power-word-kill", ["V"]), ("resistance", ["V", "S"]), ("searing-smite", ["V"]),
])
def test_componenti_del_catalogo_2024(indice, componenti):
    # Le componenti finiscono sull'incantesimo del personaggio: la Verbale chiude il nascondiglio 2024 (casts_verbally)
    assert CATALOGO[indice]["components"] == componenti


@pytest.mark.caccia(id="CB-3813", fonte="2024 · Incantesimi · Malocchio, Marchio del Cacciatore e Maledizione (durata della concentrazione secondo lo slot) · pag. 285, 287, 245",
                    zona="regola:2024/incantesimi-M-R", voce="limiti",
                    copre=["carta:2024/spells.md#Malocchio", "carta:2024/spells.md#Marchio del cacciatore", "carta:2024/spells.md#Maledizione",
                           "POST /characters/{char_id}/spells/{spell_id}/use"])
@pytest.mark.parametrize("indice,slot,scelte,round_attesi", [
    ("hex", 2, {"ability": "wisdom"}, 2400), ("hex", 3, {"ability": "wisdom"}, 4800),
    ("hunters-mark", 3, None, 4800), ("hunters-mark", 5, None, 14400), ("bestow-curse", 4, None, 100),
])
@pytest.mark.xfail(strict=True, reason="CB-3813: difforme dal manuale, confermato")
async def test_la_concentrazione_dura_quanto_lo_slot_scelto(client, indice, slot, scelte, round_attesi):
    cid = await _pg(client)
    sid = await _dal_catalogo(client, cid, indice, slot=slot)
    r = await client.post(f"/characters/{cid}/spells/{sid}/use", json={"slot_level": slot, **({"choices": scelte} if scelte else {})})
    assert r.status_code == 200, r.text
    scheda = r.json()
    assert scheda["concentrating_spell_id"] == sid
    # il contatore che, a zero, chiude la concentrazione e con lei l'incantesimo
    assert scheda["settings"]["concentration_rounds_left"] == round_attesi


@pytest.mark.caccia(id="CB-3814", fonte="2024 · Incantesimi · Maledizione (con slot di 5° o superiore niente Concentrazione) · pag. 245",
                    zona="regola:2024/incantesimi-M-R", voce="limiti",
                    copre=["carta:2024/spells.md#Maledizione", "POST /characters/{char_id}/spells/{spell_id}/use"])
@pytest.mark.parametrize("slot", [5, 7, 9])
@pytest.mark.xfail(strict=True, reason="CB-3814: difforme dal manuale, confermato")
async def test_maledizione_con_slot_alto_non_richiede_concentrazione(client, slot):
    cid = await _pg(client)
    sid = await _dal_catalogo(client, cid, "bestow-curse", slot=slot)
    r = await client.post(f"/characters/{cid}/spells/{sid}/use", json={"slot_level": slot})
    assert r.status_code == 200, r.text
    assert r.json()["concentrating_spell_id"] is None


@pytest.mark.caccia(id="CB-3815", fonte="2024 · Incantesimi · Malocchio, Marchio del Cacciatore, Mantello del Crociato, Maledizione (danno ai colpi), Porta Dimensionale e Ragnatela (danno solo in un caso) · pag. 285, 287, 259, 245, 262, 340",
                    zona="regola:2024/incantesimi-M-R", voce="regola",
                    copre=["carta:2024/spells.md#Malocchio", "carta:2024/spells.md#Marchio del cacciatore",
                           "carta:2024/spells.md#Mantello del Crociato", "carta:2024/spells.md#Maledizione",
                           "carta:2024/spells.md#Porta Dimensionale", "carta:2024/spells.md#Ragnatela", "GET /characters/{char_id}/spells"])
@pytest.mark.parametrize("indice", ["hex", "hunters-mark", "crusaders-mantle", "bestow-curse", "dimension-door", "web"])
async def test_incantesimi_senza_danno_al_lancio_non_aprono_il_tiro_di_danno(client, indice):
    cid = await _pg(client)
    await _dal_catalogo(client, cid, indice)
    r = await client.get(f"/characters/{cid}/spells")
    assert r.status_code == 200, r.text
    voce = next(s for s in r.json() if s["srd_index"] == indice)
    # la regola del client (rollsDamageOnCast): dadi dell'incantesimo e nessun danno «al colpo» -> il lancio apre il tiro di danno
    assert not (voce["damage_dice"] and not (voce["effect"] or {}).get("hit_damage"))


@pytest.mark.caccia(id="CB-3816", fonte="2024 · Incantesimi · Preveggenza (termina se lanci di nuovo l'incantesimo) · pag. 276",
                    zona="regola:2024/incantesimi-M-R", voce="edizioni",
                    copre=["carta:2024/spells.md#Preveggenza", "POST /characters/{char_id}/spells/{spell_id}/use"])
@pytest.mark.xfail(strict=True, reason="CB-3816: difforme dal manuale, confermato")
async def test_preveggenza_2024_lanciata_di_nuovo_finisce_sul_primo_bersaglio(client, test_session_factory):
    _, eroe = await seed_session(test_session_factory)
    as_user(GM_ID)
    mago = await _pg(client)
    sid = await _dal_catalogo(client, mago, "foresight", slot=9)
    await _seat(test_session_factory, mago, GM_ID)
    r = await client.post(f"/characters/{mago}/spells/{sid}/use", json={"slot_level": 9, "targets": [eroe]})
    assert r.status_code == 200, r.text
    as_user(PLAYER_ID)
    assert _stati(await _scheda(client, eroe), "spell:foresight")
    as_user(GM_ID)
    # 2024: un solo incantesimo con slot per turno, confermato (il secondo lancio è di un altro momento)
    r = await client.post(f"/characters/{mago}/spells/{sid}/use", json={"slot_level": 9, "targets": [mago], "confirm": ["one_slot_per_turn"]})
    assert r.status_code == 200, r.text
    assert _stati(await _scheda(client, mago), "spell:foresight")
    as_user(PLAYER_ID)
    assert not _stati(await _scheda(client, eroe), "spell:foresight")


# ---------------------------------------------------------------------------
# Regole giuste da proteggere
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-3817", fonte="2024 · Incantesimi · Punizioni del Paladino 2024 (dadi extra e slot superiori) · pag. 314, 316, 320, 334, 343",
                    zona="regola:2024/incantesimi-M-R", voce="limiti",
                    copre=["carta:2024/spells.md#Punizione Infuocata", "carta:2024/spells.md#Punizione Splendente",
                           "carta:2024/spells.md#Punizione Sconvolgente", "carta:2024/spells.md#Punizione Tonante",
                           "carta:2024/spells.md#Punizione Collerica"])
@pytest.mark.parametrize("srd,slot,atteso,concentrazione", [
    ("searing-smite", 1, "1d6", False), ("searing-smite", 4, "4d6", False),
    ("shining-smite", 2, "2d6", True), ("shining-smite", 5, "5d6", True),
    ("staggering-smite", 4, "4d6", False), ("staggering-smite", 6, "6d6", False),
    ("thunderous-smite", 1, "2d6", False), ("thunderous-smite", 3, "4d6", False),
    ("wrathful-smite", 1, "1d6", True), ("wrathful-smite", 2, "2d6", True),
])
def test_dadi_delle_punizioni_2024_per_slot(srd, slot, atteso, concentrazione):
    _effetto, variante = spell_effect("2024", srd)
    assert any(o.phase == "after_hit" for o in variante.on_hit)  # si lancia subito dopo il colpo, con lo slot scelto lì
    colpo = next(o for o in variante.options if o.phase == "after_hit")
    assert variante.concentration is concentrazione
    assert colpo.extra_dice(SimpleNamespace(spell_data={"slot_level": slot}), {}) == atteso


@pytest.mark.caccia(id="CB-3818", fonte="2024 · Incantesimi · Malocchio e Marchio del Cacciatore (durata secondo lo slot) · pag. 285, 287",
                    zona="regola:2024/incantesimi-M-R", voce="edizioni",
                    copre=["carta:2024/spells.md#Malocchio", "carta:2024/spells.md#Marchio del cacciatore"])
@pytest.mark.parametrize("srd,slot,round_attesi", [
    ("hex", 1, 600), ("hex", 2, 2400), ("hex", 3, 4800), ("hex", 4, 4800), ("hex", 5, 14400), ("hex", 9, 14400),
    ("hunters-mark", 1, 600), ("hunters-mark", 2, 600), ("hunters-mark", 3, 4800), ("hunters-mark", 5, 14400),
])
def test_durata_di_malocchio_e_marchio_2024_per_slot(srd, slot, round_attesi):
    _effetto, variante = spell_effect("2024", srd)
    assert variante.concentration is True
    assert variante.duration(slot) == round_attesi


@pytest.mark.caccia(id="CB-3819", fonte="2024 · Incantesimi · Parola di Guarigione (2d4 + modificatore, +2d4 per slot) · pag. 284",
                    zona="regola:2024/incantesimi-M-R", voce="regola",
                    copre=["carta:2024/spells.md#Parola di guarigione", "POST /characters/{char_id}/spells/{spell_id}/roll_healing"])
async def test_parola_di_guarigione_2024_cura_due_d4_per_slot_piu_il_modificatore(client, dadi):
    cid = await _pg(client, "Chierica", "cleric", 5, wisdom=16)
    classe = (await _scheda(client, cid))["classes"][0]["id"]
    sid = await _dal_catalogo(client, cid, "healing-word", class_id=classe)
    await _pf(client, cid, 60, 10)
    dadi(1, 2, 3, 4)
    r = await client.post(f"/characters/{cid}/spells/{sid}/roll_healing", json={"casting_level": 2, "apply_to_self": True})
    assert r.status_code == 200, r.text
    assert r.json()["main_rolls"] == [1, 2, 3, 4] and r.json()["total"] == 10 + 3
    assert (await _scheda(client, cid))["current_hit_points"] == 23


@pytest.mark.caccia(id="CB-3820", fonte="2024 · Incantesimi · Preghiera di Guarigione (2d8, +1d8 per slot, senza modificatore) · pag. 307",
                    zona="regola:2024/incantesimi-M-R", voce="edizioni",
                    copre=["carta:2024/spells.md#Preghiera di Guarigione", "POST /characters/{char_id}/spells/{spell_id}/roll_healing"])
async def test_preghiera_di_guarigione_2024_non_somma_il_modificatore(client, dadi):
    cid = await _pg(client, "Chierica", "cleric", 5, wisdom=18)
    classe = (await _scheda(client, cid))["classes"][0]["id"]
    sid = await _dal_catalogo(client, cid, "prayer-of-healing", class_id=classe)
    await _pf(client, cid, 60, 10)
    dadi(2, 3, 4)
    r = await client.post(f"/characters/{cid}/spells/{sid}/roll_healing", json={"casting_level": 3, "apply_to_self": True})
    assert r.status_code == 200, r.text
    assert r.json()["main_rolls"] == [2, 3, 4] and r.json()["total"] == 9
    assert (await _scheda(client, cid))["current_hit_points"] == 19


@pytest.mark.caccia(id="CB-3821", fonte="2024 · Incantesimi · Protezione dal Veleno (termina Avvelenato, resistenza al veleno) · pag. 310",
                    zona="regola:2024/incantesimi-M-R", voce="regola",
                    copre=["carta:2024/spells.md#Protezione dal Veleno", "POST /characters/{char_id}/spells/{spell_id}/use"])
async def test_protezione_dal_veleno_2024_toglie_avvelenato_e_da_resistenza(client):
    cid = await _pg(client)
    r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"poisoned": True}})
    assert r.status_code == 200, r.text
    sid = await _dal_catalogo(client, cid, "protection-from-poison", slot=2)
    r = await client.post(f"/characters/{cid}/spells/{sid}/use", json={"slot_level": 2})
    assert r.status_code == 200, r.text
    scheda = r.json()
    assert not (scheda["conditions"] or {}).get("poisoned")
    assert "poison" in scheda["computed"]["resistances"]
    assert scheda["concentrating_spell_id"] is None


@pytest.mark.caccia(id="CB-3822", fonte="2024 · Incantesimi · Morte Apparente (Accecato, Incapacitato, resistenze tranne psichici) · pag. 271",
                    zona="regola:2024/incantesimi-M-R", voce="regola",
                    copre=["carta:2024/spells.md#Morte apparente", "POST /characters/{char_id}/spells/{spell_id}/use"])
async def test_morte_apparente_2024_accieca_incapacita_e_resiste_a_tutto_tranne_psichici(client):
    cid = await _pg(client)
    sid = await _dal_catalogo(client, cid, "feign-death", slot=3)
    r = await client.post(f"/characters/{cid}/spells/{sid}/use", json={"slot_level": 3})
    assert r.status_code == 200, r.text
    scheda = r.json()
    assert scheda["conditions"].get("blinded") and scheda["conditions"].get("incapacitated")
    assert "fire" in scheda["computed"]["resistances"] and "psychic" not in scheda["computed"]["resistances"]
