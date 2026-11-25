"""Controlli della zona regola:2014/wizard."""
from types import SimpleNamespace

import pytest

from core.rules.spellcasting import known_limits, slots_for
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, setup_full_encounter
from tests.integration._telegram_stub import install_fake_telegram

SCUOLE = {"abjuration": "Scuola di Abiurazione", "enchantment": "Scuola di Ammaliamento",
          "evocation": "Scuola di Invocazione", "necromancy": "Scuola di Necromanzia",
          "transmutation": "Scuola di Trasmutazione"}


async def _mago(client, livello, scuola=None, **punteggi) -> int:
    corpo = {"name": "Mago", "initial_class": {"class_name": "wizard", "level": livello, "subclass": SCUOLE.get(scuola)}}
    r = await client.post("/characters", json=corpo)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    for nome, valore in punteggi.items():
        r = await client.patch(f"/characters/{cid}/ability_scores/{nome}", json={"value": valore})
        assert r.status_code == 200, r.text
    return cid


async def _scheda(client, cid) -> dict:
    return (await client.get(f"/characters/{cid}")).json()


async def _classe(client, cid, nome) -> int:
    return next(c["id"] for c in (await _scheda(client, cid))["classes"] if c["class_name"].lower() == nome)


async def _incantesimo(client, cid, nome, livello, **altro) -> int:
    r = await client.post(f"/characters/{cid}/spells", json={"name": nome, "level": livello, "casting_time": "1 azione", **altro})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _lancia(client, cid, sid, slot=None):
    return await client.post(f"/characters/{cid}/spells/{sid}/use", json={"slot_level": slot} if slot else {})


async def _usa(client, cid, chiave, **corpo):
    return await client.post(f"/characters/{cid}/features/{chiave}/use", json=corpo)


async def _pf(client, cid, valore) -> None:
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": valore})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": valore})


def _interdizione(scheda: dict) -> dict | None:
    return next((s for s in scheda["active_states"] or [] if s["key"] == "arcane_ward"), None)


async def _opzioni(client, cid, roll, **query) -> list[str]:
    r = await client.get(f"/characters/{cid}/roll-options", params={"roll": roll, **query})
    assert r.status_code == 200, r.text
    return [o["key"] for o in r.json()]


async def _slot_usati(client, cid) -> dict[int, int]:
    return {s["level"]: s["used"] for s in (await _scheda(client, cid))["spell_slots"]}


async def _spendi_slot(client, cid, livello, usati) -> None:
    slot = next(s for s in (await _scheda(client, cid))["spell_slots"] if s["level"] == livello)
    r = await client.patch(f"/characters/{cid}/spell_slots/{slot['id']}", json={"used": usati})
    assert r.status_code == 200, r.text


async def _in_serata(client, factory, monkeypatch, classe: dict) -> tuple[int, int, int]:
    """Serata con incontro attivo: il PG del giocatore (che prende ``classe``) e due goblin. Ritorna (sessione, PG, goblin 1)."""
    install_fake_telegram(monkeypatch)
    sid, _ = await setup_full_encounter(client, factory)
    pc, g1, _g2 = (await client.post(f"/sessions/{sid}/encounter/start", json={})).json()["combatants"]
    as_user(PLAYER_ID)
    cid = pc["character_id"]
    r = await client.post(f"/characters/{cid}/classes", json=classe)
    assert r.status_code == 201, r.text
    await _pf(client, cid, 100)
    return sid, cid, g1["id"]


async def _goblin(client, sid, gid) -> dict:
    as_user(GM_ID)
    live = (await client.get(f"/sessions/{sid}/live")).json()
    as_user(PLAYER_ID)
    return next(c for c in live["encounter"]["combatants"] if c["id"] == gid)


async def _risolvi(client, sid, gid, superato: bool) -> None:
    ts = (await _goblin(client, sid, gid))["pending_saves"][0]
    as_user(GM_ID)
    r = await client.post(f"/sessions/{sid}/encounter/pending-saves/{ts['id']}/resolve", json={"passed": superato})
    assert r.status_code == 200, r.text
    as_user(PLAYER_ID)


async def _bersaglio(client, cid, gid, chiave):
    return await client.post(f"/characters/{cid}/target-effects", json={"combatant_id": gid, "effect_key": chiave})


