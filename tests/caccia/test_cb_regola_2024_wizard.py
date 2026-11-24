"""Controlli della zona regola:2024/wizard."""
import random
from types import SimpleNamespace

import pytest

from core.rules.spellcasting import known_limits, prepared_limit, slots_for

NOMI = {"abjurer": "Abiuratore", "diviner": "Divinatore", "evoker": "Invocatore", "illusionist": "Illusionista"}
SCUOLE_2014 = {"abjuration": "Scuola di Abiurazione"}
ESPERTA = "wizard.expert_divination"
TERZO_OCCHIO = "wizard.third_eye"
SATURAZIONE = "wizard.overchannel"
PORTENTO = "wizard.portent"


async def _mago(client, livello, sottoclasse=None, edizione="2024", **punteggi) -> int:
    nome = NOMI.get(sottoclasse) or SCUOLE_2014.get(sottoclasse)
    r = await client.post("/characters", json={"name": "Mago", "initial_class": {"class_name": "wizard", "level": livello, "subclass": nome}})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    if edizione == "2024":
        assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    for car, valore in {"intelligence": 16, **punteggi}.items():
        assert (await client.patch(f"/characters/{cid}/ability_scores/{car}", json={"value": valore})).status_code == 200
    return cid


async def _scheda(client, cid) -> dict:
    return (await client.get(f"/characters/{cid}")).json()


def _scelta(scheda: dict, gruppo: str) -> dict | None:
    return next((c for c in scheda["pending_choices"] if c.get("group") == gruppo), None)


async def _incantesimo(client, cid, nome, livello, **altro) -> int:
    r = await client.post(f"/characters/{cid}/spells", json={"name": nome, "level": livello, "casting_time": "1 azione", **altro})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _nel_libro(client, cid, nome, livello, **altro) -> int:
    sid = await _incantesimo(client, cid, nome, livello, **altro)
    r = await client.post(f"/characters/{cid}/spells/{sid}/copy", json={"mode": "copy"})
    assert r.status_code == 200, r.text
    return sid


async def _oro(client, cid, quanto) -> None:
    assert (await client.patch(f"/characters/{cid}/currency", json={"gold": quanto})).status_code == 200


async def _per_indice(client, cid) -> dict[str, dict]:
    return {s["srd_index"]: s for s in (await client.get(f"/characters/{cid}/spells")).json() if s["srd_index"]}


async def _usa(client, cid, chiave, **corpo):
    return await client.post(f"/characters/{cid}/features/{chiave}/use", json=corpo)


async def _abilita(client, cid, chiave) -> dict | None:
    return next((a for a in (await _scheda(client, cid))["abilities"] if a["feature_key"] == chiave), None)


async def _opzioni(client, cid, tiro, **query) -> list[str]:
    r = await client.get(f"/characters/{cid}/roll-options", params={"roll": tiro, **query})
    assert r.status_code == 200, r.text
    return [o["key"] for o in r.json()]


async def _usati(client, cid) -> dict[int, int]:
    return {s["level"]: s["used"] for s in (await _scheda(client, cid))["spell_slots"]}


async def _spendi(client, cid, livello, usati) -> None:
    slot = next(s for s in (await _scheda(client, cid))["spell_slots"] if s["level"] == livello)
    assert (await client.patch(f"/characters/{cid}/spell_slots/{slot['id']}", json={"used": usati})).status_code == 200


async def _pf(client, cid, valore) -> None:
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": valore})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": valore})


def _stati(scheda: dict) -> dict[str, dict]:
    return {s["key"]: s for s in scheda["active_states"] or []}


async def _riposo(client, cid, tipo, **altro):
    return await client.post(f"/characters/{cid}/rest", json={"rest_type": tipo, "confirm_early": True, **altro})


