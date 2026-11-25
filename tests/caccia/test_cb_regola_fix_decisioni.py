"""Controlli delle decisioni dell'utente D-021…D-044 (tests/caccia/decisioni.md), scritti nel giro che le applica."""
import pytest

from tests.integration._encounter_helpers import PLAYER_ID, as_user


async def _pg(client, edizione: str, classe: str | None = None, livello: int = 1, sottoclasse: str | None = None, **punteggi) -> int:
    corpo = {"name": "Prova", "rules_edition": edizione}
    if classe:
        corpo["initial_class"] = {"class_name": classe, "level": livello, "subclass": sottoclasse}
    r = await client.post("/characters", json=corpo)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    for nome, valore in punteggi.items():
        r = await client.patch(f"/characters/{cid}/ability_scores/{nome}", json={"value": valore})
        assert r.status_code == 200, r.text
    return cid


async def _scheda(client, cid) -> dict:
    return (await client.get(f"/characters/{cid}")).json()


async def _turno(client, cid) -> dict:
    return (await client.get(f"/characters/{cid}/turn-state")).json()["turn"]


@pytest.mark.caccia(id="CB-4601", fonte="decisione D-021 (tests/caccia/decisioni.md): nel 2024 «Termina» l'Ira è gratis; 2024 · Barbaro · Ira · pag. 51; 2014 · pag. 48",
                    zona="regola:2024/barbarian", voce="regola",
                    copre=["carta:2024/classes/barbarian.md#Ira / Rage (Barbaro 1, pag. 51)",
                           "DELETE /characters/{char_id}/active-states/{key}"])
@pytest.mark.parametrize("edizione, speso", [("2014", True), ("2024", False)])
async def test_terminare_l_ira_a_mano_costa_l_azione_bonus_solo_nel_2014(client, edizione, speso):
    cid = await _pg(client, edizione, "barbarian", 15)  # Ira Persistente: resta accesa al turno dopo senza attacchi
    assert (await client.post(f"/characters/{cid}/features/barbarian.rage/use", json={})).status_code == 200
    await client.post(f"/characters/{cid}/turn/new")
    assert (await client.delete(f"/characters/{cid}/active-states/rage")).status_code == 200
    assert (await _turno(client, cid))["bonus_used"] is speso


@pytest.mark.caccia(id="CB-4602", fonte="decisione D-022 (tests/caccia/decisioni.md): per edizione, nel 2024 il dado del Valore raddoppia sul critico e nel 2014 no; 2024 · Bardo · pag. 67; 2014 · pag. 55",
                    zona="regola:2024/bard", voce="regola",
                    copre=["carta:2024/classes/bard.md#Ispirazione in Combattimento / Combat Inspiration (Collegio del Valore 3, pag. 67)",
                           "POST /characters/{char_id}/attack/{attack_id}/damage"])
@pytest.mark.parametrize("edizione, dadi_tirati", [("2014", 1), ("2024", 2)])
async def test_il_dado_del_valore_2024_raddoppia_sul_critico_di_un_arma(client, test_session_factory, edizione, dadi_tirati):
    from tests.integration.rules import test_2014_bard_inspiration as b14, test_2024_bard as b24
    modulo = b14 if edizione == "2014" else b24
    _sid, bard, hero = await modulo._table(client, test_session_factory, level=3, subclass=modulo.VALOR)
    assert (await b14._give(client, bard, hero)).status_code == 200
    as_user(PLAYER_ID)
    arma = await b14._sword(client, hero)
    colpo = (await client.post(f"/characters/{hero}/items/{arma}/attack", json={"die": 20, "defer_damage": True})).json()
    assert colpo["is_critical"], colpo
    r = await client.post(f"/characters/{hero}/attack/{colpo['attack_id']}/damage", json={"options": ["bardic_die:damage"]})
    assert r.status_code == 200 and len(r.json()["option_result"]["extra_rolls"]) == dadi_tirati, r.text


@pytest.mark.caccia(id="CB-4603", fonte="decisione D-028 (tests/caccia/decisioni.md): assegnare PE non abbassa mai il livello di classe; 2024 · Glossario · Punti Esperienza · pag. 366-367",
                    zona="regola:2024/generali", voce="interazione",
                    copre=["carta:2024/general.md#Experience Points (Punti Esperienza) (pag. 366-367)", "PATCH /characters/{char_id}/xp"])
async def test_un_set_di_punti_esperienza_verso_l_alto_non_toglie_livelli(client):
    cid = await _pg(client, "2024", "fighter", 5)  # 0 PE: il livello viene dalla classe
    livello = lambda r: r.json()["classes"][0]["level"]  # noqa: E731
    r = await client.patch(f"/characters/{cid}/xp", json={"set": 300})
    assert r.status_code == 200 and livello(r) == 5
    r = await client.patch(f"/characters/{cid}/xp", json={"set": 14000})
    assert livello(r) == 6
    r = await client.patch(f"/characters/{cid}/xp", json={"set": 2700})  # correzione esplicita verso il basso
    assert livello(r) == 4