# ---------------------------------------------------------------------------
# Rossi
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-2111", fonte="2014 · Mago · Interdizione Arcana: 2 x livello dell'incantesimo; regole generali, lancio a livello superiore · pag. 85, 201",
                    zona="regola:2014/wizard", voce="regola",
                    copre=["carta:2014/classes/wizard.md#Interdizione Arcana / Arcane Ward (Abiurazione 2, pag. 85)",
                           "POST /characters/{char_id}/spells/{spell_id}/use"])
async def test_interdizione_ricaricata_dal_livello_a_cui_si_lancia(client):
    cid = await _mago(client, 6, "abjuration", intelligence=16)  # interdizione massima 2 x 6 + 3 = 15
    await _pf(client, cid, 100)
    scudo = await _incantesimo(client, cid, "Scudo", 1, school="abjuration")
    assert (await _lancia(client, cid, scudo, 1)).status_code == 200
    await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 15})
    assert _interdizione(await _scheda(client, cid))["data"]["hp"] == 0
    await client.post(f"/characters/{cid}/turn/new")
    assert (await _lancia(client, cid, scudo, 3)).status_code == 200  # con uno slot di 3° l'incantesimo è di 3° livello
    assert _interdizione(await _scheda(client, cid))["data"]["hp"] == 6


@pytest.mark.caccia(id="CB-2112", fonte="2014 · Mago · Saturazione Magica: solo incantesimi da mago di 1°-5° livello · pag. 87",
                    zona="regola:2014/wizard", voce="interazione",
                    copre=["carta:2014/classes/wizard.md#Saturazione Magica / Overchannel (Invocazione 14, pag. 87)",
                           "GET /characters/{char_id}/roll-options"])
async def test_saturazione_magica_non_vale_per_un_incantesimo_di_un_altra_classe(client):
    cid = await _mago(client, 14, "evocation")
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "cleric", "level": 1, "hit_die": 8})
    assert r.status_code == 201, r.text
    mago, chierico = await _classe(client, cid, "wizard"), await _classe(client, cid, "cleric")
    del_mago = await _incantesimo(client, cid, "Dardo incantato", 1, class_id=mago, school="evocation", damage_dice="3d4",
                                  damage_type="force")
    del_chierico = await _incantesimo(client, cid, "Dardo tracciante", 1, class_id=chierico, school="evocation",
                                      attack_save="ATK", damage_dice="4d6", damage_type="radiant")
    assert "wizard.overchannel" in await _opzioni(client, cid, "spell_damage", spell_id=del_mago)
    assert "wizard.overchannel" not in await _opzioni(client, cid, "spell_damage", spell_id=del_chierico)


@pytest.mark.caccia(id="CB-2113", fonte="2014 · Mago · Sguardo Ipnotico: finito l'effetto la creatura non è più bersaglio fino al riposo lungo · pag. 85",
                    zona="regola:2014/wizard", voce="regola",
                    copre=["carta:2014/classes/wizard.md#Sguardo Ipnotico / Hypnotic Gaze (Ammaliamento 2, pag. 85)",
                           "POST /characters/{char_id}/target-effects"])
async def test_sguardo_ipnotico_non_si_ripete_sulla_stessa_creatura_dopo_la_fine(client, test_session_factory, monkeypatch):
    sid, cid, g1 = await _in_serata(client, test_session_factory, monkeypatch,
                                    {"class_name": "wizard", "level": 2, "hit_die": 6, "subclass": "Scuola di Ammaliamento"})
    assert (await _usa(client, cid, "wizard.hypnotic_gaze")).status_code == 200
    assert (await _bersaglio(client, cid, g1, "wizard.hypnotic_gaze")).json()["pending_save_id"] is not None
    await _risolvi(client, sid, g1, superato=False)
    assert (await _goblin(client, sid, g1))["conditions"].get("charmed")
    for _ in range(9):  # i turni passano finché l'effetto non finisce
        if not (await _goblin(client, sid, g1))["conditions"].get("charmed"):
            break
        as_user(GM_ID)
        assert (await client.post(f"/sessions/{sid}/encounter/next-turn")).status_code == 200
        as_user(PLAYER_ID)
    assert not (await _goblin(client, sid, g1))["conditions"].get("charmed")
    await client.post(f"/characters/{cid}/turn/new")
    assert (await _usa(client, cid, "wizard.hypnotic_gaze")).status_code == 200
    di_nuovo = await _bersaglio(client, cid, g1, "wizard.hypnotic_gaze")
    assert di_nuovo.status_code == 409 and di_nuovo.json()["detail"]["code"] == "target_immune"


