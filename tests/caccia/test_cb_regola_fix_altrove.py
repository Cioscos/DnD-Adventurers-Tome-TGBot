"""Controlli delle revisioni delle correzioni regole 2026-11-24: lo stesso errore trovato altrove."""
import pytest

from tests.caccia.test_cb_regola_2014_incantesimi_g_l import _pg, _scheda
from tests.caccia.test_cb_regola_2024_incantesimi_a_c import _dal_catalogo, _pg as _pg24
from tests.caccia.test_cb_regola_2024_paladin import _seduti
from tests.caccia.test_cb_regola_2024_rogue import _ladro
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, setup_full_encounter
from tests.integration.rules.test_2014_bard import _roll_keys, _states, _use
from tests.integration.rules.test_2014_fighter_eldritch_knight import _spell
from tests.integration.rules.test_2014_sorcerer_metamagic import TWINNED, _caster
from tests.integration.rules.test_2014_wizard import _wizard
from tests.integration.rules.test_2014_wizard_illusion_evocation import _illusion
from tests.integration.rules.test_2024_cleric_domains import _dom, _spell_rows
from tests.integration.rules.test_2024_druid_circles import _circle
from tests.integration.rules.test_2024_paladin_oaths import _oath
from tests.integration.test_magic_items import _item


@pytest.mark.caccia(id="CB-4701", fonte="2024 · Chierico · Benedizione del Dio della Guerra (nessun bonus al tiro per colpire) · pag. 77",
                    zona="regola:2024/cleric", voce="edizioni",
                    copre=["carta:2024/classes/cleric.md#Benedizione del Dio della Guerra / War God's Blessing (Guerra 6, pag. 77)",
                           "GET /characters/{char_id}/roll-options"])
async def test_la_benedizione_2024_non_offre_il_piu_dieci_del_2014(client):
    cid = await _dom(client, 6, "war")
    assert (await _use(client, cid, "cleric.war_gods_blessing", params={"spell": "shield-of-faith"})).status_code == 200
    scudo = (await _spell_rows(client, cid))["shield-of-faith"]["id"]
    assert (await client.post(f"/characters/{cid}/spells/{scudo}/use", json={"free_cast": True})).status_code == 200
    assert "war_gods_blessing" in [s["key"] for s in await _states(client, cid)]  # il minuto del privilegio
    assert "war_blessing:add" not in await _roll_keys(client, cid, "attack")


async def _da_oggetto(client, cid, **incantesimo) -> dict:
    iid = await _item(client, cid, name="Bacchetta", charges={"current": 3, "max": 3}, granted_spells=[
        {"charges_cost": 1, "is_concentration": True, **incantesimo}])
    r = await client.post(f"/characters/{cid}/items/{iid}/cast", json={"spell_index": 0})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.caccia(id="CB-4702", fonte="2014 · Incantesimi · Immagine Maggiore pag. 242, Scagliare Maledizione pag. 273, Dominare Persone pag. 232; "
                    "2024 · Immagine Maggiore pag. 295 (concentrazione e durata dallo slot)",
                    zona="regola:2014/incantesimi-G-L", voce="interazione",
                    copre=["carta:2014/spells.md#Immagine Maggiore", "carta:2014/spells.md#Dominare Persone", "carta:2024/spells.md#Immagine Maggiore",
                           "POST /characters/{char_id}/items/{item_id}/cast"])
@pytest.mark.parametrize("edizione,indice,nome,base,slot,atteso", [
    ("2014", "major-image", "Immagine Maggiore", 3, 6, None), ("2024", "major-image", "Immagine Maggiore", 3, 4, None),
    ("2014", "major-image", "Immagine Maggiore", 3, 5, 100), ("2014", "bestow-curse", "Scagliare Maledizione", 3, 4, 100),
    ("2014", "bestow-curse", "Scagliare Maledizione", 3, 5, None), ("2014", "dominate-person", "Dominare Persone", 5, 7, 600)])
