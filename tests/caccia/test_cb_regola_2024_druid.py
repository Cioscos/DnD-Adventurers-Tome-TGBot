"""Controlli della zona regola:2024/druid."""
import asyncio

import pytest

from core.rules.forms import FormRules
from tests.integration.rules.test_2014_bard import _ability, _full, _states, _use
from tests.integration.rules.test_2014_druid import _activate, _beast, _form
from tests.integration.rules.test_2024_bard import _set_uses
from tests.integration.rules.test_2024_druid import WILD, _druid24, _shape
from tests.integration.rules.test_2024_druid_circles import _circle, _spend_slots


async def _caster(client, cid) -> dict:
    return next(c for c in (await _full(client, cid))["spellcasting"]["casters"] if c["class_name"] in ("druid", "Druido"))


async def _amuleto(client, cid) -> None:
    """Un oggetto indossato che dà +1 alla CD degli incantesimi."""
    r = await client.post(f"/characters/{cid}/items", json={"name": "Amuleto", "item_type": "accessory",
                                                           "item_metadata": {"bonuses": [{"target": "spell_dc", "value": 1}]}})
    assert r.status_code == 201, r.text
    amuleto = next(i["id"] for i in (await client.get(f"/characters/{cid}/items")).json() if i["name"] == "Amuleto")
    r = await client.patch(f"/characters/{cid}/items/{amuleto}", json={"is_equipped": True, "equipment_slot": "neck"})
    assert r.status_code == 200, r.text


async def _ferito(client, cid) -> None:
    assert (await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": 40})).status_code == 200
    assert (await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 5})).status_code == 200


# un lupo con le competenze del suo profilo: Furtività +4 e TS su Costituzione +6
LUPO = {**_beast(0.25), "abilities": {"str": 12, "dex": 15, "con": 12, "int": 3, "wis": 12, "cha": 6},
        "skills": {"stealth": 4}, "saves": {"con": 6}}


# ---------------------------------------------------------------------------
# Rossi
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-2311", fonte="2024 · Druido · Regole della Forma Selvatica (competenze della Bestia) · pag. 81", zona="regola:2024/druid",
                    voce="regola", copre=["carta:2024/classes/druid.md#Regole della Forma Selvatica / Rules While Shape-Shifted (Druido 2, pag. 81)",
                                          "POST /characters/{char_id}/skills/{skill_name}/roll",
                                          "POST /characters/{char_id}/saving_throws/{ability}/roll"])
async def test_in_forma_2024_valgono_i_bonus_della_bestia_se_piu_alti(client):
    cid = await _druid24(client, 4)  # Destrezza e Costituzione 10, nessuna competenza in Furtività né nel TS di Costituzione
    assert (await _activate(client, cid, await _form(client, cid, LUPO))).status_code == 200
    furtivita = (await client.post(f"/characters/{cid}/skills/stealth/roll", json={})).json()["bonus"]
    ts_cos = (await client.post(f"/characters/{cid}/saving_throws/constitution/roll", json={})).json()["bonus"]
    assert (furtivita, ts_cos) == (4, 6)  # i bonus del profilo della Bestia sono più alti di quelli del druido


@pytest.mark.caccia(id="CB-2312", fonte="2024 · Druido · Circolo delle Stelle · Calice · pag. 89", zona="regola:2024/druid", voce="regola",
                    copre=["carta:2024/classes/druid.md#Calice / Chalice (Circolo delle Stelle 3, pag. 89)",
                           "POST /characters/{char_id}/spells/{spell_id}/roll_healing"])
@pytest.mark.xfail(strict=True, reason="CB-2312: difforme dal manuale, confermato")
async def test_il_calice_cura_una_sola_creatura_per_incantesimo(client, dadi):
    cid = await _circle(client, "stars", 5, wisdom=16)
    assert (await _use(client, cid, "druid.starry_form", params={"constellation": "chalice"})).status_code == 200
    await _ferito(client, cid)
    cura = (await client.post(f"/characters/{cid}/spells", json={"name": "Cura Ferite", "level": 1, "srd_index": "cure-wounds"})).json()
    dadi(4, 4, 4, 4)  # 2d8 della cura, poi il d8 di ogni Calice
    r = await client.post(f"/characters/{cid}/spells/{cura['id']}/roll_healing",
                          json={"casting_level": 1, "options": ["druid.chalice", "druid.chalice_other"]})
    # il Calice cura il druido OPPURE un'altra creatura: le due opzioni insieme vanno rifiutate o ne vale una sola
    assert r.status_code in (409, 422) or not (r.json()["self_healed"] and r.json()["option_result"]["effects"]), r.text