# ---------------------------------------------------------------------------
# Rossi
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-2711", fonte="2024 · Mago · Divinatore · Divinazione Esperta · pag. 173", zona="regola:2024/wizard", voce="regola",
                    copre=["carta:2024/classes/wizard.md#Divinazione Esperta / Expert Divination (Divinatore 6, pag. 173)",
                           "carta:2024/classes/wizard.md#Vedere Invisibilità / See Invisibility (Divinatore 10, pag. 173)",
                           "POST /characters/{char_id}/spells/{spell_id}/use"])
@pytest.mark.parametrize("lancio", ["terzo_occhio", "rituale"])
@pytest.mark.xfail(strict=True, reason="CB-2711: difforme dal manuale, confermato")
async def test_divinazione_esperta_non_rende_slot_a_un_lancio_senza_slot(client, lancio):
    cid = await _mago(client, 10, "diviner")
    await _spendi(client, cid, 1, 2)
    if lancio == "terzo_occhio":  # Vedere Invisibilità (divinazione di 2°) lanciata gratis dal Terzo Occhio
        assert (await _usa(client, cid, TERZO_OCCHIO, params={"option": "see_invisibility"})).status_code == 200
        await client.post(f"/characters/{cid}/turn/new")
        sid = (await _per_indice(client, cid))["see-invisibility"]["id"]
        corpo = {"free_cast": True}
    else:  # una divinazione rituale di 2° livello, lanciata come rituale
        sid = await _incantesimo(client, cid, "Rito divinatorio", 2, school="divination", is_ritual=True)
        corpo = {"as_ritual": True, "confirm": ["ritual_unprepared"]}
    await client.post(f"/characters/{cid}/spells/{sid}/use", json={**corpo, "options": [ESPERTA], "option_inputs": {ESPERTA: {"slot_level": 1}}})
    assert (await _usati(client, cid))[1] == 2  # nessuno slot speso: nessuno slot recuperato


@pytest.mark.caccia(id="CB-2712", fonte="2024 · Mago · Incantesimi e Libro degli Incantesimi pag. 165; Divinatore · Divinazione Sapiente pag. 173", zona="regola:2024/wizard",
                    voce="limiti", copre=["carta:2024/classes/wizard.md#Incantesimi / Spellcasting (Mago 1, pag. 165)",
                                          "carta:2024/classes/wizard.md#Libro degli Incantesimi / Spellbook (Mago 1, pag. 165)",
                                          "carta:2024/classes/wizard.md#Divinazione Sapiente / Divination Savant (Divinatore 3, pag. 173)",
                                          "POST /characters/{char_id}/spells"])
@pytest.mark.parametrize("gruppo,livello,sottoclasse,scuola,livello_inc,ammessi", [
    ("spellbook", 3, None, None, 2, 2),  # 6 di 1° al 1° livello, 2 al 2° (max 1°), 2 al 3° (max 2°)
    ("divination_savant", 5, "diviner", "divination", 3, 1),  # due di livello massimo 2, poi uno di 3° al 5°
])
@pytest.mark.xfail(strict=True, reason="CB-2712: difforme dal manuale, confermato")
async def test_le_scelte_di_incantesimi_dei_livelli_passati_hanno_il_tetto_di_quel_livello(client, gruppo, livello, sottoclasse, scuola,
                                                                                            livello_inc, ammessi):
    cid = await _mago(client, livello, sottoclasse)
    esiti = []
    for n in range(ammessi + 1):
        scelta = _scelta(await _scheda(client, cid), gruppo)
        r = await client.post(f"/characters/{cid}/spells", json={
            "name": f"Prova {n}", "level": livello_inc, "casting_time": "1 azione", "pick_id": scelta["id"],
            **({"school": scuola} if scuola else {})})
        esiti.append(r.status_code)
    assert esiti[:-1] == [201] * ammessi  # i posti di quel livello ci sono
    assert esiti[-1] == 422  # oltre i posti di quel livello di incantesimo


