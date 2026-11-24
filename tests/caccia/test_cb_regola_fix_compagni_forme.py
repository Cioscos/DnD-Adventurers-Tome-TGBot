"""Controlli scritti dalla correzione del gruppo compagni-forme (dubbi «Q-…» risolti come difetti)."""
import pytest

from tests.integration.rules.test_2014_druid import _activate, _beast, _form
from tests.integration.rules.test_2014_ranger_beast import _companion, _master
from tests.integration.rules.test_2024_druid import _druid24
from tests.integration.test_rules_forms import beast


def _from_catalog(index: str, size: str, kind: str, cr: float) -> dict:
    """Il corpo che CompanionForm manda per una voce del catalogo (monsterToStatblock: size, type, challenge_rating)."""
    sb = beast(cr=cr, type_=kind, dex=15, con=10)
    sb["size"] = size
    return {"srd_index": index, "statblock": sb}


@pytest.mark.caccia(id="CB-4351", fonte="2014 · Ranger · Signore delle Bestie · Compagno del Ranger: bestia Media o più piccola, GS 1/4 o meno · pag. 106",
                    zona="regola:2014/ranger", voce="limiti",
                    copre=["carta:2014/classes/ranger.md#Compagno del Ranger / Ranger's Companion (Signore delle Bestie 3, pag. 106)",
                           "POST /characters/{char_id}/companions"])
@pytest.mark.parametrize("body,status", [
    (_from_catalog("wolf", "Medium", "beast", 0.25), 201),  # al limite: Media, GS 1/4
    (_from_catalog("cat", "tiny", "beast", 0), 201),  # import di D&D Beyond: taglia in minuscolo
    (_from_catalog("brown-bear", "Large", "beast", 1), 422),
    (_from_catalog("young-red-dragon", "Large", "dragon", 10), 422),
    ({"statblock": {"actions": [{"name": "Morso", "attack_bonus": 4, "damage_dice": "1d6+2"}]}}, 201),  # a mano: nulla da verificare
])
async def test_la_bestia_fuori_dai_limiti_e_rifiutata_e_quella_nei_limiti_accettata(client, body, status):
    cid = await _master(client, 3)
    r = await _companion(client, cid, **body)
    assert r.status_code == status, r.text
    if status == 422:
        assert r.json()["detail"] == "beast_not_allowed"


@pytest.mark.caccia(id="CB-4352", fonte="2024 · Druido · Regole della Forma Selvatica: Forza, Destrezza e Costituzione sono quelle della Bestia · pag. 81",
                    zona="regola:2024/druid", voce="regola",
                    copre=["carta:2024/classes/druid.md#Regole della Forma Selvatica / Rules While Shape-Shifted (Druido 2, pag. 81)",
                           "POST /characters/{char_id}/skills/{skill_name}/roll",
                           "POST /characters/{char_id}/saving_throws/{ability}/roll"])
async def test_in_forma_2024_la_forza_e_quella_della_bestia_non_la_piu_alta(client):
    cid = await _druid24(client, 4, strength=18)  # nessuna competenza in Atletica né nel TS di Forza
    bestia = {**_beast(0.25), "abilities": {"str": 10, "dex": 10, "con": 12, "int": 3, "wis": 12, "cha": 6}}
    assert (await _activate(client, cid, await _form(client, cid, bestia))).status_code == 200
    atletica = (await client.post(f"/characters/{cid}/skills/athletics/roll", json={})).json()["bonus"]
    ts_for = (await client.post(f"/characters/{cid}/saving_throws/strength/roll", json={})).json()["bonus"]
    assert (atletica, ts_for) == (0, 0)  # Forza 10 della Bestia, non la Forza 18 del druido
