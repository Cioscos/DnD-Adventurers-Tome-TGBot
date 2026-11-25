"""Controlli della zona regola:2014/druid."""
from types import SimpleNamespace

import pytest

from core.rules.spellcasting import known_limits, slots_for
from tests.integration.rules.test_2014_bard import _ability, _full
from tests.integration.rules.test_2014_druid import _activate, _beast, _druid, _form


async def _nuovo_turno(client, cid) -> None:
    assert (await client.post(f"/characters/{cid}/turn/new")).status_code == 200


async def _caster(client, cid) -> dict:
    return next(c for c in (await _full(client, cid))["spellcasting"]["casters"] if c["class_name"] in ("druid", "Druido"))


# ---------------------------------------------------------------------------
# Rossi
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-1711", fonte="2014 · Druido · Forma Selvatica (PF e Dadi Vita della bestia) · pag. 66", zona="regola:2014/druid",
                    voce="regola", copre=["carta:2014/classes/druid.md#Forma Selvatica / Wild Shape (Druido 2, pag. 66)",
                                          "POST /characters/{char_id}/hit_dice/spend"])
@pytest.mark.xfail(strict=True, reason="CB-1711: difforme dal manuale, confermato")
async def test_in_forma_selvatica_i_dadi_vita_del_druido_non_curano_la_forma_normale(client):
    cid = await _druid(client, 4, "land")  # 23 PF, 4 Dadi Vita d8
    assert (await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 10})).status_code == 200
    forma = await _form(client, cid, _beast(0.25), hp=10)
    assert (await _activate(client, cid, forma)).status_code == 200
    classe = (await _full(client, cid))["classes"][0]["id"]
    await client.post(f"/characters/{cid}/hit_dice/spend", json={"class_id": classe, "count": 1, "rolls": [6]})
    dopo = await _full(client, cid)
    # in forma i PF e i Dadi Vita sono quelli della bestia: quelli del druido restano com'erano fino al ritorno
    assert dopo["current_hit_points"] == 10
    assert dopo["classes"][0]["hit_dice_used"] == 0


@pytest.mark.caccia(id="CB-1712", fonte="2014 · Druido · Circolo della Terra · Rifugio della Natura · pag. 69", zona="regola:2014/druid",
                    voce="regola", copre=["carta:2014/classes/druid.md#Rifugio della Natura / Nature's Sanctuary (Circolo della Terra 14, pag. 69)",
                                          "POST /characters/{char_id}/features/{feature_key}/use",
                                          "GET /characters/{char_id}/target-effects/{effect_key}"])
async def test_il_rifugio_della_natura_usa_la_cd_degli_incantesimi_del_druido(client):
    cid = await _druid(client, 14, "land", wisdom=16)
    r = await client.post(f"/characters/{cid}/items", json={"name": "Amuleto", "item_type": "accessory",
                                                           "item_metadata": {"bonuses": [{"target": "spell_dc", "value": 1}]}})
    assert r.status_code == 201, r.text
    amuleto = next(i["id"] for i in (await client.get(f"/characters/{cid}/items")).json() if i["name"] == "Amuleto")
    r = await client.patch(f"/characters/{cid}/items/{amuleto}", json={"is_equipped": True, "equipment_slot": "neck"})
    assert r.status_code == 200, r.text
    cd_incantesimi = (await _caster(client, cid))["save_dc"]
    assert cd_incantesimi == 8 + 5 + 3 + 1  # competenza, Saggezza 16 e l'amuleto
    assert (await client.post(f"/characters/{cid}/features/druid.natures_sanctuary/use", json={})).status_code == 200
    effetto =(await client.get(f"/characters/{cid}/target-effects/druid.natures_sanctuary")).json()["result"]
    assert effetto["save_dc"] == cd_incantesimi


@pytest.mark.caccia(id="CB-1713", fonte="2014 · Druido · Incantesimi (preparati solo di livelli per cui si hanno slot) · pag. 66",
                    zona="regola:2014/druid", voce="limiti",
                    copre=["carta:2014/classes/druid.md#Incantesimi / Spellcasting (Druido 1, pag. 66)", "POST /characters/{char_id}/spells"])
