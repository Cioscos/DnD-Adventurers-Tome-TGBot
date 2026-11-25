"""Controlli scritti dalla correzione del gruppo lancio-core per i dubbi risolti come difetti (Q-…)."""
import pytest

from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, seed_session
from tests.integration.rules.test_2014_bard_inspiration import _seat
from tests.integration.rules.test_2014_fighter_eldritch_knight import _spell
from tests.integration.rules.test_2014_sorcerer import _slots
from tests.integration.rules.test_2024_sorcerer import QUICKENED, _cast, _caster24
from tests.integration.rules.test_2024_sorcerer_subclasses import _spells


async def _pg(client, classe, livello, edizione="2014", sottoclasse=None, **punteggi) -> tuple[int, int]:
    """``(personaggio, classe)``."""
    r = await client.post("/characters", json={"name": "Incantatore", "rules_edition": edizione,
                                               "initial_class": {"class_name": classe, "level": livello, "subclass": sottoclasse}})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    for caratteristica, valore in punteggi.items():
        r = await client.patch(f"/characters/{cid}/ability_scores/{caratteristica}", json={"value": valore})
        assert r.status_code == 200, r.text
    return cid, (await client.get(f"/characters/{cid}")).json()["classes"][0]["id"]


@pytest.mark.caccia(id="CB-3991", fonte="2014 · Incantesimi · Contattare Altri Piani · pag. 224", zona="regola:2014/incantesimi-A-C", voce="regola",
                    copre=["carta:2014/spells.md#Contattare Altri Piani", "GET /characters/{char_id}/spells"])
async def test_contattare_altri_piani_mostra_la_cd_15_fissa_del_ts_di_chi_lancia(client):
    cid, classe = await _pg(client, "warlock", 9, charisma=20)  # CD degli incantesimi 8 + 4 + 5 = 17
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Contattare Altri Piani", "srd_index": "contact-other-plane", "level": 5,
                                                            "attack_save": "SAVE", "class_id": classe, "is_prepared": True})
    assert r.status_code == 201, r.text
    contatto = next(s for s in (await client.get(f"/characters/{cid}/spells")).json() if s["srd_index"] == "contact-other-plane")
    # Q-2014-incantesimi-a-c-3, opzione A: chi lancia fa un TS di Intelligenza con CD 15, qualunque sia la sua CD
    assert (contatto["attack_save"], contatto["save_dc"]) == ("SAVE", 15)


@pytest.mark.caccia(id="CB-3992", fonte="decisione D-041 (tests/caccia/decisioni.md): rifiutato su sé stessi, come nel 2024; 2014 · Incantesimi · Vincolo di Interdizione · pag. 289", zona="regola:2014/incantesimi-S-Z", voce="regola",
                    copre=["carta:2014/spells.md#Vincolo di Interdizione", "POST /characters/{char_id}/spells/{spell_id}/use"])
@pytest.mark.parametrize("su_di_se", [True, False], ids=["su_di_se", "senza_bersagli"])
async def test_vincolo_di_interdizione_non_si_lancia_su_chi_lo_lancia(client, su_di_se):
    cid, classe = await _pg(client, "cleric", 3)
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Vincolo di Interdizione", "srd_index": "warding-bond", "level": 2,
                                                            "class_id": classe, "is_prepared": True})
    assert r.status_code == 201, r.text
    corpo = {"slot_level": 2, **({"targets": [cid]} if su_di_se else {})}
    r = await client.post(f"/characters/{cid}/spells/{r.json()['id']}/use", json=corpo)
    # Q-2014-incantesimi-s-z-1, opzione A: il vincolo lega chi lancia a un'altra creatura, che riceve +1 CA e TS e resistenza
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_target", r.text
    scheda = (await client.get(f"/characters/{cid}")).json()
    assert not any(s["key"] == "spell:warding_bond" for s in scheda["active_states"] or [])
    assert next(s for s in scheda["spell_slots"] if s["level"] == 2)["used"] == 0  # rifiutato prima di spendere lo slot