async def test_lancio_da_oggetto_a_slot_alto_segue_lo_slot_per_concentrazione_e_durata(client, edizione, indice, nome, base, slot, atteso):
    cid = await _pg(client, "fighter", 5, edizione=edizione)
    durata = "Concentrazione, fino a 10 minuti" if indice == "major-image" else "Concentrazione, fino a 1 minuto"
    s = (await _da_oggetto(client, cid, name=nome, srd_index=indice, level=base, slot_level=slot, duration=durata))["settings"] or {}
    assert (s.get("concentration_rounds_left"), bool(s.get("concentration_item_spell"))) == (atteso, atteso is not None)


async def _rilancia(client, cid, spell, **corpo):
    r = await client.post(f"/characters/{cid}/spells/{spell}/use", json=corpo)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.caccia(id="CB-4704", fonte="2014 · Mago · Realtà Illusoria (finché l'incantesimo è attivo) · pag. 87; Alterare Ricordi (prima che l'incantesimo termini) · pag. 85",
                    zona="regola:2014/wizard", voce="interazione",
                    copre=["carta:2014/classes/wizard.md#Realtà Illusoria / Illusory Reality (Illusione 14, pag. 87)",
                           "POST /characters/{char_id}/spells/{spell_id}/use", "POST /characters/{char_id}/features/{feature_key}/use"])
async def test_la_finestra_di_realta_illusoria_resta_con_una_illusione_a_concentrazione(client):
    cid = await _wizard(client, 14, "illusion")
    await _rilancia(client, cid, await _illusion(client, cid, is_concentration=True), slot_level=1)
    r = await _use(client, cid, "wizard.illusory_reality", params={"object": "Ponte"})
    assert r.status_code == 200, r.text


@pytest.mark.caccia(id="CB-4703", fonte="2014 · Mago · Realtà Illusoria (finché l'incantesimo è attivo) · pag. 87; Immagine Maggiore dal 6° senza concentrazione · pag. 242",
                    zona="regola:2014/wizard", voce="interazione",
                    copre=["carta:2014/classes/wizard.md#Realtà Illusoria / Illusory Reality (Illusione 14, pag. 87)", "carta:2014/spells.md#Immagine Maggiore",
                           "POST /characters/{char_id}/spells/{spell_id}/use", "POST /characters/{char_id}/features/{feature_key}/use"])
@pytest.mark.parametrize("slot", [3, 6])
async def test_realta_illusoria_vale_finche_dura_l_immagine_maggiore_lanciata_con_quello_slot(client, slot):
    cid = await _wizard(client, 14, "illusion")
    silenziosa = await _illusion(client, cid, is_concentration=True)
    maggiore = await _illusion(client, cid, 3, "Concentrazione, fino a 10 minuti", "Immagine Maggiore", is_concentration=True, srd_index="major-image")
    await _rilancia(client, cid, silenziosa, slot_level=1)  # una concentrazione di prima
    assert (await client.post(f"/characters/{cid}/turn/new")).status_code == 200
    await _rilancia(client, cid, maggiore, slot_level=slot)
    assert (await client.patch(f"/characters/{cid}/concentration", json={"spell_id": None})).status_code == 200
    r = await _use(client, cid, "wizard.illusory_reality", params={"object": "Ponte"})
    # col 3° l'illusione era la concentrazione appena persa; col 6° dura finché non è dissolta, la concentrazione non c'entra
    assert r.status_code == (409 if slot == 3 else 200), r.text


@pytest.mark.caccia(id="CB-4705", fonte="2014 · Incantesimi · Dominare Persone (slot del 7°: 1 ora) · pag. 232", zona="regola:2014/incantesimi-D-F",
                    voce="interazione", copre=["carta:2014/spells.md#Dominare Persone", "PATCH /characters/{char_id}/concentration"])