@pytest.mark.parametrize("livello_druido, livello_incantesimo", [(1, 2), (2, 2), (4, 3), (16, 9)])
@pytest.mark.xfail(strict=True, reason="CB-1713: difforme dal manuale, confermato")
async def test_il_druido_non_prepara_incantesimi_di_un_livello_senza_slot(client, livello_druido, livello_incantesimo):
    cid = await _druid(client, livello_druido, wisdom=18)  # posto libero fra i preparati
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Incantesimo alto", "level": livello_incantesimo,
                                                              "is_prepared": True})
    preparati = [s for s in (await client.get(f"/characters/{cid}/spells")).json() if s["is_prepared"]]
    assert r.status_code in (400, 409, 422) and preparati == []


@pytest.mark.caccia(id="CB-1714", fonte="2014 · Druido · Incantesimi Bestiali (solo incantesimi da druido) · pag. 67", zona="regola:2014/druid",
                    voce="interazione", copre=["carta:2014/classes/druid.md#Incantesimi Bestiali / Beast Spells (Druido 18, pag. 67)",
                                               "GET /characters/{char_id}/spells/{spell_id}/cast-check"])
@pytest.mark.xfail(strict=True, reason="CB-1714: difforme dal manuale, confermato")
async def test_incantesimi_bestiali_non_sbloccano_gli_incantesimi_di_un_altra_classe(client):
    cid = await _druid(client, 18, "land")
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "wizard", "level": 2, "hit_die": 6})
    assert r.status_code == 201, r.text
    mago = next(c["id"] for c in (await _full(client, cid))["classes"] if c["class_name"] in ("wizard", "Mago"))
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Dardo incantato", "level": 1, "components": "V, S",
                                                              "class_id": mago})
    assert r.status_code == 201, r.text
    incantesimo = r.json()["id"]
    assert (await _activate(client, cid, await _form(client, cid, _beast(1)))).status_code == 200
    avvisi = (await client.get(f"/characters/{cid}/spells/{incantesimo}/cast-check")).json()
    assert "wild_shape" in avvisi  # in forma bestiale si lanciano solo incantesimi da druido


@pytest.mark.caccia(id="CB-1715", fonte="2014 · Druido · Circolo della Luna · Forma Selvatica da Combattimento (azione bonus) · pag. 69",
                    zona="regola:2014/druid", voce="regola",
                    copre=["carta:2014/classes/druid.md#Forma Selvatica da Combattimento / Combat Wild Shape (Circolo della Luna 2, pag. 69)",
                           "GET /characters/{char_id}"])
async def test_la_forma_selvatica_della_luna_e_una_azione_bonus_sulla_scheda(client):
    luna = await _ability(client, await _druid(client, 2, "moon"), "druid.wild_shape")
    terra = await _ability(client, await _druid(client, 2, "land"), "druid.wild_shape")
    assert terra["action_type"] == "action"
    assert luna["action_type"] == "bonus_action"  # il Turno la mette fra le azioni bonus


@pytest.mark.caccia(id="CB-1716", fonte="2014 · Druido · Circolo della Terra · Trucchetto Bonus · pag. 68", zona="regola:2014/druid",
                    voce="interazione", copre=["carta:2014/classes/druid.md#Trucchetto Bonus / Bonus Cantrip (Circolo della Terra 2, pag. 68)",
                                               "PATCH /characters/{char_id}/classes/{class_id}"])