@pytest.mark.caccia(id="CB-3993", fonte="2014 · Incantesimi · Guarigione di Massa · pag. 240", zona="regola:2014/incantesimi-G-L", voce="regola",
                    copre=["carta:2014/spells.md#Guarigione di Massa", "POST /characters/{char_id}/spells/{spell_id}/roll_healing"])
@pytest.mark.xfail(strict=True, reason="CB-3993: difforme dal manuale, confermato")
async def test_guarigione_di_massa_divide_i_700_pf_fra_piu_creature(client, test_session_factory):
    _, eroe = await seed_session(test_session_factory)
    as_user(PLAYER_ID)
    for op, valore in (("set_max", 200), ("set_current", 100)):
        assert (await client.patch(f"/characters/{eroe}/hp", json={"op": op, "value": valore})).status_code == 200
    as_user(GM_ID)
    cid, classe = await _pg(client, "cleric", 17)
    for op, valore in (("set_max", 60), ("set_current", 10)):
        assert (await client.patch(f"/characters/{cid}/hp", json={"op": op, "value": valore})).status_code == 200
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Guarigione di Massa", "srd_index": "mass-heal", "level": 9,
                                                            "class_id": classe, "is_prepared": True})
    assert r.status_code == 201, r.text
    sid = r.json()["id"]
    await _seat(test_session_factory, cid, GM_ID)
    assert (await client.post(f"/characters/{cid}/spells/{sid}/use", json={"slot_level": 9})).status_code == 200
    # Q-2014-incantesimi-g-l-1: fino a 700 PF divisi a piacere fra quante creature si vuole; 100 + 50 mancanti stanno nei 700
    r = await client.post(f"/characters/{cid}/spells/{sid}/roll_healing", json={"casting_level": 9, "apply_to_self": True,
                                                                               "target_character_ids": [eroe]})
    assert r.status_code == 200, r.text
    assert (await client.get(f"/characters/{cid}")).json()["current_hit_points"] == 60
    as_user(PLAYER_ID)
    assert (await client.get(f"/characters/{eroe}")).json()["current_hit_points"] == 200


@pytest.mark.caccia(id="CB-3994", fonte="2024 · Incantesimi · Guarigione di Massa · pag. 296", zona="regola:2024/incantesimi-G-L", voce="regola",
                    copre=["carta:2024/spells.md#Guarigione di Massa", "POST /characters/{char_id}/spells/{spell_id}/roll_healing"])
@pytest.mark.xfail(strict=True, reason="CB-3994: difforme dal manuale, confermato")
async def test_guarigione_di_massa_2024_divide_i_700_pf_fra_piu_creature(client, test_session_factory):
    _, eroe = await seed_session(test_session_factory)
    as_user(PLAYER_ID)
    for op, valore in (("set_max", 200), ("set_current", 100)):
        assert (await client.patch(f"/characters/{eroe}/hp", json={"op": op, "value": valore})).status_code == 200
    as_user(GM_ID)
    cid, classe = await _pg(client, "cleric", 17, edizione="2024")
    for op, valore in (("set_max", 60), ("set_current", 10)):
        assert (await client.patch(f"/characters/{cid}/hp", json={"op": op, "value": valore})).status_code == 200
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Guarigione di Massa", "srd_index": "mass-heal", "level": 9,
                                                            "class_id": classe, "is_prepared": True})
    assert r.status_code == 201, r.text
    sid = r.json()["id"]
    await _seat(test_session_factory, cid, GM_ID)
    assert (await client.post(f"/characters/{cid}/spells/{sid}/use", json={"slot_level": 9})).status_code == 200
    # Q-2024-incantesimi-g-l-1: fino a 700 PF divisi a scelta fra qualsiasi numero di creature visibili; 100 + 50 mancanti stanno nei 700
    r = await client.post(f"/characters/{cid}/spells/{sid}/roll_healing", json={"casting_level": 9, "apply_to_self": True,
                                                                               "target_character_ids": [eroe]})
    assert r.status_code == 200, r.text
    assert (await client.get(f"/characters/{cid}")).json()["current_hit_points"] == 60
    as_user(PLAYER_ID)
    assert (await client.get(f"/characters/{eroe}")).json()["current_hit_points"] == 200