@pytest.mark.caccia(id="CB-2114", fonte="2014 · Mago · Comandare Non Morti: TS superato, mai più contro quella creatura · pag. 88",
                    zona="regola:2014/wizard", voce="limiti",
                    copre=["carta:2014/classes/wizard.md#Comandare Non Morti / Command Undead (Necromanzia 14, pag. 88)",
                           "POST /characters/{char_id}/target-effects", "POST /characters/{char_id}/rest"])
@pytest.mark.xfail(strict=True, reason="CB-2114: difforme dal manuale, confermato")
async def test_comandare_non_morti_immunita_anche_dopo_il_riposo_lungo(client, test_session_factory, monkeypatch):
    sid, cid, g1 = await _in_serata(client, test_session_factory, monkeypatch,
                                    {"class_name": "wizard", "level": 14, "hit_die": 6, "subclass": "Scuola di Necromanzia"})
    assert (await _usa(client, cid, "wizard.command_undead", params={"intelligence": "lt8"})).status_code == 200
    assert (await _bersaglio(client, cid, g1, "wizard.command_undead")).status_code == 200
    await _risolvi(client, sid, g1, superato=True)
    r = await client.post(f"/characters/{cid}/rest", json={"rest_type": "long", "confirm_early": True})
    assert r.status_code == 200, r.text
    await client.post(f"/characters/{cid}/turn/new")
    assert (await _usa(client, cid, "wizard.command_undead", params={"intelligence": "lt8"})).status_code == 200
    di_nuovo = await _bersaglio(client, cid, g1, "wizard.command_undead")
    assert di_nuovo.status_code == 409 and di_nuovo.json()["detail"]["code"] == "target_immune"


@pytest.mark.caccia(id="CB-2115", fonte="2014 · Mago · Pietra del Trasmutatore: +3 m solo se non ingombrato · pag. 88",
                    zona="regola:2014/wizard", voce="regola",
                    copre=["carta:2014/classes/wizard.md#Pietra del Trasmutatore / Transmuter's Stone (Trasmutazione 6, pag. 88)",
                           "POST /characters/{char_id}/features/{feature_key}/use"])
async def test_pietra_velocita_niente_bonus_da_ingombrato(client):
    cid = await _mago(client, 6, "transmutation", strength=10)  # variante: ingombrato oltre 50 lb
    impostazioni = {**((await _scheda(client, cid))["settings"] or {}), "encumbrance_variant": True}
    assert (await client.patch(f"/characters/{cid}", json={"settings": impostazioni})).status_code == 200
    r = await client.post(f"/characters/{cid}/items", json={"name": "Zavorra", "item_type": "generic", "weight": 60})
    assert r.status_code == 201, r.text
    scheda = await _scheda(client, cid)
    assert scheda["encumbrance_level"] == "encumbered"
    base = scheda["computed"]["speed"]
    assert (await _usa(client, cid, "wizard.transmuters_stone", params={"benefit": "speed"})).status_code == 200
    assert (await _scheda(client, cid))["computed"]["speed"] == base


@pytest.mark.caccia(id="CB-2116", fonte="2014 · Mago · Alterare Ricordi: una volta, prima che l'ammaliamento termini · pag. 85",
                    zona="regola:2014/wizard", voce="regola",
                    copre=["carta:2014/classes/wizard.md#Alterare Ricordi / Alter Memories (Ammaliamento 14, pag. 85)",
                           "POST /characters/{char_id}/features/{feature_key}/use"])