@pytest.mark.caccia(id="CB-2313", fonte="2024 · Druido · Aiuto della Terra pag. 85, Ira del Mare pag. 87, Dono Oceanico pag. 88 (CD degli incantesimi)",
                    zona="regola:2024/druid", voce="regola",
                    copre=["carta:2024/classes/druid.md#Aiuto della Terra / Land's Aid (Circolo della Terra 3, pag. 85)",
                           "carta:2024/classes/druid.md#Ira del Mare / Wrath of the Sea (Circolo del Mare 3, pag. 87)",
                           "carta:2024/classes/druid.md#Dono Oceanico / Oceanic Gift (Circolo del Mare 14, pag. 88)",
                           "POST /characters/{char_id}/features/{feature_key}/use"])
@pytest.mark.parametrize("cerchio,livello,chiave,parametri,stato", [
    ("land", 3, "druid.lands_aid", {"mode": "self"}, "lands_aid"),
    ("sea", 3, "druid.wrath_of_the_sea", {}, "wrath_of_the_sea"),
    ("sea", 14, "druid.oceanic_gift", {"target": "ally"}, "oceanic_gift_ally")])
@pytest.mark.xfail(strict=True, reason="CB-2313: difforme dal manuale, confermato")
async def test_i_privilegi_di_circolo_usano_la_cd_degli_incantesimi_con_gli_oggetti(client, cerchio, livello, chiave, parametri, stato):
    cid = await _circle(client, cerchio, livello, wisdom=16)
    await _amuleto(client, cid)
    cd = (await _caster(client, cid))["save_dc"]
    assert cd == 8 + (2 if livello < 5 else 5) + 3 + 1  # competenza, Saggezza 16 e l'amuleto
    r = await _use(client, cid, chiave, params=parametri)
    assert r.status_code == 200, r.text
    assert next(s for s in await _states(client, cid) if s["key"] == stato)["data"]["dc"] == cd


@pytest.mark.caccia(id="CB-2314", fonte="2024 · Druido · Incantesimi (preparati solo di livelli per cui si hanno slot) · pag. 79", zona="regola:2024/druid",
                    voce="limiti", copre=["carta:2024/classes/druid.md#Incantesimi / Spellcasting (Druido 1, pag. 79)", "POST /characters/{char_id}/spells"])
@pytest.mark.parametrize("livello_druido,livello_incantesimo", [(1, 2), (2, 2), (4, 3), (16, 9)])
@pytest.mark.xfail(strict=True, reason="CB-2314: difforme dal manuale, confermato")
async def test_il_druido_2024_non_prepara_incantesimi_di_un_livello_senza_slot(client, livello_druido, livello_incantesimo):
    cid = await _druid24(client, livello_druido)  # il limite della tabella lascia posto fra i preparati
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Incantesimo alto", "level": livello_incantesimo, "is_prepared": True})
    preparati = [s for s in (await client.get(f"/characters/{cid}/spells")).json()
                 if s["is_prepared"] and s["level"] >= 1 and not s.get("always_prepared")]
    assert r.status_code in (400, 409, 422) and preparati == []


@pytest.mark.caccia(id="CB-2315", fonte="2024 · Druido · Circolo delle Stelle · Costellazioni Scintillanti (all'inizio di ogni turno) · pag. 89",
                    zona="regola:2024/druid", voce="limiti",
                    copre=["carta:2024/classes/druid.md#Costellazioni Scintillanti / Twinkling Constellations (Circolo delle Stelle 10, pag. 89)",
                           "POST /characters/{char_id}/features/{feature_key}/use"])
@pytest.mark.xfail(strict=True, reason="CB-2315: difforme dal manuale, confermato")
async def test_la_costellazione_non_si_cambia_nel_turno_in_cui_si_assume_la_forma_stellare(client):
    cid = await _circle(client, "stars", 10, wisdom=16)
    assert (await _use(client, cid, "druid.starry_form", params={"constellation": "archer"})).status_code == 200
    r = await _use(client, cid, "druid.twinkling_constellations", params={"constellation": "dragon"})
    assert r.status_code == 409  # il cambio è all'inizio di un turno successivo
    assert next(s for s in await _states(client, cid) if s["key"] == "starry_form")["data"]["constellation"] == "archer"


# ---------------------------------------------------------------------------
# Verdi
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-2316", fonte="2024 · Druido · Tabella di classe (colonna Forma Selvatica) e Forma Selvatica · pag. 79-80", zona="regola:2024/druid",
                    voce="limiti", copre=["carta:2024/classes/druid.md#Forma Selvatica / Wild Shape (Druido 2, pag. 80)", "POST /characters/{char_id}/rest"])