async def test_passando_alla_luna_il_trucchetto_bonus_della_terra_non_resta_fuori_dal_limite(client):
    cid = await _druid(client, 2, "land")
    scelta = next(c for c in (await _full(client, cid))["pending_choices"] if c.get("group") == "bonus_cantrip")
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Randello incantato", "level": 0, "pick_id": scelta["id"],
                                                              "srd_index": "shillelagh"})
    assert r.status_code == 201, r.text
    classe = (await _full(client, cid))["classes"][0]["id"]
    r = await client.patch(f"/characters/{cid}/classes/{classe}", json={"subclass": "Circolo della Luna"})
    assert r.status_code == 200, r.text
    trucchetti = [s for s in (await client.get(f"/characters/{cid}/spells")).json() if s["level"] == 0]
    limiti = (await _full(client, cid))["spellcasting"]["limits"][0]
    # il trucchetto in più è della Terra: alla Luna resta solo la tabella (2 al 2° livello), niente fuori dal limite
    assert len(trucchetti) == limiti["cantrips_count"]


# ---------------------------------------------------------------------------
# Verdi
# ---------------------------------------------------------------------------

# livello -> (trucchetti, slot dal 1° al 9°), dalla tabella di classe del Druido (pag. 65)
TABELLA = {
    1: (2, (2,)), 2: (2, (3,)), 3: (2, (4, 2)), 4: (3, (4, 3)), 5: (3, (4, 3, 2)), 6: (3, (4, 3, 3)), 7: (3, (4, 3, 3, 1)),
    8: (3, (4, 3, 3, 2)), 9: (3, (4, 3, 3, 3, 1)), 10: (4, (4, 3, 3, 3, 2)), 11: (4, (4, 3, 3, 3, 2, 1)),
    12: (4, (4, 3, 3, 3, 2, 1)), 13: (4, (4, 3, 3, 3, 2, 1, 1)), 14: (4, (4, 3, 3, 3, 2, 1, 1)),
    15: (4, (4, 3, 3, 3, 2, 1, 1, 1)), 16: (4, (4, 3, 3, 3, 2, 1, 1, 1)), 17: (4, (4, 3, 3, 3, 2, 1, 1, 1, 1)),
    18: (4, (4, 3, 3, 3, 3, 1, 1, 1, 1)), 19: (4, (4, 3, 3, 3, 3, 2, 1, 1, 1)), 20: (4, (4, 3, 3, 3, 3, 2, 2, 1, 1)),
}


@pytest.mark.caccia(id="CB-1717", fonte="2014 · Druido · Tabella di classe (trucchetti e slot) · pag. 65", zona="regola:2014/druid",
                    voce="limiti", copre=["carta:2014/classes/druid.md#Incantesimi / Spellcasting (Druido 1, pag. 66)"])
@pytest.mark.parametrize("livello", list(range(1, 21)))
def test_trucchetti_e_slot_del_druido_seguono_la_tabella(livello):
    trucchetti, slot = TABELLA[livello]
    riga = SimpleNamespace(class_name="druid", level=livello, subclass_key=None, spellcasting_ability="wisdom")
    assert known_limits("2014", "druid", livello).cantrips == trucchetti
    assert slots_for("2014", [riga]).regular == {i + 1: n for i, n in enumerate(slot)}


@pytest.mark.caccia(id="CB-1718", fonte="2014 · Druido · Incantesimi (preparati: Saggezza + livello, minimo 1) · pag. 66",
                    zona="regola:2014/druid", voce="limiti",
                    copre=["carta:2014/classes/druid.md#Incantesimi / Spellcasting (Druido 1, pag. 66)", "GET /characters/{char_id}"])
@pytest.mark.parametrize("livello, saggezza, attesi", [(1, 8, 1), (3, 6, 1), (7, 14, 9), (20, 20, 25)])
async def test_incantesimi_preparati_saggezza_piu_livello_minimo_uno(client, livello, saggezza, attesi):
    cid = await _druid(client, livello, wisdom=saggezza)
    assert (await _full(client, cid))["spellcasting"]["prepared_cap"] == attesi


@pytest.mark.caccia(id="CB-1719", fonte="2014 · Druido · Incantesimi (CD e attacco con la Saggezza) · pag. 66", zona="regola:2014/druid",
                    voce="regola", copre=["carta:2014/classes/druid.md#Incantesimi / Spellcasting (Druido 1, pag. 66)", "GET /characters/{char_id}"])
