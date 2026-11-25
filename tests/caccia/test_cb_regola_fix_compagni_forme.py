"""Controlli scritti dalla correzione del gruppo compagni-forme (dubbi «Q-…» risolti come difetti)."""
from types import SimpleNamespace

import pytest

from core.game.stats import roll_ability_mod
from tests.integration.rules.test_2014_bard import _full
from tests.integration.rules.test_2014_druid import _activate, _beast, _form
from tests.integration.rules.test_2014_ranger_beast import _companion, _master
from tests.integration.rules.test_2024_druid import _druid24
from tests.integration.rules.test_2024_ranger_subclasses import _beast as _primal, _companions, _sub
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


@pytest.mark.caccia(id="CB-4353", fonte="2024 · Ranger · Compagno Primordiale: PF e Dadi Vita della bestia seguono il livello di Ranger · pag. 122; Bestia della Terra: Dadi Vita d8 pari al livello · pag. 123",
                    zona="regola:2024/ranger", voce="regola",
                    copre=["carta:2024/classes/ranger.md#Compagno Primordiale / Primal Companion (Signore delle Bestie 3, pag. 122)",
                           "carta:2024/classes/ranger.md#Bestia della Terra / Beast of the Land (Signore delle Bestie 3, pag. 123)",
                           "GET /characters/{char_id}/companions", "POST /characters/{char_id}/companions/{comp_id}/hit-dice"])
async def test_i_dadi_vita_della_bestia_primordiale_salgono_col_livello(client, dadi):
    cid = await _sub(client, 5, "beast_master")
    comp = await _primal(client, cid)  # evocata al 5°: 5d8
    klass = (await _full(client, cid))["classes"][0]["id"]
    assert (await client.patch(f"/characters/{cid}/classes/{klass}", json={"level": 6})).status_code == 200
    comp = next(c for c in await _companions(client, cid) if c["id"] == comp["id"])
    assert (comp["max_hp"], comp["statblock"]["hit_dice"]) == (35, "6d8")
    assert (await client.patch(f"/characters/{cid}/companions/{comp['id']}/hp", json={"op": "damage", "value": 20})).status_code == 200
    dadi(1, 1, 1, 1, 1, 1)
    r = await client.post(f"/characters/{cid}/companions/{comp['id']}/hit-dice", json={"count": 6})
    assert r.status_code == 200, r.text
    assert r.json()["hit_dice_left"] == 0


@pytest.mark.caccia(id="CB-4354", fonte="2024 · Druido · Regole della Forma Selvatica: Forza, Destrezza e Costituzione sono quelle della Bestia · pag. 81",
                    zona="regola:2024/druid", voce="regola",
                    copre=["carta:2024/classes/druid.md#Regole della Forma Selvatica / Rules While Shape-Shifted (Druido 2, pag. 81)"])
def test_una_forma_2024_gia_salvata_col_massimo_usa_la_forza_della_bestia():
    """Lo stato salvato prima della correzione porta mode «max»: la Forza resta comunque quella della Bestia."""
    form = {"key": "wild_shape", "data": {"abilities": {"strength": 10}, "mode": "max", "own_hp": False}}
    char = SimpleNamespace(ability_scores=[SimpleNamespace(name="strength", value=18)], items=[], active_states=[form])
    assert roll_ability_mod(char, "strength") == 0