async def test_alterare_ricordi_resta_finche_dura_l_ammaliamento(client):
    cid = await _mago(client, 14, "enchantment")
    charme = await _incantesimo(client, cid, "Charme su persone", 1, school="enchantment", duration="1 ora", attack_save="WIS")
    assert (await _lancia(client, cid, charme, 1)).status_code == 200
    await client.post(f"/characters/{cid}/turn/new")
    dardo = await _incantesimo(client, cid, "Dardo incantato", 1, school="evocation")
    assert (await _lancia(client, cid, dardo, 1)).status_code == 200  # il charme dura ancora un'ora
    await client.post(f"/characters/{cid}/turn/new")
    assert (await _usa(client, cid, "wizard.alter_memories")).status_code == 200




# ---------------------------------------------------------------------------
# Verdi
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-2118", fonte="2014 · Mago · tabella di classe: slot e trucchetti per livello · pag. 82-83",
                    zona="regola:2014/wizard", voce="limiti",
                    copre=["carta:2014/classes/wizard.md#Incantesimi / Spellcasting (Mago 1, pag. 83)",
                           "carta:2014/classes/wizard.md#Trucchetti / Cantrips (Mago 1, pag. 83)"])
@pytest.mark.parametrize("livello, slot, trucchetti", [
    (1, (2,), 3), (2, (3,), 3), (3, (4, 2), 3), (4, (4, 3), 4), (9, (4, 3, 3, 3, 1), 4), (10, (4, 3, 3, 3, 2), 5),
    (17, (4, 3, 3, 3, 2, 1, 1, 1, 1), 5), (18, (4, 3, 3, 3, 3, 1, 1, 1, 1), 5), (19, (4, 3, 3, 3, 3, 2, 1, 1, 1), 5),
    (20, (4, 3, 3, 3, 3, 2, 2, 1, 1), 5)])
def test_slot_e_trucchetti_seguono_la_tabella(livello, slot, trucchetti):
    riga = SimpleNamespace(class_name="wizard", level=livello, subclass_key=None, spellcasting_ability="intelligence")
    regolari = slots_for("2014", [riga]).regular
    assert tuple(regolari[lv] for lv in sorted(regolari)) == slot
    assert known_limits("2014", "wizard", livello).cantrips == trucchetti


@pytest.mark.caccia(id="CB-2119", fonte="2014 · Mago · Preparare: mod. Intelligenza + livello da mago, minimo 1 · pag. 83",
                    zona="regola:2014/wizard", voce="limiti",
                    copre=["carta:2014/classes/wizard.md#Preparare e Lanciare Incantesimi / Preparing and Casting Spells (Mago 1, pag. 83)",
                           "GET /characters/{char_id}"])
@pytest.mark.parametrize("livello, intelligenza, atteso", [(1, 6, 1), (1, 12, 2), (5, 16, 8), (20, 20, 25)])
async def test_incantesimi_preparabili(client, livello, intelligenza, atteso):
    cid = await _mago(client, livello, intelligence=intelligenza)
    assert (await _scheda(client, cid))["spellcasting"]["limits"][0]["prepared_limit"] == atteso


@pytest.mark.caccia(id="CB-2120", fonte="2014 · Multiclasse: libro e preparazione seguono i livelli da mago (mago 3, Int 16: sei) · pag. 164",
                    zona="regola:2014/wizard", voce="interazione",
                    copre=["carta:2014/classes/wizard.md#Multiclasse: Mago / Multiclassing: Wizard (Manuale 2014, pag. 163)",
                           "POST /characters/{char_id}/classes"])
async def test_multiclasse_preparati_dai_soli_livelli_da_mago(client):
    cid = await _mago(client, 3, intelligence=16)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "cleric", "level": 5, "hit_die": 8})
    assert r.status_code == 201, r.text
    mago = await _classe(client, cid, "wizard")
    riga = next(x for x in (await _scheda(client, cid))["spellcasting"]["limits"] if x["class_id"] == mago)
    assert riga["prepared_limit"] == 6


@pytest.mark.caccia(id="CB-2121", fonte="2014 · Mago · Caratteristica da incantatore: CD 8 + competenza + Int, attacco competenza + Int · pag. 83",
                    zona="regola:2014/wizard", voce="regola",
                    copre=["carta:2014/classes/wizard.md#Caratteristica da Incantatore / Spellcasting Ability (Mago 1, pag. 83)",
                           "GET /characters/{char_id}"])