@pytest.mark.parametrize("livello, saggezza, cd, attacco", [(1, 16, 13, 5), (9, 18, 16, 8), (17, 20, 19, 11)])
async def test_cd_e_attacco_degli_incantesimi_usano_la_saggezza(client, livello, saggezza, cd, attacco):
    cid = await _druid(client, livello, wisdom=saggezza, intelligence=20, charisma=20)
    c = await _caster(client, cid)
    assert (c["ability"], c["save_dc"], c["attack_bonus"]) == ("wisdom", cd, attacco)


@pytest.mark.caccia(id="CB-1720", fonte="2014 · Druido · Circolo della Terra · Recupero Naturale · pag. 68", zona="regola:2014/druid",
                    voce="limiti", copre=["carta:2014/classes/druid.md#Recupero Naturale / Natural Recovery (Circolo della Terra 2, pag. 68)",
                                          "POST /characters/{char_id}/rest"])
async def test_recupero_naturale_meta_livello_per_eccesso_al_livello_dispari(client):
    cid = await _druid(client, 7, "land")  # 4 livelli di slot
    for s in (await _full(client, cid))["spell_slots"]:
        await client.patch(f"/characters/{cid}/spell_slots/{s['id']}", json={"used": s["total"]})
    troppo = await client.post(f"/characters/{cid}/rest", json={"rest_type": "short", "natural_recovery": {"4": 1, "1": 1}})
    assert troppo.status_code == 422
    r = await client.post(f"/characters/{cid}/rest", json={"rest_type": "short", "natural_recovery": {"3": 1, "1": 1}})
    assert r.status_code == 200, r.text
    assert {s["level"]: s["used"] for s in r.json()["spell_slots"]} == {1: 3, 2: 3, 3: 2, 4: 1}


@pytest.mark.caccia(id="CB-1721", fonte="2014 · Druido · Circolo della Luna · Forma Selvatica da Combattimento (1d8 per livello dello slot) · pag. 69",
                    zona="regola:2014/druid", voce="regola",
                    copre=["carta:2014/classes/druid.md#Forma Selvatica da Combattimento / Combat Wild Shape (Circolo della Luna 2, pag. 69)",
                           "POST /characters/{char_id}/companions/{comp_id}/wild-heal"])
async def test_la_cura_in_forma_tira_un_d8_per_livello_dello_slot(client, dadi):
    cid = await _druid(client, 6, "moon")
    forma = await _form(client, cid, _beast(1), hp=40)
    assert (await _activate(client, cid, forma)).status_code == 200
    await _nuovo_turno(client, cid)
    await client.patch(f"/characters/{cid}/companions/{forma}/hp", json={"op": "damage", "value": 30})
    dadi(2, 5, 8)
    r = await client.post(f"/characters/{cid}/companions/{forma}/wild-heal", json={"slot_level": 3})
    assert r.status_code == 200, r.text
    assert (r.json()["rolls"], r.json()["healed"], r.json()["companion"]["current_hp"]) == ([2, 5, 8], 15, 25)


@pytest.mark.caccia(id="CB-1722", fonte="2014 · Druido · Incantesimi · pag. 66 (Saggezza + livello) e 2024 · Druido · Incantesimi · pag. 79 (tabella)",
                    zona="regola:2014/druid", voce="edizioni",
                    copre=["carta:2014/classes/druid.md#Incantesimi / Spellcasting (Druido 1, pag. 66)",
                           "carta:2024/classes/druid.md#Incantesimi / Spellcasting (Druido 1, pag. 79)", "PATCH /characters/{char_id}"])
async def test_i_preparati_del_druido_seguono_l_edizione(client):
    cid = await _druid(client, 5, wisdom=16)
    assert (await _full(client, cid))["spellcasting"]["prepared_cap"] == 3 + 5  # 2014: Saggezza + livello
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    assert (await _full(client, cid))["spellcasting"]["prepared_cap"] == 9  # 2024: colonna della tabella al 5° livello
