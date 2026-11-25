"""Controlli delle revisioni delle correzioni regole 2026-11-24: lo stesso errore trovato altrove."""
import pytest

from tests.caccia.test_cb_regola_2014_incantesimi_g_l import _pg
from tests.integration.rules.test_2014_bard import _roll_keys, _states, _use
from tests.integration.rules.test_2014_wizard import _wizard
from tests.integration.rules.test_2014_wizard_illusion_evocation import _illusion
from tests.integration.rules.test_2024_cleric_domains import _dom, _spell_rows
from tests.integration.test_magic_items import _item
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
