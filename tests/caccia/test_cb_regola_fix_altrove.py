"""Controlli delle revisioni delle correzioni regole 2026-11-24: lo stesso errore trovato altrove."""
import pytest

from tests.caccia.test_cb_regola_2014_incantesimi_g_l import _pg, _scheda
from tests.caccia.test_cb_regola_2014_razze import _specie
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


@pytest.mark.caccia(id="CB-4709", fonte="2014 · Condizioni · Privo di Sensi (cade prono) · pag. 292; 2024 · Unconscious · pag. 377", zona="regola:2014/generali",
                    voce="interazione", copre=["carta:2014/general.md#Privo di Sensi / Unconscious (pag. 292)",
                                               "carta:2024/general.md#Unconscious [Condition] (Privo di Sensi) (pag. 377)",
                                               "POST /sessions/{session_id}/encounter/combatants/{combatant_id}/conditions",
                                               "PATCH /sessions/{session_id}/encounter/combatants/{combatant_id}"])
async def test_un_mostro_privo_di_sensi_cade_prono(client, test_session_factory):
    sid, incontro = await setup_full_encounter(client, test_session_factory)
    uno, due = [c for c in incontro["combatants"] if c["kind"] == "monster"]
    base = f"/sessions/{sid}/encounter/combatants"
    r = await client.post(f"{base}/{uno['id']}/conditions", json={"slug": "unconscious", "value": True})
    assert r.status_code == 200, r.text
    r = await client.patch(f"{base}/{due['id']}", json={"conditions": {"unconscious": True}})
    assert r.status_code == 200, r.text
    stato = {c["id"]: c["conditions"] for c in r.json()["combatants"]}
    assert all(stato[m["id"]].get("prone") for m in (uno, due)), stato
    # risvegliandosi resta prono, e il master può rialzarlo
    r = await client.patch(f"{base}/{due['id']}", json={"conditions": {"unconscious": True, "prone": False}})
    assert next(c for c in r.json()["combatants"] if c["id"] == due["id"])["conditions"]["prone"] is False


@pytest.mark.caccia(id="CB-4710", fonte="2024 · Glossario · Nascondersi (il tiro per colpire fa finire l'Invisibilità) · pag. 368; Druido · Arciere · pag. 89",
                    zona="regola:2024/druid", voce="interazione",
                    copre=["carta:2024/general.md#Hide [Action] (Nascondersi) (pag. 368)", "carta:2024/classes/druid.md#Arciere / Archer (Circolo delle Stelle 3, pag. 89)",
                           "POST /characters/{char_id}/features/{feature_key}/use"])
async def test_l_attacco_dell_arciere_fa_finire_il_nascondiglio(client):
    cid = await _circle(client, "stars", 3, wisdom=16)
    assert (await _use(client, cid, "druid.starry_form", params={"constellation": "archer"})).status_code == 200
    assert (await client.post(f"/characters/{cid}/turn/new")).status_code == 200
    assert (await client.post(f"/characters/{cid}/skills/stealth/roll", json={"dice": [20]})).status_code == 200
    r = await client.post(f"/characters/{cid}/hide")
    assert r.status_code == 200 and r.json()["conditions"].get("invisible") is True, r.text
    r = await _use(client, cid, "druid.archer")
    assert r.status_code == 200, r.text
    j = await _scheda(client, cid)
    assert (bool(j["conditions"].get("invisible")), j["hiding_dc"]) == (False, None)


@pytest.mark.caccia(id="CB-4711", fonte="2024 · Glossario · Incapacitato (niente azioni) · pag. 369; Furfante · Usare Dispositivi Magici · pag. 137",
                    zona="regola:2024/rogue", voce="interazione",
                    copre=["carta:2024/general.md#Incapacitated [Condition] (Incapacitato) (pag. 369)",
                           "carta:2024/classes/rogue.md#Usare Dispositivi Magici / Use Magic Device (Furfante 13, pag. 137)",
                           "POST /characters/{char_id}/items/{item_id}/scroll"])
