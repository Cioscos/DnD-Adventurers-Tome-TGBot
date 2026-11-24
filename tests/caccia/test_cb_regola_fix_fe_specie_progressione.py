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