@pytest.mark.caccia(id="CB-3995", fonte="2014 · Incantesimi · Rinascita · pag. 271; Rianimare Morti · pag. 270", zona="regola:2014/incantesimi-M-R",
                    voce="regola", copre=["carta:2014/spells.md#Rinascita", "carta:2014/spells.md#Rianimare Morti",
                                          "POST /characters/{char_id}/spells/{spell_id}/roll_healing"])
@pytest.mark.parametrize("srd,livello", [("revivify", 3), ("raise-dead", 5)])
async def test_rinascita_e_rianimare_morti_non_curano_un_alleato_vivo(client, test_session_factory, srd, livello):
    _, eroe = await seed_session(test_session_factory)
    as_user(PLAYER_ID)
    for op, valore in (("set_max", 10), ("set_current", 5)):
        assert (await client.patch(f"/characters/{eroe}/hp", json={"op": op, "value": valore})).status_code == 200
    as_user(GM_ID)
    cid, _ = await _pg(client, "cleric", 9, sottoclasse="Dominio della Vita")  # Discepolo della Vita: 2 + livello a ogni cura
    sid = next(s["id"] for s in (await client.get(f"/characters/{cid}/spells")).json() if s["srd_index"] == srd)  # dal Dominio
    await _seat(test_session_factory, cid, GM_ID)
    assert (await client.post(f"/characters/{cid}/spells/{sid}/use", json={"slot_level": livello})).status_code == 200
    # Q-2014-incantesimi-m-r-4: riportano in vita con 1 PF una creatura morta; una creatura viva non recupera nulla
    await client.post(f"/characters/{cid}/spells/{sid}/roll_healing", json={"casting_level": livello, "target_character_ids": [eroe]})
    as_user(PLAYER_ID)
    assert (await client.get(f"/characters/{eroe}")).json()["current_hit_points"] == 5


@pytest.mark.caccia(id="CB-4561", fonte="2024 · Stregone · Incantesimo Rapido · pag. 142; Stregoneria Psionica · pag. 146", zona="regola:2024/sorcerer",
                    voce="interazione",
                    copre=["carta:2024/classes/sorcerer.md#Incantesimo Rapido / Quickened Spell (Metamagia, pag. 142)",
                           "POST /characters/{char_id}/spells/{spell_id}/use"])
async def test_dopo_rapido_senza_slot_un_incantesimo_di_livello_va_confermato_e_un_trucchetto_no(client):
    cid = await _caster24(client, 6, "quickened")
    classe = (await client.get(f"/characters/{cid}")).json()["classes"][0]["id"]
    r = await client.patch(f"/characters/{cid}/classes/{classe}", json={"subclass": "Stregoneria Aberrante"})
    assert r.status_code == 200, r.text
    psionico = (await _spells(client, cid))["arms-of-hadar"]["id"]
    r = await client.post(f"/characters/{cid}/spells/{psionico}/use", json={"ki": True, "options": [QUICKENED], "option_inputs": {}})
    assert r.status_code == 200, r.text
    charme = await _spell(client, cid, "Charme", 1)
    prima = (await _slots(client, cid))[1]
    # Q-2024-sorcerer-1, opzione A: un avviso da confermare, come le altre regole del turno, anche senza slot già spesi
    r = await _cast(client, cid, charme, slot_level=1)
    assert r.status_code == 409 and r.json()["detail"] == {"code": "cast_confirm", "warnings": ["quickened_after"]}, r.text
    assert (await _slots(client, cid))[1] == prima
    assert (await client.get(f"/characters/{cid}/spells/{charme}/cast-check")).json() == ["quickened_after"]
    trucchetto = await _spell(client, cid, "Luce", 0)
    assert (await client.get(f"/characters/{cid}/spells/{trucchetto}/cast-check")).json() == []
    r = await client.post(f"/characters/{cid}/spells/{charme}/use", json={"slot_level": 1, "confirm": ["quickened_after"]})
    assert r.status_code == 200, r.text
    assert (await client.post(f"/characters/{cid}/turn/new")).status_code == 200
    assert (await client.get(f"/characters/{cid}/spells/{charme}/cast-check")).json() == []