@pytest.mark.parametrize("livello,usi", [(2, 2), (5, 2), (6, 3), (16, 3), (17, 4), (20, 4)])
async def test_usi_di_forma_selvatica_un_riposo_breve_ne_rende_uno_il_lungo_tutti(client, livello, usi):
    cid = await _druid24(client, livello)
    assert (await _ability(client, cid, WILD))["max_uses"] == usi
    await _set_uses(client, cid, WILD, 0)
    assert (await client.post(f"/characters/{cid}/rest", json={"rest_type": "short"})).status_code == 200
    assert (await _ability(client, cid, WILD))["uses"] == 1
    assert (await client.post(f"/characters/{cid}/rest", json={"rest_type": "long", "confirm_early": True})).status_code == 200
    assert (await _ability(client, cid, WILD))["uses"] == usi


@pytest.mark.caccia(id="CB-2317", fonte="2024 · Druido · Forma Selvatica (Forme Bestiali) pag. 80, Regole della Forma Selvatica pag. 81, Forme del Circolo pag. 86",
                    zona="regola:2024/druid", voce="limiti",
                    copre=["carta:2024/classes/druid.md#Forma Selvatica / Wild Shape (Druido 2, pag. 80)",
                           "carta:2024/classes/druid.md#Regole della Forma Selvatica / Rules While Shape-Shifted (Druido 2, pag. 81)",
                           "carta:2024/classes/druid.md#Forme del Circolo / Circle Forms (Circolo della Luna 3, pag. 86)"])
@pytest.mark.parametrize("livello,luna,gs,volo,forme,ore,pf_temp", [
    (2, False, 0.25, False, 4, 1, 2), (3, False, 0.25, False, 4, 1, 3), (3, True, 1, False, 4, 1, 9), (4, False, 0.5, False, 6, 2, 4),
    (7, False, 0.5, False, 6, 3, 7), (8, False, 1, True, 8, 4, 8), (6, True, 2, False, 6, 3, 18), (20, False, 1, True, 8, 10, 20),
    (20, True, 6, True, 8, 10, 60)])
def test_limiti_della_forma_2024_per_livello_e_circolo(livello, luna, gs, volo, forme, ore, pf_temp):
    limiti = FormRules("2024", livello, "moon" if luna else None)
    assert (limiti.max_cr, limiti.fly, limiti.swim, limiti.known_forms) == (gs, volo, True, forme)
    assert (limiti.rounds, limiti.temp_hp, limiti.own_hp) == (ore * 600, pf_temp, False)


@pytest.mark.caccia(id="CB-2318", fonte="2024 · Druido · Regole della Forma Selvatica (PF temporanei pari al livello da druido) pag. 81 e Multiclasse: Druido pag. 44",
                    zona="regola:2024/druid", voce="interazione",
                    copre=["carta:2024/classes/druid.md#Regole della Forma Selvatica / Rules While Shape-Shifted (Druido 2, pag. 81)",
                           "carta:2024/classes/druid.md#Multiclasse: Druido / Multiclassing: Druid (Regole multiclasse, pag. 44)",
                           "POST /characters/{char_id}/classes", "POST /characters/{char_id}/companions/{comp_id}/activate"])
async def test_in_multiclasse_pf_temporanei_e_durata_usano_il_livello_da_druido(client):
    r = await client.post("/characters", json={"name": "Mista", "initial_class": {"class_name": "fighter", "level": 5, "subclass": None}})
    cid = r.json()["id"]
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    assert (await client.patch(f"/characters/{cid}/ability_scores/wisdom", json={"value": 14})).status_code == 200
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "druid", "level": 2})
    assert r.status_code == 201, r.text
    assert (await _activate(client, cid, await _form(client, cid, _beast(0.25)))).status_code == 200
    full = await _full(client, cid)
    forma = next(s for s in full["active_states"] if s["key"] == "wild_shape")
    assert (full["temp_hp"], forma["rounds_left"]) == (2, 600)  # druido 2: 2 PF temporanei e un'ora, non il livello 7


@pytest.mark.caccia(id="CB-2319", fonte="2024 · Druido · Incantesimi Bestiali pag. 81 (ogni incantesimo) e 2014 · Druido · Incantesimi Bestiali pag. 67 (solo da druido)",
                    zona="regola:2024/druid", voce="edizioni",
                    copre=["carta:2024/classes/druid.md#Incantesimi Bestiali / Beast Spells (Druido 18, pag. 81)",
                           "carta:2014/classes/druid.md#Incantesimi Bestiali / Beast Spells (Druido 18, pag. 67)",
                           "GET /characters/{char_id}/spells/{spell_id}/cast-check"])
async def test_incantesimi_bestiali_2024_valgono_anche_per_un_altra_classe(client):
    cid = await _druid24(client, 18)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "wizard", "level": 2, "hit_die": 6})
    assert r.status_code == 201, r.text
    mago = next(c["id"] for c in (await _full(client, cid))["classes"] if c["class_name"] in ("wizard", "Mago"))
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Dardo incantato", "level": 1, "components": "V, S", "class_id": mago})
    assert r.status_code == 201, r.text
    await _shape(client, cid, 1, fly=30)
    assert (await client.get(f"/characters/{cid}/spells/{r.json()['id']}/cast-check")).json() == []


