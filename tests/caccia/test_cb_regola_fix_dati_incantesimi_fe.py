"""Controlli scritti dalla correzione del gruppo dati-incantesimi-fe (dubbi risolti come difetti)."""
import pytest

from core.rules.catalog.granted_spells import granted_spell
from tests.caccia.test_cb_regola_2014_incantesimi_a_c import _dal_catalogo as _dal_catalogo_2014, _pg as _pg_2014
from tests.caccia.test_cb_regola_2024_incantesimi_m_r import _dal_catalogo, _pg


@pytest.mark.caccia(id="CB-4031", fonte="2024 · Incantesimi · Favore divino, Fonte di luce lunare, Fondersi nella Pietra, Desiderio (nessun danno al lancio) · pag. 265, 277, 296-297, 341",
                    zona="regola:2024/incantesimi-D-F", voce="regola",
                    copre=["carta:2024/spells.md#Favore divino", "carta:2024/spells.md#Fonte di luce lunare",
                           "carta:2024/spells.md#Fondersi nella Pietra", "carta:2024/spells.md#Desiderio", "GET /characters/{char_id}/spells"])
@pytest.mark.parametrize("indice", ["divine-favor", "fount-of-moonlight", "meld-into-stone", "wish"])
async def test_incantesimi_2024_senza_danno_al_lancio_non_aprono_il_tiro_di_danno(client, indice):
    cid = await _pg(client)
    await _dal_catalogo(client, cid, indice)
    r = await client.get(f"/characters/{cid}/spells")
    assert r.status_code == 200, r.text
    voce = next(s for s in r.json() if s["srd_index"] == indice)
    # rollsDamageOnCast: dadi dell'incantesimo e nessun danno «al colpo» -> il lancio apre il tiro di danno
    assert not (voce["damage_dice"] and not (voce["effect"] or {}).get("hit_damage"))


@pytest.mark.caccia(id="CB-4032", fonte="2024 · Incantesimi · Arma elementale · pag. 268", zona="regola:2024/incantesimi-A-C", voce="regola",
                    copre=["carta:2024/spells.md#Arma elementale", "POST /characters/{char_id}/spells", "GET /characters/{char_id}/spells"])
async def test_arma_elementale_2024_dal_catalogo_non_tira_danni_al_lancio(client):
    cid = await _pg(client)
    await _dal_catalogo(client, cid, "elemental-weapon")
    r = await client.get(f"/characters/{cid}/spells")
    assert r.status_code == 200, r.text
    voce = next(s for s in r.json() if s["srd_index"] == "elemental-weapon")
    # 1d4/2d4/3d4 del tipo scelto arrivano agli attacchi con l'arma (opzione già nel totale), l'incantesimo non ha un tiro suo
    assert not (voce["damage_dice"] and not (voce["effect"] or {}).get("hit_damage"))


@pytest.mark.caccia(id="CB-4033", fonte="2014 · Incantesimi · Arma Elementale · pag. 215", zona="regola:2014/incantesimi-A-C", voce="regola",
                    copre=["carta:2014/spells.md#Arma Elementale", "POST /characters/{char_id}/spells", "GET /characters/{char_id}/spells"])
async def test_arma_elementale_2014_dal_catalogo_non_tira_danni_al_lancio(client):
    cid = await _pg_2014(client, "paladin", 9)
    await _dal_catalogo_2014(client, cid, "elemental-weapon")
    r = await client.get(f"/characters/{cid}/spells")
    assert r.status_code == 200, r.text
    voce = next(s for s in r.json() if s["srd_index"] == "elemental-weapon")
    # +1/+2/+3 e 1d4/2d4/3d4 del tipo scelto arrivano agli attacchi con l'arma (opzione già nel totale), l'incantesimo non ha un tiro suo
    assert not (voce["damage_dice"] and not (voce["effect"] or {}).get("hit_damage"))


@pytest.mark.caccia(id="CB-4034", fonte="2014 · Incantesimi · Porta Dimensionale · pag. 261", zona="regola:2014/incantesimi-M-R", voce="regola",
                    copre=["carta:2014/spells.md#Porta Dimensionale", "POST /characters/{char_id}/spells", "GET /characters/{char_id}/spells"])
async def test_porta_dimensionale_2014_dal_catalogo_non_tira_danni_al_lancio(client):
    cid = await _pg_2014(client, "bard", 7)
    await _dal_catalogo_2014(client, cid, "dimension-door")
    r = await client.get(f"/characters/{cid}/spells")
    assert r.status_code == 200, r.text
    voce = next(s for s in r.json() if s["srd_index"] == "dimension-door")
    # la carta descrive solo il teletrasporto: i 4d6 forza del manuale toccano chi viaggia solo se l'arrivo fallisce, mai al lancio
    assert not (voce["damage_dice"] and not (voce["effect"] or {}).get("hit_damage"))


@pytest.mark.caccia(id="CB-4035", fonte="2014 · Incantesimi · Cura Ferite di Massa (Invocazione di 5° livello) · pag. 228", zona="regola:2014/incantesimi-A-C",
                    voce="regola", copre=["carta:2014/spells.md#Cura Ferite di Massa", "POST /characters/{char_id}/spells"])
async def test_cura_ferite_di_massa_2014_e_di_invocazione(client):
    cid = await _pg_2014(client, "cleric", 9)
    # Invocazione = evocation (Evocazione = conjuration): conta per la Trasposizione Benevola solo se fosse conjuration
    assert (await _dal_catalogo_2014(client, cid, "mass-cure-wounds"))["school"] == "evocation"
    assert granted_spell("mass-cure-wounds", "2014").school == "evocation"  # incantesimo di dominio della Vita


@pytest.mark.caccia(id="CB-4036", fonte="2014 · Incantesimi · Rinascita (Necromanzia di 3° livello) · pag. 271", zona="regola:2014/incantesimi-M-R",
                    voce="regola", copre=["carta:2014/spells.md#Rinascita", "POST /characters/{char_id}/spells"])
async def test_rinascita_2014_e_di_necromanzia(client):
    cid = await _pg_2014(client, "cleric", 5)
    assert (await _dal_catalogo_2014(client, cid, "revivify"))["school"] == "necromancy"
    assert granted_spell("revivify", "2014").school == "necromancy"  # incantesimo di dominio della Vita