async def test_chi_e_incapacitato_non_lancia_da_una_pergamena(client):
    cid = await _ladro(client, 13, "thief")
    r = await client.post(f"/characters/{cid}/items", json={
        "name": "Pergamena", "item_type": "consumable", "quantity": 1, "item_metadata": {"subtype": "scroll"}})
    iid = max(i["id"] for i in r.json()["items"])
    assert (await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"stunned": True}})).status_code == 200
    r = await client.post(f"/characters/{cid}/items/{iid}/scroll", json={"spell_level": 1})
    assert (r.status_code, r.json()["detail"].get("code")) == (409, "incapacitated"), r.text
    assert next(i for i in (await _scheda(client, cid))["items"] if i["id"] == iid)["quantity"] == 1


@pytest.mark.caccia(id="CB-4712", fonte="decisione D-005 (tests/caccia/decisioni.md): ciò che dava la vecchia specie se ne va col cambio; "
                    "2014 · Tiefling pag. 43, Nano pag. 28, Elfo pag. 20, Gnomo delle Rocce pag. 37",
                    zona="regola:2024/razze", voce="edizioni",
                    copre=["carta:2014/races.md#Tiefling / Tiefling (pag. 43)", "carta:2014/races.md#Nano / Dwarf - tratti base (pag. 28)",
                           "carta:2014/races.md#Gnomo delle Rocce / Rock Gnome (pag. 37)", "PUT /characters/{char_id}/species",
                           "POST /characters/{char_id}/species/preview"])
async def test_la_prima_specie_2024_toglie_cio_che_dava_la_razza_2014(client):
    async def passa(specie, abilita=None, classe="wizard", chiave="2024_orc", opzioni=None) -> tuple[list, dict]:
        r = await client.post("/characters", json={
            "name": "R", "rules_edition": "2014", "species": specie, "skills": {a: True for a in abilita or ()},
            "initial_class": {"class_name": classe, "level": 1}})
        assert r.status_code == 201, r.text
        cid = r.json()["id"]
        assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
        corpo = {"key": chiave, "options": opzioni or {}}
        cambi = (await client.post(f"/characters/{cid}/species/preview", json=corpo)).json()["changes"]
        assert (await client.put(f"/characters/{cid}/species", json=corpo)).status_code == 200
        return cambi, await _scheda(client, cid)

    cambi, tiefling = await passa(_specie("tiefling"))
    assert "fire" not in tiefling["damage_modifiers"].get("resistances", []) and "resistance_removed:fire" in cambi
    cambi, nano = await passa(_specie("dwarf", "hill-dwarf"))
    assert not {"Ascia da battaglia", "Martello da guerra"} & set(nano["general_proficiencies"]["weapons"])
    assert "weapon_removed:Ascia da battaglia" in cambi and "poison" not in nano["damage_modifiers"].get("resistances", [])
    cambi, gnomo = await passa(_specie("gnome", "rock-gnome"))
    assert "tinkers_tools" not in gnomo["tool_proficiencies"] and "tool_removed:tinkers_tools" in cambi
    mezzorco = {**_specie("half-orc"), "skills": ["intimidation"]}
    cambi, orco = await passa(mezzorco, ["intimidation", "insight"])
    assert "intimidation" not in orco["skills"] and orco["skills"]["insight"] is True and "skill_removed:intimidation" in cambi
    # ciò che dà anche la classe resta (Ladro 2014: spada lunga e corta), e l'abilità che la nuova specie sceglie pure
    elfo = {**_specie("elf", "high-elf"), "skills": ["perception"]}
    cambi, elfo24 = await passa(elfo, ["perception"], "rogue", "2024_elf", {"lineage": "high", "spell_ability": "intelligence", "skill": "perception"})
    armi = set(elfo24["general_proficiencies"]["weapons"])
    assert "Spada lunga" in armi and "Arco lungo" not in armi
    assert elfo24["skills"]["perception"] is True and "skill_removed:perception" not in cambi