async def test_cd_e_attacco_con_intelligenza(client):
    cid = await _mago(client, 5, intelligence=18)  # competenza +3, Int +4
    [mago] = (await _scheda(client, cid))["spellcasting"]["casters"]
    assert (mago["ability"], mago["save_dc"], mago["attack_bonus"]) == ("intelligence", 15, 7)


@pytest.mark.caccia(id="CB-2122", fonte="2014 · Mago · Preparare: Int + livello (pag. 83); 2024 · Mago · Incantesimi: tabella (pag. 165)",
                    zona="regola:2014/wizard", voce="edizioni",
                    copre=["carta:2014/classes/wizard.md#Preparare e Lanciare Incantesimi / Preparing and Casting Spells (Mago 1, pag. 83)",
                           "carta:2024/classes/wizard.md#Incantesimi / Spellcasting (Mago 1, pag. 165)",
                           "PATCH /characters/{char_id}"])
@pytest.mark.parametrize("edizione, atteso", [("2014", 8), ("2024", 9)])
async def test_preparati_per_edizione(client, edizione, atteso):
    cid = await _mago(client, 5, intelligence=16)
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": edizione})).status_code == 200
    assert (await _scheda(client, cid))["spellcasting"]["limits"][0]["prepared_limit"] == atteso


@pytest.mark.caccia(id="CB-2123", fonte="2014 · Mago · Recupero Arcano: una volta al giorno · pag. 84",
                    zona="regola:2014/wizard", voce="ripetizione",
                    copre=["carta:2014/classes/wizard.md#Recupero Arcano / Arcane Recovery (Mago 1, pag. 84)",
                           "POST /characters/{char_id}/rest"])
async def test_recupero_arcano_ripetuto_non_rende_due_volte(client):
    cid = await _mago(client, 4)  # due livelli di slot
    await _spendi_slot(client, cid, 1, 4)
    corpo = {"rest_type": "short", "arcane_recovery": {"1": 2}}
    assert (await client.post(f"/characters/{cid}/rest", json=corpo)).status_code == 200
    di_nuovo = await client.post(f"/characters/{cid}/rest", json=corpo)
    assert di_nuovo.status_code == 409 and di_nuovo.json()["detail"]["code"] == "no_uses"
    assert (await _slot_usati(client, cid))[1] == 2


@pytest.mark.caccia(id="CB-2124", fonte="invariante: solo il proprietario usa il Recupero Arcano del suo mago",
                    zona="regola:2014/wizard", voce="permessi",
                    copre=["carta:2014/classes/wizard.md#Recupero Arcano / Arcane Recovery (Mago 1, pag. 84)",
                           "POST /characters/{char_id}/rest"])
async def test_recupero_arcano_solo_del_proprietario(client, come_utente):
    cid = await _mago(client, 4)
    await _spendi_slot(client, cid, 1, 4)
    come_utente(9002)
    altro = await client.post(f"/characters/{cid}/rest", json={"rest_type": "short", "arcane_recovery": {"1": 2}})
    assert altro.status_code in (403, 404)
    come_utente(1234)
    assert (await _slot_usati(client, cid))[1] == 4


@pytest.mark.caccia(id="CB-2125", fonte="2014 · Mago · Interdizione Arcana: l'annullo del danno ridà i PF assorbiti · pag. 85",
                    zona="regola:2014/wizard", voce="annullamento",
                    copre=["carta:2014/classes/wizard.md#Interdizione Arcana / Arcane Ward (Abiurazione 2, pag. 85)",
                           "POST /characters/{char_id}/hp/undo"])
async def test_annullo_del_danno_rida_l_interdizione(client):
    cid = await _mago(client, 6, "abjuration", intelligence=16)
    await _pf(client, cid, 100)
    assert (await _lancia(client, cid, await _incantesimo(client, cid, "Scudo", 1, school="abjuration"), 1)).status_code == 200
    danno = (await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 20})).json()
    assert (danno["current_hit_points"], _interdizione(danno)["data"]["hp"]) == (95, 0)
    annullo = await client.post(f"/characters/{cid}/hp/undo", json={"op_id": danno["hp_undo_id"]})
    assert annullo.status_code == 200, annullo.text
    assert (annullo.json()["current_hit_points"], _interdizione(annullo.json())["data"]["hp"]) == (100, 15)
