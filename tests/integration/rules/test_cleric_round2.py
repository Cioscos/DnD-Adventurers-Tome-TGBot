"""Chierico 2014, giro di correzione 2: N1-N6, R1, R2."""
from __future__ import annotations

from tests.integration._encounter_helpers import GM_ID, as_user
from tests.integration.rules.test_2014_bard import _ability, _full, _spells, _states, _use
from tests.integration.rules.test_2014_cleric import POOL, _cleric
from tests.integration.rules.test_preserve_life import _go, _scene

WRATH = "cleric.destructive_wrath"


async def _spell(client, cid, srd_index) -> dict:
    return next(s for s in (await _spells(client, cid)).values() if s["srd_index"] == srd_index)


async def _roll(client, cid, spell, **body):
    return await client.post(f"/characters/{cid}/spells/{spell['id']}/roll_damage", json=body)


# --- N1: la riserva a catalogo ha un dato esplicito; le righe automatiche restano usabili ------------------------------

async def test_only_the_catalog_pool_rows_are_marked_as_pools(client):
    cleric = await _cleric(client, 5, "life")
    assert (await _ability(client, cleric, POOL))["is_pool"] is True
    assert (await _ability(client, cleric, "cleric.preserve_life"))["is_pool"] is False


async def test_an_automatic_row_of_a_class_without_catalog_stays_usable(client, rules_catalog):
    rules_catalog()  # registro vuoto: nessuna classe ha un catalogo, ognuna resta su CLASS_RESOURCES (non dipende dai task futuri)
    r = await client.post("/characters", json={"name": "Mago", "initial_class": {"class_name": "wizard", "level": 3}})
    recovery = await _ability(client, r.json()["id"], "wizard.arcane_recovery")
    assert recovery is not None and recovery["is_pool"] is False and recovery["has_on_use"] is False


# --- N2: la concentrazione di uno stato chiuso dal riposo si chiude con lui ------------------------------------------------

async def test_a_short_rest_ends_the_concentration_of_the_state_it_closes(client):
    cid = await _cleric(client, 6, "trickery", wisdom=16)
    assert (await _use(client, cid, "cleric.invoke_duplicity")).status_code == 200
    assert (await _full(client, cid))["settings"].get("concentration_item_spell")
    await client.post(f"/characters/{cid}/rest", json={"rest_type": "short", "confirm_early": True})
    assert await _states(client, cid) == []
    assert not (await _full(client, cid))["settings"].get("concentration_item_spell")


async def test_a_short_rest_keeps_the_concentration_of_a_spell(client):
    cid = await _cleric(client, 6, "life", wisdom=16)
    bless = await _spell(client, cid, "bless")
    assert (await client.post(f"/characters/{cid}/spells/{bless['id']}/use", json={"slot_level": 1})).status_code == 200
    await client.post(f"/characters/{cid}/rest", json={"rest_type": "short", "confirm_early": True})
    assert (await _full(client, cid))["concentrating_spell_id"] == bless["id"]


# --- N4: duplicato ed export conservano la seconda parte del danno ---------------------------------------------------------

async def test_export_import_and_duplicate_keep_the_second_damage_part(client):
    cid = await _cleric(client, 9, "light", wisdom=16)
    exported = (await client.get(f"/characters/{cid}/export")).json()
    strike = next(s for s in exported["spells"] if s["srd_index"] == "flame-strike")
    assert (strike["extra_damage_dice"], strike["extra_damage_type"]) == ("4d6", "radiant")
    for new in ((await client.post("/characters/import", json=exported)).json()["id"],
                (await client.post(f"/characters/{cid}/duplicate")).json()["id"]):
        copy = await _spell(client, new, "flame-strike")
        assert (copy["extra_damage_dice"], copy["extra_damage_type"]) == ("4d6", "radiant")


async def test_an_old_file_without_the_second_part_still_imports(client):
    cid = await _cleric(client, 9, "light", wisdom=16)
    exported = (await client.get(f"/characters/{cid}/export")).json()
    for s in exported["spells"]:
        s.pop("extra_damage_dice", None)
        s.pop("extra_damage_type", None)
    r = await client.post("/characters/import", json=exported)
    assert r.status_code == 201, r.text
    assert (await _spell(client, r.json()["id"], "flame-strike"))["extra_damage_dice"] is None