@pytest.mark.caccia(id="CB-2713", fonte="2024 · Mago · Invocatore · Saturazione Magica: incantesimo da mago · pag. 174", zona="regola:2024/wizard",
                    voce="interazione", copre=["carta:2024/classes/wizard.md#Saturazione Magica / Overchannel (Invocatore 14, pag. 174)",
                                               "carta:2024/classes/wizard.md#Multiclasse: Mago / Multiclassing: Wizard (Mago, pag. 44)",
                                               "GET /characters/{char_id}/roll-options"])
@pytest.mark.xfail(strict=True, reason="CB-2713: difforme dal manuale, confermato")
async def test_saturazione_magica_2024_non_vale_per_un_incantesimo_da_chierico(client):
    cid = await _mago(client, 14, "evoker")
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "cleric", "level": 1, "hit_die": 8})
    assert r.status_code == 201, r.text
    chierico = next(c["id"] for c in (await _scheda(client, cid))["classes"] if c["class_name"].lower() == "cleric")
    dardo = await _incantesimo(client, cid, "Dardo tracciante", 1, class_id=chierico, school="evocation", attack_save="ATK",
                               damage_dice="4d6", damage_type="radiant")
    assert SATURAZIONE not in await _opzioni(client, cid, "spell_damage", spell_id=dardo)


