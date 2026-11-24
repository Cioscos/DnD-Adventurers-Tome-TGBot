"""Controlli scritti dalla correzione del gruppo dati-incantesimi-fe (dubbi risolti come difetti)."""
import pytest

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
