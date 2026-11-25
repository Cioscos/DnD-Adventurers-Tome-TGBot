"""Controlli scritti nella correzione del gruppo fe-specie-progressione (dubbi «Q-…» risolti come difetti)."""
from tests.caccia.test_cb_regola_2024_razze import LUCK, _pg

import pytest


@pytest.mark.caccia(id="CB-4551", fonte="2024 · Specie · Halfling · Fortuna · pag. 193; Regole di gioco · Vantaggio e Svantaggio, rilanci · pag. 12-13",
                    zona="regola:2024/razze", voce="interazione",
                    copre=["carta:2024/races.md#Halfling / Halfling (pag. 193)",
                           "carta:2024/general.md#Vantaggio e Svantaggio / Advantage/Disadvantage (pag. 12-13)",
                           "GET /characters/{char_id}/roll-options", "POST /characters/{char_id}/saving_throws/{ability}/roll",
                           "POST /characters/{char_id}/last-roll/options"])
async def test_fortuna_con_vantaggio_si_offre_se_uno_dei_due_d20_fa_1(client):
    cid = await _pg(client, "2024_halfling", {})
    r = await client.post(f"/characters/{cid}/saving_throws/wisdom/roll", json={"mode": "advantage", "dice": [1, 15]})
    assert r.status_code == 200, r.text
    assert r.json()["die"] == 15
    # Con Vantaggio un ritiro tocca uno solo dei due dadi, a scelta (pag. 12-13): l'1 si ritira anche se vale l'altro
    offerte = (await client.get(f"/characters/{cid}/roll-options", params={"roll": "save", "ability": "wisdom"})).json()
    assert LUCK in {o["key"] for o in offerte}, offerte
    r = await client.post(f"/characters/{cid}/last-roll/options", json={"options": [LUCK], "dice": [18]})
    assert r.status_code == 200, r.text
    assert r.json()["die"] == 18


@pytest.mark.caccia(id="CB-4556", fonte="2014 · Razze · Nano, Addestramento da Combattimento Nanico · pag. 28; invariante: un personaggio senza classe "
                    "è competente con tutte le armi, prima e dopo il riavvio (proficiencies.is_weapon_proficient, semina all'avvio)",
                    zona="regola:2014/razze", voce="persistenza",
                    copre=["carta:2014/races.md#Nano / Dwarf - tratti base (pag. 28)", "POST /characters", "POST /characters/{char_id}/items"])
async def test_nano_senza_classe_resta_competente_con_le_armi_da_guerra(client):
    r = await client.post("/characters", json={"name": "Gimli", "species": {
        "name": "Nano delle colline", "weapons": ["battleaxe", "handaxe", "light_hammer", "warhammer"], "resistances": ["poison"]}})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    r = await client.post(f"/characters/{cid}/items", json={"name": "Spada lunga", "item_type": "weapon", "item_metadata": {
        "damage_dice": "1d8", "weapon_type": "melee", "properties": ["versatile"], "weapon_category": "martial"}})
    assert r.status_code == 201, r.text
    spada = next(i for i in (await client.get(f"/characters/{cid}")).json()["items"] if i["name"] == "Spada lunga")
    assert spada["attack_preview"]["to_hit"] == 2  # FOR 10 + competenza 2, come dopo la semina del riavvio
    # la classe presa dopo decide le competenze: il Mago non eredita le armi da guerra
    assert (await client.post(f"/characters/{cid}/classes", json={"class_name": "wizard", "level": 1})).status_code in (200, 201)
    spada = next(i for i in (await client.get(f"/characters/{cid}")).json()["items"] if i["name"] == "Spada lunga")
    assert spada["attack_preview"]["to_hit"] == 0