@pytest.mark.caccia(id="CB-2714", fonte="2024 · Mago · Invocatore · Saturazione Magica: lancio con uno slot di livello 1-5 · pag. 174",
                    zona="regola:2024/wizard", voce="interazione",
                    copre=["carta:2024/classes/wizard.md#Saturazione Magica / Overchannel (Invocatore 14, pag. 174)",
                           "carta:2024/classes/wizard.md#Maestria negli Incantesimi / Spell Mastery (Mago 18, pag. 167)",
                           "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
@pytest.mark.xfail(strict=True, reason="CB-2714: difforme dal manuale, confermato")
async def test_saturazione_magica_2024_non_vale_per_un_lancio_senza_slot(client):
    cid = await _mago(client, 18, "evoker")
    await _oro(client, cid, 500)
    dardo = await _nel_libro(client, cid, "Dardo incantato", 1, school="evocation", damage_dice="3d4", damage_type="force")
    scelta = _scelta(await _scheda(client, cid), "spell_mastery_1")
    r = await client.post(f"/characters/{cid}/choices/{scelta['id']}/resolve", json={"kind": "class_option", "options": ["Dardo incantato"]})
    assert r.status_code == 200, r.text
    assert (await client.post(f"/characters/{cid}/spells/{dardo}/use", json={"free_cast": True})).status_code == 200  # Maestria: senza slot
    await client.post(f"/characters/{cid}/spells/{dardo}/roll_damage", json={"casting_level": 1, "options": [SATURAZIONE]})
    assert "overchannel" not in _stati(await _scheda(client, cid))  # nessun uso della Saturazione contato


@pytest.mark.caccia(id="CB-2715", fonte="2024 · Mago · Invocatore · Saturazione Magica: un uso per lancio · pag. 174", zona="regola:2024/wizard",
                    voce="ripetizione", copre=["carta:2024/classes/wizard.md#Saturazione Magica / Overchannel (Invocatore 14, pag. 174)",
                                               "POST /characters/{char_id}/spells/{spell_id}/use",
                                               "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
@pytest.mark.xfail(strict=True, reason="CB-2715: difforme dal manuale, confermato")
async def test_saturazione_magica_i_raggi_dello_stesso_lancio_sono_un_solo_uso(client, monkeypatch):
    cid = await _mago(client, 14, "evoker")
    await _pf(client, cid, 200)
    raggio = await _incantesimo(client, cid, "Raggio rovente", 2, school="evocation", attack_save="ATK", damage_dice="2d6",
                                damage_type="fire")
    assert (await client.post(f"/characters/{cid}/spells/{raggio}/use", json={"slot_level": 2})).status_code == 200  # un solo lancio
    monkeypatch.setattr(random, "randint", lambda a, b: 1)
    for _ in range(3):  # tre raggi, ognuno col suo tiro di danno al massimo
        r = await client.post(f"/characters/{cid}/spells/{raggio}/roll_damage", json={"casting_level": 2, "options": [SATURAZIONE]})
        assert r.status_code == 200, r.text
    scheda = await _scheda(client, cid)
    assert scheda["current_hit_points"] == 200 and _stati(scheda)["overchannel"]["data"]["uses"] == 1


# ---------------------------------------------------------------------------
# Verdi
# ---------------------------------------------------------------------------

TABELLA = {  # livello: (trucchetti, preparati, slot)
    1: (3, 4, (2,)), 2: (3, 5, (3,)), 3: (3, 6, (4, 2)), 4: (4, 7, (4, 3)), 5: (4, 9, (4, 3, 2)), 6: (4, 10, (4, 3, 3)),
    7: (4, 11, (4, 3, 3, 1)), 8: (4, 12, (4, 3, 3, 2)), 9: (4, 14, (4, 3, 3, 3, 1)), 10: (5, 15, (4, 3, 3, 3, 2)),
    11: (5, 16, (4, 3, 3, 3, 2, 1)), 12: (5, 16, (4, 3, 3, 3, 2, 1)), 13: (5, 17, (4, 3, 3, 3, 2, 1, 1)),
    14: (5, 18, (4, 3, 3, 3, 2, 1, 1)), 15: (5, 19, (4, 3, 3, 3, 2, 1, 1, 1)), 16: (5, 21, (4, 3, 3, 3, 2, 1, 1, 1)),
    17: (5, 22, (4, 3, 3, 3, 2, 1, 1, 1, 1)), 18: (5, 23, (4, 3, 3, 3, 3, 1, 1, 1, 1)), 19: (5, 24, (4, 3, 3, 3, 3, 2, 1, 1, 1)),
    20: (5, 25, (4, 3, 3, 3, 3, 2, 2, 1, 1)),
}


@pytest.mark.caccia(id="CB-2718", fonte="2024 · Mago · tabella di classe: trucchetti, preparati e slot · pag. 165", zona="regola:2024/wizard",
                    voce="limiti", copre=["carta:2024/classes/wizard.md#Incantesimi / Spellcasting (Mago 1, pag. 165)"])
@pytest.mark.parametrize("livello", list(range(1, 21)))
def test_trucchetti_preparati_e_slot_della_tabella(livello):
    riga = SimpleNamespace(class_name="wizard", level=livello, subclass_key=None, spellcasting_ability="intelligence")
    trucchetti, preparati, slot = TABELLA[livello]
    regolari = slots_for("2024", [riga]).regular
    assert tuple(regolari[lv] for lv in sorted(regolari) if regolari[lv]) == slot
    assert known_limits("2024", "wizard", livello).cantrips == trucchetti
    assert prepared_limit("2024", "wizard", livello, SimpleNamespace(classes=[riga])) == preparati


@pytest.mark.caccia(id="CB-2719", fonte="2024 · Mago · Libro degli Incantesimi pag. 165 e Sapiente 2024 pag. 172; 2014 · Mago · Abiuratore Sapiente pag. 85",
                    zona="regola:2024/wizard", voce="edizioni",
                    copre=["carta:2024/classes/wizard.md#Libro degli Incantesimi / Spellbook (Mago 1, pag. 165)",
                           "carta:2024/classes/wizard.md#Abiurazione Sapiente / Abjuration Savant (Abiuratore 3, pag. 172)",
                           "carta:2014/classes/wizard.md#Abiuratore Sapiente / Abjuration Savant (Abiurazione 2, pag. 85)",
                           "GET /characters/{char_id}/spellbook/cost"])
@pytest.mark.parametrize("edizione,sottoclasse,atteso", [
    ("2014", "abjuration", {"hours": 3, "gold": 75, "halved": True}),
    ("2024", "abjurer", {"hours": 6, "gold": 150, "halved": False}),
])
async def test_copiare_un_abiurazione_costa_per_edizione(client, edizione, sottoclasse, atteso):
    cid = await _mago(client, 5, sottoclasse, edizione)
    r = await client.get(f"/characters/{cid}/spellbook/cost", params={"level": 3, "school": "abjuration", "mode": "copy"})
    assert r.status_code == 200 and r.json() == atteso, r.text


@pytest.mark.caccia(id="CB-2720", fonte="2024 · Mago · Abiuratore · Interdizione Arcana · pag. 172", zona="regola:2024/wizard", voce="regola",
                    copre=["carta:2024/classes/wizard.md#Interdizione Arcana / Arcane Ward (Abiuratore 3, pag. 172)",
                           "POST /characters/{char_id}/spells/{spell_id}/use", "PATCH /characters/{char_id}/hp"])
async def test_interdizione_2024_nasce_con_lo_slot_e_si_ricarica_del_doppio_dello_slot(client):
    cid = await _mago(client, 3, "abjurer")  # 2 x 3 + 3 = 9
    await _pf(client, cid, 50)
    rito = await _incantesimo(client, cid, "Allarme", 1, school="abjuration", is_ritual=True)
    assert (await client.post(f"/characters/{cid}/spells/{rito}/use", json={"as_ritual": True, "confirm": ["ritual_unprepared"]})).status_code == 200
    assert "arcane_ward" not in _stati(await _scheda(client, cid))  # senza slot nessuna interdizione
    scudo = await _incantesimo(client, cid, "Armatura arcana", 1, school="abjuration")
    assert (await client.post(f"/characters/{cid}/spells/{scudo}/use", json={"slot_level": 1})).status_code == 200
    assert _stati(await _scheda(client, cid))["arcane_ward"]["data"]["hp"] == 9
    danno = (await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 9})).json()
    assert danno["current_hit_points"] == 50
    await client.post(f"/characters/{cid}/turn/new")
    assert (await client.post(f"/characters/{cid}/spells/{scudo}/use", json={"slot_level": 2})).status_code == 200
    assert _stati(await _scheda(client, cid))["arcane_ward"]["data"]["hp"] == 4  # 2 x livello dello slot


@pytest.mark.caccia(id="CB-2721", fonte="2024 · Mago · Divinatore · Portento pag. 173 e Portento Superiore pag. 173", zona="regola:2024/wizard",
                    voce="limiti", copre=["carta:2024/classes/wizard.md#Portento / Portent (Divinatore 3, pag. 173)",
                                          "carta:2024/classes/wizard.md#Portento Superiore / Greater Portent (Divinatore 14, pag. 173)",
                                          "POST /characters/{char_id}/rest"])
@pytest.mark.parametrize("livello,dadi", [(2, 0), (3, 2), (13, 2), (14, 3)])
async def test_portento_due_dadi_dal_terzo_e_tre_dal_quattordicesimo(client, monkeypatch, livello, dadi):
    cid = await _mago(client, livello, "diviner")
    monkeypatch.setattr(random, "randint", lambda a, b: 13 if b == 20 else a)
    assert (await _riposo(client, cid, "long")).status_code == 200
    salvati = ((await _scheda(client, cid))["settings"].get("saved_dice") or {}).get(PORTENTO, [])
    assert salvati == [13] * dadi


@pytest.mark.caccia(id="CB-2722", fonte="2024 · Mago · Incantesimi Personali · pag. 167", zona="regola:2024/wizard", voce="ripetizione",
                    copre=["carta:2024/classes/wizard.md#Incantesimi Personali / Signature Spells (Mago 20, pag. 167)",
                           "POST /characters/{char_id}/spells/{spell_id}/use", "POST /characters/{char_id}/rest"])
async def test_incantesimo_personale_gratis_una_volta_poi_un_riposo_breve(client):
    cid = await _mago(client, 20)
    await _oro(client, cid, 2000)
    palla = await _nel_libro(client, cid, "Palla di fuoco", 3, school="evocation")
    await _nel_libro(client, cid, "Controincantesimo", 3, school="abjuration")
    for gruppo, nome in (("signature_1", "Palla di fuoco"), ("signature_2", "Controincantesimo")):
        scelta = _scelta(await _scheda(client, cid), gruppo)
        r = await client.post(f"/characters/{cid}/choices/{scelta['id']}/resolve", json={"kind": "class_option", "options": [nome]})
        assert r.status_code == 200, r.text
    prima = await _usati(client, cid)
    assert (await client.post(f"/characters/{cid}/spells/{palla}/use", json={"free_cast": True})).status_code == 200
    await client.post(f"/characters/{cid}/turn/new")
    di_nuovo = await client.post(f"/characters/{cid}/spells/{palla}/use", json={"free_cast": True})
    assert di_nuovo.status_code == 409 and await _usati(client, cid) == prima
    assert (await _riposo(client, cid, "short")).status_code == 200
    assert (await _abilita(client, cid, "wizard.signature_spell_1"))["uses"] == 1


@pytest.mark.caccia(id="CB-2723", fonte="2024 · Mago · Abiuratore · Interdizione Arcana: l'annullo del danno ridà i PF assorbiti · pag. 172",
                    zona="regola:2024/wizard", voce="annullamento",
                    copre=["carta:2024/classes/wizard.md#Interdizione Arcana / Arcane Ward (Abiuratore 3, pag. 172)",
                           "POST /characters/{char_id}/hp/undo"])
async def test_annullo_del_danno_rida_l_interdizione_2024(client):
    cid = await _mago(client, 6, "abjurer")  # 2 x 6 + 3 = 15
    await _pf(client, cid, 100)
    scudo = await _incantesimo(client, cid, "Armatura arcana", 1, school="abjuration")
    assert (await client.post(f"/characters/{cid}/spells/{scudo}/use", json={"slot_level": 1})).status_code == 200
    danno = (await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 20})).json()
    assert (danno["current_hit_points"], _stati(danno)["arcane_ward"]["data"]["hp"]) == (95, 0)
    annullo = await client.post(f"/characters/{cid}/hp/undo", json={"op_id": danno["hp_undo_id"]})
    assert annullo.status_code == 200, annullo.text
    assert (annullo.json()["current_hit_points"], _stati(annullo.json())["arcane_ward"]["data"]["hp"]) == (100, 15)