async def test_riprendere_la_concentrazione_nel_turno_del_lancio_tiene_lo_slot(client):
    cid = await _pg(client, "wizard", 13)
    domina = await _spell(client, cid, "Dominare Persone", 5, srd_index="dominate-person", duration="Concentrazione, fino a 1 minuto",
                          is_concentration=True, school="enchantment")
    assert (await _rilancia(client, cid, domina, slot_level=7))["settings"]["concentration_rounds_left"] == 600
    assert (await client.patch(f"/characters/{cid}/concentration", json={"spell_id": None})).status_code == 200  # tolta per sbaglio
    r = await client.patch(f"/characters/{cid}/concentration", json={"spell_id": domina})
    assert r.status_code == 200, r.text
    s = r.json()["settings"]
    assert (s["concentration_rounds_left"], s["concentration_level"]) == (600, 7)


@pytest.mark.caccia(id="CB-4706", fonte="2024 · Incantesimi · Evoca Fatato (3d12 + modificatore da incantatore) · pag. 255", zona="regola:2024/incantesimi-A-C",
                    voce="regola", copre=["carta:2024/spells.md#Evoca Fatato", "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
async def test_l_attacco_dello_spirito_di_evoca_fatato_somma_il_modificatore(client, dadi):
    cid = await _pg24(client, "druid", 11, wisdom=16)  # Saggezza +3
    spirito = await _dal_catalogo(client, cid, "conjure-fey")
    dadi(4, 5, 6)
    r = await client.post(f"/characters/{cid}/spells/{spirito['id']}/roll_damage", json={"casting_level": 6})
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 15 + 3


@pytest.mark.caccia(id="CB-4707", fonte="2014 · Combattimento · Tiri per i Danni (mai sotto 0) · pag. 196; Stregone · Incantesimo Raddoppiato · pag. 110",
                    zona="regola:2014/sorcerer", voce="limiti",
                    copre=["carta:2014/classes/sorcerer.md#Incantesimo Raddoppiato / Twinned Spell (Stregone 3, pag. 110)",
                           "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
async def test_il_danno_del_secondo_bersaglio_di_raddoppiato_non_scende_sotto_zero(client, dadi):
    cid = await _caster(client, 10, "twinned")
    raggio = await _spell(client, cid, "Raggio debole", 0, attack_save="ATK", damage_dice="1d4-3", damage_type="cold", range_area="18 m")
    dadi(10, 10, 1, 1, 1, 1)  # i due tiri per colpire, poi 2d4-3 per ciascun bersaglio (trucchetto al 10° livello)
    r = await client.post(f"/characters/{cid}/spells/{raggio}/attack", json={"cast_options": [TWINNED], "cast_option_inputs": {}})
    assert r.status_code == 200, r.text
    r = await client.post(f"/characters/{cid}/spells/{raggio}/roll_damage", json={})
    assert r.status_code == 200, r.text
    assert (r.json()["total"], r.json()["twinned_damage"]["total"]) == (0, 0)


@pytest.mark.caccia(id="CB-4708", fonte="2024 · Paladino · Aura di Interdizione (solo dentro l'aura) · pag. 116; Aura di Protezione, inattiva da Incapacitato · pag. 111",
                    zona="regola:2024/paladin", voce="interazione",
                    copre=["carta:2024/classes/paladin.md#Aura di Interdizione / Aura of Warding (Giuramento degli Antichi, Paladino 7, pag. 116)",
                           "GET /characters/{char_id}/roll-options", "PATCH /characters/{char_id}/conditions"])
async def test_l_interdizione_di_un_altro_paladino_protegge_chi_ha_la_propria_spenta(client, test_session_factory):
    as_user(PLAYER_ID)
    compagno = await _oath(client, 7, "ancients")
    as_user(GM_ID)
    cid = await _oath(client, 7, "ancients")
    await _seduti(test_session_factory, (GM_ID, cid), (PLAYER_ID, compagno))
    as_user(GM_ID)
    chiave = "aura:warding_2024"
    assert chiave not in await _roll_keys(client, cid, "damage_taken", damage_type="necrotic")  # ha la sua
    assert (await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"stunned": True}})).status_code == 200
    assert chiave in await _roll_keys(client, cid, "damage_taken", damage_type="necrotic")
