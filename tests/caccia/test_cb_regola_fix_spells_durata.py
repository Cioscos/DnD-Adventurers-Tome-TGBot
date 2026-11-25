"""Controlli scritti dai correttori del gruppo spells-durata per i dubbi risolti come difetti."""
import pytest

from tests.caccia.test_cb_regola_2014_incantesimi_d_f import _impara, _pg
from tests.caccia.test_cb_regola_2014_incantesimi_g_l import _dal_catalogo
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user
from tests.integration.rules.test_2014_bard import _add_spell, _full, _roll_keys, _use
from tests.integration.rules.test_2024_cleric_domains import _spell_rows, _table
from tests.integration.rules.test_2024_bard import VALOR, _bard24
from tests.integration.rules.test_2024_bard_lore_valor import _sword


@pytest.mark.caccia(id="CB-3911", fonte="2024 · Bardo · Collegio del Valore · Magia da Battaglia · pag. 67; Regole generali · Tempo di lancio · pag. 236",
                    zona="regola:2024/bard", voce="regola",
                    copre=["carta:2024/classes/bard.md#Magia da Battaglia / Battle Magic (Collegio del Valore 14, pag. 67)",
                           "carta:2024/general.md#Tempo di lancio / Casting Time (pag. 236)",
                           "POST /characters/{char_id}/spells/{spell_id}/use", "GET /characters/{char_id}/roll-options"])
async def test_magia_da_battaglia_non_segue_un_lancio_rituale(client):
    # Q-2024-bard-2: il rituale (+10 minuti) è un tempo di lancio lungo, non il tempo di lancio di un'azione
    cid = await _bard24(client, 14, VALOR)
    sword = await _sword(client, cid)
    bard_class = (await _full(client, cid))["classes"][0]["id"]
    spell = (await _add_spell(client, cid, "Rituale da un'azione", 1, casting_time="1 azione", is_ritual=True,
                              is_prepared=True, class_id=bard_class)).json()
    r = await client.post(f"/characters/{cid}/spells/{spell['id']}/use", json={"as_ritual": True})
    assert r.status_code == 200, r.text
    assert "bard.battle_magic" not in await _roll_keys(client, cid, "attack", item_id=sword)


@pytest.mark.caccia(id="CB-3912", fonte="2014 · Incantesimi · Deflagrazione Occulta (un tiro per colpire per ogni raggio) · pag. 229",
                    zona="regola:2014/incantesimi-D-F", voce="regola",
                    copre=["carta:2014/spells.md#Deflagrazione Occulta", "POST /characters/{char_id}/spells/{spell_id}/attack"])
@pytest.mark.xfail(strict=True, reason="CB-3912: difforme dal manuale, rinviato (un tiro e un danno per raggio cambiano la UX del lancio)")
async def test_deflagrazione_occulta_tira_per_colpire_una_volta_per_raggio(client, dadi):
    # Q-2014-incantesimi-d-f-1: «effettuando un tiro per colpire separato per ogni raggio», anche sullo stesso bersaglio
    cid = await _pg(client, "warlock", 5)  # due raggi
    sid = await _impara(client, cid, "eldritch-blast")
    dadi(20, 1)  # il primo raggio fa 20 naturale, il secondo 1: nessuno dei due decide per l'altro
    r = await client.post(f"/characters/{cid}/spells/{sid}/attack", json={})
    assert r.status_code == 200, r.text
    assert sorted(r.json()["dice"]) == [1, 20]  # oggi un solo d20 vale per tutti i raggi: critico o mancato tutto insieme


@pytest.mark.caccia(id="CB-3913", fonte="2024 · Chierico · Dominio della Guerra · Benedizione del Dio della Guerra (termina prima se lo si rilancia) · pag. 77",
                    zona="regola:2024/cleric", voce="regola",
                    copre=["carta:2024/classes/cleric.md#Benedizione del Dio della Guerra / War God's Blessing (Guerra 6, pag. 77)",
                           "POST /characters/{char_id}/features/{feature_key}/use", "POST /characters/{char_id}/spells/{spell_id}/use"])
async def test_lo_scudo_della_fede_della_benedizione_rilanciato_su_altri_lascia_il_bersaglio_di_prima(client, test_session_factory):
    # senza Concentrazione il lancio non scaccia il precedente da solo: lo chiude la regola del privilegio
    _, chierico, eroe = await _table(client, test_session_factory, 6, "war")
    as_user(PLAYER_ID)
    ca = (await _full(client, eroe))["ac"]
    as_user(GM_ID)
    scudo = (await _spell_rows(client, chierico))["shield-of-faith"]["id"]
    for bersaglio in (eroe, chierico):
        assert (await _use(client, chierico, "cleric.war_gods_blessing", params={"spell": "shield-of-faith"})).status_code == 200
        r = await client.post(f"/characters/{chierico}/spells/{scudo}/use", json={"free_cast": True, "targets": [bersaglio]})
        assert r.status_code == 200, r.text
        assert (await client.post(f"/characters/{chierico}/turn/new")).status_code == 200
    as_user(PLAYER_ID)
    assert (await _full(client, eroe))["ac"] == ca  # il secondo lancio ha chiuso il primo



@pytest.mark.caccia(id="CB-3914", fonte="2014 · Incantesimi · Immagine Maggiore (dal 6° livello senza concentrazione) · pag. 242",
                    zona="regola:2014/incantesimi-G-L", voce="interazione",
                    copre=["carta:2014/spells.md#Immagine Maggiore", "POST /characters/{char_id}/spells/{spell_id}/use"])
@pytest.mark.parametrize("nome", ["Immagine Maggiore", "Major Image", "Immagine Maggiore / Major Image"])
async def test_immagine_maggiore_scritta_a_mano_dal_sesto_livello_non_chiede_concentrazione(client, nome):
    # la riga senza srd_index (scritta a mano, homebrew, import vecchi) si riconosce dal nome, come per gli effetti del lancio
    cid = await _pg(client, "bard", 17)
    silenziosa = await _impara(client, cid, "silent-image")
    riga = {k: v for k, v in _dal_catalogo("major-image").items() if k != "srd_index"} | {"name": nome}
    r = await client.post(f"/characters/{cid}/spells", json=riga)
    assert r.status_code == 201, r.text
    maggiore = r.json()["id"]
    assert (await client.post(f"/characters/{cid}/spells/{silenziosa}/use", json={"slot_level": 1})).status_code == 200
    r = await client.post(f"/characters/{cid}/spells/{maggiore}/use", json={"slot_level": 6, "confirm": ["one_slot_per_turn"]})
    assert r.status_code == 200, r.text
    assert r.json()["concentrating_spell_id"] == silenziosa  # quella su Immagine Silenziosa resta