@pytest.mark.caccia(id="CB-2724", fonte="2024 · Mago · Memorizzare Incantesimo · pag. 167", zona="regola:2024/wizard", voce="limiti",
                    copre=["carta:2024/classes/wizard.md#Memorizzare Incantesimo / Memorize Spell (Mago 5, pag. 167)",
                           "POST /characters/{char_id}/rest"])
@pytest.mark.parametrize("livello,atteso", [(4, 422), (5, 200)])
async def test_memorizzare_dal_quinto_livello(client, livello, atteso):
    cid = await _mago(client, livello)
    await _oro(client, cid, 500)
    fuori = await _nel_libro(client, cid, "Scudo", 1, school="abjuration")
    dentro = await _nel_libro(client, cid, "Sonno", 1, school="enchantment")
    assert (await client.patch(f"/characters/{cid}/spells/{fuori}", json={"is_prepared": True})).status_code == 200
    r = await _riposo(client, cid, "short", memorize_spell={"out": fuori, "into": dentro})
    assert r.status_code == atteso, r.text


@pytest.mark.caccia(id="CB-2725", fonte="invariante: solo il proprietario usa il Terzo Occhio del suo mago", zona="regola:2024/wizard",
                    voce="permessi", copre=["carta:2024/classes/wizard.md#Terzo Occhio / The Third Eye (Divinatore 10, pag. 173)",
                                            "POST /characters/{char_id}/features/{feature_key}/use"])
async def test_terzo_occhio_solo_del_proprietario(client, come_utente):
    cid = await _mago(client, 10, "diviner")
    come_utente(9002)
    altro = await _usa(client, cid, TERZO_OCCHIO, params={"option": "darkvision"})
    assert altro.status_code in (403, 404)
    come_utente(1234)
    assert (await _abilita(client, cid, TERZO_OCCHIO))["uses"] == 1

