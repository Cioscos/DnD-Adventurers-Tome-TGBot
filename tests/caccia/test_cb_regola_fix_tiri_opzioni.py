"""Controlli scritti dal correttore del gruppo tiri-opzioni per i dubbi «Q-…» risolti dai verificatori come difetti."""
import pytest


async def _pg(client, edizione="2024", classe="fighter", livello=5) -> int:
    r = await client.post("/characters", json={"name": "P", "rules_edition": edizione,
                                               "initial_class": {"class_name": classe, "level": livello}})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    r = await client.patch(f"/characters/{cid}", json={"rules_edition": edizione})
    assert r.status_code == 200, r.text
    return cid


async def _cond(client, cid, **condizioni) -> dict:
    r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": condizioni})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.caccia(id="CB-4231", fonte="2024 · Regole di gioco · Vantaggio e Svantaggio, rilanci · pag. 12-13; Ispirazione Eroica · pag. 13", zona="regola:2024/generali",
                    voce="interazione", copre=["carta:2024/general.md#Vantaggio e Svantaggio / Advantage/Disadvantage (pag. 12-13)",
                                               "carta:2024/general.md#Ispirazione Eroica / Heroic Inspiration (pag. 13)",
                                               "POST /characters/{char_id}/skills/{skill_name}/roll"])
@pytest.mark.parametrize("primo,atteso", [
    ({"mode": "advantage", "dice": [8, 5]}, ("advantage", 8)),  # rilancia il 5: max(8, 3) = 8
    ({"mode": "normal", "dice": [15, 3], "avvelenato": True}, ("disadvantage", 15)),  # svantaggio automatico: min(15, 18) = 15
])
async def test_il_rilancio_con_ispirazione_tiene_l_altro_d20_e_il_modo(client, primo, atteso):
    cid = await _pg(client)
    if primo.pop("avvelenato", False):
        await _cond(client, cid, poisoned=True)
    await client.patch(f"/characters/{cid}/inspiration", json={"heroic_inspiration": True})
    assert (await client.post(f"/characters/{cid}/skills/stealth/roll", json=primo)).status_code == 200
    nuovo = 3 if atteso[0] == "advantage" else 18
    r = await client.post(f"/characters/{cid}/skills/stealth/roll", json={"with_inspiration": True, "die": nuovo})
    assert r.status_code == 200, r.text
    # un solo d20 si rilancia, l'altro resta e il vantaggio o lo svantaggio continua a decidere
    assert (r.json()["mode"], r.json()["die"]) == atteso, r.json()
    assert len(r.json()["dice"]) == 2 and nuovo in r.json()["dice"], r.json()