@pytest.mark.caccia(id="CB-2320", fonte="2024 · Druido · Rigenerazione Selvatica (uso in cambio di uno slot di 1° livello, poi riposo lungo) · pag. 81",
                    zona="regola:2024/druid", voce="ripetizione",
                    copre=["carta:2024/classes/druid.md#Rigenerazione Selvatica / Wild Resurgence (Druido 5, pag. 81)",
                           "POST /characters/{char_id}/features/{feature_key}/use"])
async def test_due_richieste_insieme_creano_un_solo_slot_dalla_rigenerazione(client):
    cid = await _druid24(client, 5)
    rs = await asyncio.gather(*[_use(client, cid, "druid.wild_resurgence_slot") for _ in range(2)])
    assert sorted(r.status_code for r in rs) == [200, 409]
    primo = next(s for s in (await _full(client, cid))["spell_slots"] if s["level"] == 1)
    assert ((await _ability(client, cid, WILD))["uses"], primo["total"]) == (1, 5)


@pytest.mark.caccia(id="CB-2321", fonte="2024 · Druido · Circolo della Luna · Forme del Circolo (CA 13 + Saggezza se più alta) · pag. 86", zona="regola:2024/druid",
                    voce="regola", copre=["carta:2024/classes/druid.md#Forme del Circolo / Circle Forms (Circolo della Luna 3, pag. 86)",
                                          "POST /characters/{char_id}/companions/{comp_id}/activate", "GET /characters/{char_id}"])
@pytest.mark.parametrize("luna,saggezza,ca", [(True, 18, 17), (True, 10, 13), (False, 18, 12)])
async def test_la_ca_della_forma_della_luna_e_13_piu_saggezza_se_piu_alta(client, luna, saggezza, ca):
    cid = await (_circle(client, "moon", 3, wisdom=saggezza) if luna else _druid24(client, 3, wisdom=saggezza))
    assert (await _activate(client, cid, await _form(client, cid, _beast(0.25)))).status_code == 200  # CA della bestia 12
    assert (await _full(client, cid))["active_form"]["armor_class"] == ca


@pytest.mark.caccia(id="CB-2322", fonte="2024 · Druido · Circolo della Terra · Recupero Naturale (metà livello per eccesso, nessuno di 6° o più) · pag. 85",
                    zona="regola:2024/druid", voce="limiti",
                    copre=["carta:2024/classes/druid.md#Recupero Naturale / Natural Recovery (Circolo della Terra 6, pag. 85)", "POST /characters/{char_id}/rest"])
@pytest.mark.parametrize("livello,slot,stato", [(7, {"4": 1, "1": 1}, 422), (7, {"3": 1, "1": 1}, 200), (20, {"6": 1}, 422),
                                                (20, {"5": 1, "4": 1, "1": 1}, 200)])
async def test_recupero_naturale_2024_meta_livello_per_eccesso_e_niente_sesto(client, livello, slot, stato):
    cid = await _circle(client, "land", livello)
    await _spend_slots(client, cid)
    r = await client.post(f"/characters/{cid}/rest", json={"rest_type": "short", "natural_recovery": slot})
    assert r.status_code == stato, r.text


@pytest.mark.caccia(id="CB-2323", fonte="2024 · Druido · Circolo delle Stelle · Drago (d20 di 9 o meno vale 10) · pag. 89", zona="regola:2024/druid",
                    voce="regola", copre=["carta:2024/classes/druid.md#Drago / Dragon (Circolo delle Stelle 3, pag. 89)",
                                          "POST /characters/{char_id}/skills/{skill_name}/roll", "POST /characters/{char_id}/concentration/save",
                                          "POST /characters/{char_id}/saving_throws/{ability}/roll"])
@pytest.mark.parametrize("percorso,corpo,dado", [
    ("skills/perception/roll", {"die": 5}, 10), ("skills/arcana/roll", {"die": 9}, 10), ("concentration/save", {"damage": 10, "dice": [5]}, 10),
    ("skills/athletics/roll", {"die": 5}, 5), ("saving_throws/wisdom/roll", {"die": 5}, 5)])
async def test_il_drago_porta_a_10_le_prove_di_intelligenza_e_saggezza_e_la_concentrazione(client, percorso, corpo, dado):
    cid = await _circle(client, "stars", 3, wisdom=16)
    assert (await _use(client, cid, "druid.starry_form", params={"constellation": "dragon"})).status_code == 200
    r = await client.post(f"/characters/{cid}/{percorso}", json=corpo)
    assert r.status_code == 200, r.text
    assert r.json()["die"] == dado
