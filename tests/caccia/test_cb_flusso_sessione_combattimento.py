"""Controlli della zona flusso:sessione-combattimento."""
import pytest

from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, seed_session


async def _incontro(client, fabbrica):
    as_user(GM_ID)
    sid, cid = await seed_session(fabbrica, player_dex=10)
    await client.post(f"/sessions/{sid}/encounter", json={"mode": "full"})
    r = await client.post(f"/sessions/{sid}/encounter/combatants",
                          json={"name": "G", "count": 1, "initiative_mod": 0, "max_hp": 7, "ac": 10})
    pg = next(c for c in r.json()["combatants"] if c["kind"] == "pc")
    as_user(PLAYER_ID)
    await client.patch(f"/characters/{cid}/ability_scores/dexterity", json={"value": 18})
    return sid, pg["id"]


@pytest.mark.caccia(id="CB-006", fonte="2014 · Iniziativa · pag. 189: prova di Destrezza al momento del tiro",
                    zona="flusso:sessione-combattimento", voce="interazione",
                    copre=["POST /sessions/{session_id}/encounter/combatants/{combatant_id}/initiative"])
async def test_iniziativa_con_la_destrezza_attuale(client, test_session_factory):
    sid, pid = await _incontro(client, test_session_factory)
    live = (await client.get(f"/sessions/{sid}/live")).json()
    assert next(c for c in live["encounter"]["combatants"] if c["id"] == pid)["initiative_mod"] == 4
    r = await client.post(f"/sessions/{sid}/encounter/combatants/{pid}/initiative", json={"die": 10})
    assert next(c for c in r.json()["combatants"] if c["id"] == pid)["initiative"] == 14


@pytest.mark.caccia(id="CB-022", fonte="2014 · Iniziativa · pag. 189: prova di Destrezza al momento del tiro",
                    zona="flusso:sessione-combattimento", voce="interazione", copre=["POST /sessions/{session_id}/encounter/start"])
async def test_iniziativa_d_ufficio_con_la_destrezza_attuale(client, test_session_factory):
    sid, pid = await _incontro(client, test_session_factory)
    as_user(GM_ID)
    r = await client.post(f"/sessions/{sid}/encounter/start", json={"auto_roll_missing": True})
    pg = next(c for c in r.json()["combatants"] if c["id"] == pid)
    assert pg["initiative"] - pg["initiative_die"] == 4


@pytest.mark.caccia(id="CB-030", fonte="invariante: una modifica accettata ha effetto, altrimenti è rifiutata", zona="flusso:sessione-combattimento",
                    voce="contratto", copre=["PATCH /sessions/{session_id}/encounter/combatants/{combatant_id}"])
async def test_il_modificatore_di_un_pg_sta_sulla_scheda(client, test_session_factory):
    sid, pid = await _incontro(client, test_session_factory)
    as_user(GM_ID)
    url = f"/sessions/{sid}/encounter/combatants/"
    assert (await client.patch(f"{url}{pid}", json={"initiative_mod": 5})).status_code == 422
    live = (await client.get(f"/sessions/{sid}/live")).json()["encounter"]["combatants"]
    mostro = next(c for c in live if c["kind"] == "monster")
    r = await client.patch(f"{url}{mostro['id']}", json={"initiative_mod": 5})
    assert next(c for c in r.json()["combatants"] if c["id"] == mostro["id"])["initiative_mod"] == 5
