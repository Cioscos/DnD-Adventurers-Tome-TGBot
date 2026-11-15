"""Specie 2024 (Task 3): Dragonide, Nano, Goliath, Orco. Valori da docs/superpowers/rules/2024/races.md."""
from __future__ import annotations

import pytest

from core.data.species_2024 import SPECIES_2024, required_choices
from tests.integration.rules.test_2014_fighter_styles import _item
from tests.integration.rules.test_2014_bard import _ability, _full, _roll_keys, _use
from tests.integration.rules.test_2014_paladin import _hp, _hurt, _new_turn, _rest, _turn
from tests.integration.rules.test_species_2024 import _hero, _sync

DRAGON = "species.2024_dragonborn_"
GOLIATH = "species.2024_goliath_"


async def _species(client, factory, key, options=None, level=1, edition="2024", **fields) -> int:
    cid, _ = await _hero(client, level, edition)
    await _sync(factory, cid, species_key=key, species_options=options or {}, **fields)
    return cid


def test_data_cover_the_four_species():
    assert set(SPECIES_2024) >= {"2024_dragonborn", "2024_dwarf", "2024_goliath", "2024_orc"}
    assert required_choices("2024_dragonborn") == ("ancestry",) and required_choices("2024_goliath") == ("giant",)
    assert required_choices("2024_dwarf") == () and required_choices("2024_inesistente") == ()
    assert SPECIES_2024["2024_goliath"].choices[0].options == ("cloud", "fire", "frost", "hill", "stone", "storm")
    assert len(SPECIES_2024["2024_dragonborn"].choices[0].options) == 10


@pytest.mark.parametrize("level,die", [(1, "1d10"), (5, "2d10"), (11, "3d10"), (17, "4d10")])
async def test_dragonborn_breath_scales_and_flight_at_5(client, test_session_factory, level, die):
    cid = await _species(client, test_session_factory, "2024_dragonborn", {"ancestry": "red"}, level)
    row = await _ability(client, cid, DRAGON + "breath_weapon")
    assert row["max_uses"] == {1: 2, 5: 3, 11: 4, 17: 6}[level]
    assert (row["restoration_type"], row["action_type"]) == ("long_rest", "action")
    r = await _use(client, cid, DRAGON + "breath_weapon")
    assert r.status_code == 200, r.text
    assert len(r.json()["rolls"]) == int(die.split("d")[0]) and all(1 <= x <= 10 for x in r.json()["rolls"])
    flight = await _ability(client, cid, DRAGON + "draconic_flight")
    assert (flight is not None) == (level >= 5)
    full = await _full(client, cid)
    assert "fire" in full["computed"]["resistances"]
    assert {"type": "darkvision", "range_ft": 60} in full["computed"]["senses"]


async def test_dragonborn_resistance_follows_the_ancestry(client, test_session_factory):
    for dragon, damage in (("white", "cold"), ("green", "poison"), ("blue", "lightning")):
        cid = await _species(client, test_session_factory, "2024_dragonborn", {"ancestry": dragon})
        assert (await _full(client, cid))["computed"]["resistances"] == [damage]


async def test_dragonborn_breath_replaces_an_attack_and_flight_gives_fly_speed(client, test_session_factory):
    cid = await _species(client, test_session_factory, "2024_dragonborn", {"ancestry": "gold"}, level=5)
    first = await _use(client, cid, DRAGON + "breath_weapon")
    assert first.status_code == 200, first.text
    assert (await _turn(client, cid))["action_used"] is True
    assert (await _full(client, cid))["computed"]["fly_speed"] is None
    r = await _use(client, cid, DRAGON + "draconic_flight")
    assert r.status_code == 200, r.text
    assert r.json()["state"]["rounds_left"] == 100
    full = await _full(client, cid)
    assert full["computed"]["fly_speed"] == full["computed"]["speed"] == 30


async def test_dwarf_toughness_darkvision_poison(client, test_session_factory):
    base = (await _full(client, await _species(client, test_session_factory, None, level=4)))["computed"]["hp_max_effective"]
    cid = await _species(client, test_session_factory, "2024_dwarf", level=4)
    full = await _full(client, cid)
    assert full["computed"]["hp_max_effective"] == base + 4
    assert {"type": "darkvision", "range_ft": 120} in full["computed"]["senses"]
    assert "poison" in full["computed"]["resistances"]


async def test_dwarf_resilience_offers_advantage_on_saves_and_stonecunning_gives_tremorsense(client, test_session_factory):
    cid = await _species(client, test_session_factory, "2024_dwarf", level=3)
    assert "species.2024_dwarf_dwarven_resilience" in await _roll_keys(client, cid, "save", ability="constitution")
    row = await _ability(client, cid, "species.2024_dwarf_stonecunning")
    assert (row["max_uses"], row["restoration_type"], row["action_type"]) == (2, "long_rest", "bonus_action")
    assert not any(s["type"] == "tremorsense" for s in (await _full(client, cid))["computed"]["senses"])
    r = await _use(client, cid, "species.2024_dwarf_stonecunning")
    assert r.status_code == 200, r.text
    assert {"type": "tremorsense", "range_ft": 60} in (await _full(client, cid))["computed"]["senses"]