# --- N5 e N6: i dadi a mano si sommano, i gruppi si distinguono per tipo -----------------------------------------------------

async def test_dice_added_by_hand_are_summed_to_the_second_part(client):
    cid = await _cleric(client, 9, "light", wisdom=16)
    strike = await _spell(client, cid, "flame-strike")
    r = await _roll(client, cid, strike, casting_level=5, extra_dice="1d4", main_rolls=[1, 2, 3, 4], extra_rolls=[6, 6, 6, 6, 3])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 10 + 24 + 3 and body["extra_rolls"] == [6, 6, 6, 6, 3]
    assert [(p["kind"], p["type"], p["rolls"]) for p in body["parts"]] == [
        ("d6", "fire", [1, 2, 3, 4]), ("d6", "radiant", [6, 6, 6, 6]), ("d4", None, [3])]


async def test_the_second_part_is_named_by_type_and_the_wave_lets_the_player_choose(client):
    cid = await _cleric(client, 9, "tempest", wisdom=16)
    wave = await _spell(client, cid, "destructive-wave")
    assert wave["extra_damage_type"] == "radiant|necrotic"
    default = (await _roll(client, cid, wave, casting_level=5)).json()
    assert [p["type"] for p in default["parts"]] == ["thunder", "radiant"]
    chosen = (await _roll(client, cid, wave, casting_level=5, extra_damage_type="necrotic")).json()
    assert [p["type"] for p in chosen["parts"]] == ["thunder", "necrotic"] and chosen["extra_damage_type"] == "necrotic"
    assert (await _roll(client, cid, wave, casting_level=5, extra_damage_type="fire")).status_code == 422


async def test_destructive_wrath_leaves_the_radiant_part_and_the_hand_dice_alone(client):
    cid = await _cleric(client, 9, "tempest", wisdom=16)
    wave = await _spell(client, cid, "destructive-wave")
    r = await _roll(client, cid, wave, casting_level=5, extra_dice="1d4", extra_rolls=[1] * 5 + [1], options=[WRATH])
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 30 + 5 + 1 and r.json()["parts"][0]["rolls"] == [6] * 5


async def test_the_parts_come_with_the_dice_to_reroll(client):
    cid = await _cleric(client, 9, "light", wisdom=16)
    strike = await _spell(client, cid, "flame-strike")
    r = await _roll(client, cid, strike, casting_level=5)
    assert [p["type"] for p in r.json()["parts"]] == ["fire", "radiant"]
    assert len(r.json()["reroll_dice"]) == 8


# --- R1 e R2 ---------------------------------------------------------------------------------------------------------------

async def test_a_cast_from_an_item_ends_the_cloak_of_shadows(client):
    cid = await _cleric(client, 6, "trickery", wisdom=16)
    r = await client.post(f"/characters/{cid}/items", json={"name": "Bacchetta", "item_type": "wand", "item_metadata": {
        "granted_spells": [{"name": "Luce", "level": 0, "charges_cost": 0}]}})
    assert r.status_code == 201, r.text
    item = max(i["id"] for i in r.json()["items"])
    await _use(client, cid, "cleric.cloak_of_shadows")
    assert [s["key"] for s in await _states(client, cid)] == ["cloak_of_shadows"]
    assert (await client.post(f"/characters/{cid}/items/{item}/cast", json={"spell_index": 0})).status_code == 200
    assert await _states(client, cid) == []
    assert not (await _full(client, cid))["conditions"].get("invisible")


async def test_preserve_life_answers_with_the_amounts_not_the_hit_points(client, test_session_factory):
    sid, cleric, hero = await _scene(client, test_session_factory)
    as_user(GM_ID)
    body = (await _go(client, cleric, [(hero, 5)])).json()
    assert body["healed"] == [{"character_id": hero, "name": "Eroe", "healed": 5}]