async def test_goliath_speed_35_and_powerful_build(client, test_session_factory):
    cid = await _species(client, test_session_factory, "2024_goliath", {"giant": "hill"})
    full = await _full(client, cid)
    assert full["computed"]["speed"] == 35
    assert full["carry_capacity"] == 2 * (await _full(client, await _species(client, test_session_factory, None)))["carry_capacity"]
    assert GOLIATH + "powerful_build" in await _roll_keys(client, cid, "save", ability="strength")


async def test_goliath_fire_extra_damage_spends_use(client, test_session_factory):
    cid = await _species(client, test_session_factory, "2024_goliath", {"giant": "fire"})
    key = GOLIATH + "giant_ancestry_fire"
    row = await _ability(client, cid, key)
    assert (row["max_uses"], row["uses"], row["restoration_type"]) == (2, 2, "long_rest")
    assert GOLIATH + "giant_ancestry_frost" not in {a["feature_key"] for a in (await _full(client, cid))["abilities"]}
    wid = await _item(client, cid, "Spada", damage_dice="1d8", weapon_type="melee", properties=[])
    r = await client.post(f"/characters/{cid}/items/{wid}/attack", json={"die": 15, "confirm_extra_attack": True, "defer_damage": True})
    assert r.status_code == 200, r.text
    hit = r.json()
    r = await client.post(f"/characters/{cid}/attack/{hit['attack_id']}/damage", json={"options": [key], "option_inputs": {}})
    assert r.status_code == 200, r.text
    assert "fire" in r.text and (await _ability(client, cid, key))["uses"] == 1


async def test_goliath_other_ancestries_have_their_own_row(client, test_session_factory):
    cid = await _species(client, test_session_factory, "2024_goliath", {"giant": "cloud"})
    assert (await _use(client, cid, GOLIATH + "giant_ancestry_cloud")).status_code == 200
    assert (await _ability(client, cid, GOLIATH + "giant_ancestry_cloud"))["uses"] == 1
    assert (await _turn(client, cid))["bonus_used"] is True
    storm = await _species(client, test_session_factory, "2024_goliath", {"giant": "storm"})
    assert (await _use(client, storm, GOLIATH + "giant_ancestry_storm")).status_code == 200
    assert (await _turn(client, storm))["reaction_used"] is True


async def test_goliath_stone_reduces_damage_taken(client, test_session_factory):
    cid = await _species(client, test_session_factory, "2024_goliath", {"giant": "stone"})
    assert GOLIATH + "giant_ancestry_stone" in await _roll_keys(client, cid, "damage_taken", damage_type="slashing")


async def test_goliath_large_form_at_5(client, test_session_factory):
    low = await _species(client, test_session_factory, "2024_goliath", {"giant": "hill"}, level=4)
    assert await _ability(client, low, GOLIATH + "large_form") is None
    cid = await _species(client, test_session_factory, "2024_goliath", {"giant": "hill"}, level=5)
    assert (await _use(client, cid, GOLIATH + "large_form")).status_code == 200
    assert (await _full(client, cid))["computed"]["speed"] == 45


async def test_orc_relentless_holds_at_one_once(client, test_session_factory):
    cid = await _species(client, test_session_factory, "2024_orc")
    key = "species.2024_orc_relentless_endurance"
    row = await _ability(client, cid, key)
    assert (row["max_uses"], row["restoration_type"]) == (1, "long_rest")
    await _hurt(test_session_factory, cid, 5)
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 9, "options": [key]})
    assert r.status_code == 200, r.text
    assert await _hp(client, cid) == 1 and (await _ability(client, cid, key))["uses"] == 0
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 9, "options": [key]})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "option_unavailable"
    assert (await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 9})).status_code == 200
    assert await _hp(client, cid) == 0
    await _hurt(test_session_factory, cid, 5)
    await _rest(client, cid, "long")
    assert (await _ability(client, cid, key))["uses"] == 1


async def test_orc_adrenaline_rush_gives_temp_hp_and_recharges_on_short_rest(client, test_session_factory):
    cid = await _species(client, test_session_factory, "2024_orc", level=5)
    key = "species.2024_orc_adrenaline_rush"
    row = await _ability(client, cid, key)
    assert (row["max_uses"], row["restoration_type"]) == (3, "short_rest")
    assert (await _use(client, cid, key)).status_code == 200
    full = await _full(client, cid)
    assert full["temp_hp"] == 3 and (await _ability(client, cid, key))["uses"] == 2
    assert {"type": "darkvision", "range_ft": 120} in full["computed"]["senses"]


async def test_2014_character_with_species_key_gets_nothing(client, test_session_factory):
    cid = await _species(client, test_session_factory, "2024_dwarf", level=4, edition="2014")
    full = await _full(client, cid)
    assert not [a for a in full["abilities"] if a["feature_key"].startswith("species.")]
    assert full["computed"]["resistances"] == [] and full["computed"]["senses"] == []
