"""Ladro 2014, Assassino (Task 27): Competenze Bonus, Assassinare, Maestro Infiltrato, Impostore e Colpo Mortale."""
from __future__ import annotations

import pytest

from tests.integration.rules.test_2014_bard import _ability, _full, _keys_of, _roll_keys, _use
from tests.integration.rules.test_2014_rogue import SNEAK, _damage, _hit, _rapier, _rogue, _skill_roll

BONUS, ASSASSINATE, INFILTRATION, IMPOSTOR, DEATH = (
    "rogue.bonus_proficiencies", "rogue.assassinate", "rogue.infiltration_expertise", "rogue.impostor", "rogue.death_strike")
ASSASSINATE_ADV, ASSASSINATE_CRIT = "rogue.assassinate_advantage", "rogue.assassinate_crit"
IMPOSTOR_ADV, DEATH_FAILED = "rogue.impostor_advantage", "rogue.death_strike_failed"


async def _gold(client, cid, value=None) -> int:
    if value is not None:
        r = await client.patch(f"/characters/{cid}/currency", json={"gold": value})
        assert r.status_code == 200, r.text
    return (await client.get(f"/characters/{cid}/currency")).json()["gold"]


async def _notes(client, cid) -> list[dict]:
    return (await client.get(f"/characters/{cid}/notes")).json()


async def test_the_assassin_features_come_at_their_levels(client):
    for level, keys in ((3, {BONUS, ASSASSINATE}), (9, {INFILTRATION}), (13, {IMPOSTOR}), (17, {DEATH})):
        before = await _keys_of(client, await _rogue(client, level - 1 if level > 3 else 2, "assassin"))
        after = await _keys_of(client, await _rogue(client, level, "assassin"))
        assert not before & keys and keys <= after, level


async def test_a_rogue_of_another_archetype_has_no_assassin_features(client):
    keys = await _keys_of(client, await _rogue(client, 17, "thief"))
    assert not keys & {BONUS, ASSASSINATE, INFILTRATION, IMPOSTOR, DEATH}


# ---------------------------------------------------------------------------
# Competenze Bonus
# ---------------------------------------------------------------------------

async def test_bonus_proficiencies_add_the_two_kits_once(client):
    cid = await _rogue(client, 3, "assassin")
    tools = (await _full(client, cid))["tool_proficiencies"]
    assert tools.get("disguise_kit") is True and tools.get("poisoners_kit") is True
    row = (await _full(client, cid))["classes"][0]["id"]
    await client.patch(f"/characters/{cid}/classes/{row}", json={"level": 4})
    assert (await _full(client, cid))["tool_proficiencies"] == tools


async def test_the_kits_are_not_given_to_other_archetypes(client):
    tools = (await _full(client, await _rogue(client, 3, "thief")))["tool_proficiencies"]
    assert "disguise_kit" not in tools and "poisoners_kit" not in tools


# ---------------------------------------------------------------------------
# Assassinare
# ---------------------------------------------------------------------------

async def test_assassinate_gives_advantage_against_a_creature_that_has_not_acted(client):
    cid = await _rogue(client, 3, "assassin")
    wid = await _rapier(client, cid)
    assert ASSASSINATE_ADV in await _roll_keys(client, cid, "attack", item_id=wid)
    r = await client.post(f"/characters/{cid}/items/{wid}/attack", json={"dice": [4, 15], "options": [ASSASSINATE_ADV]})
    assert r.status_code == 200, r.text
    assert r.json()["mode_applied"] == "advantage" and r.json()["to_hit_die"] == 15


async def test_assassinate_makes_a_hit_against_a_surprised_creature_critical(client):
    cid = await _rogue(client, 3, "assassin")
    wid = await _rapier(client, cid)
    assert ASSASSINATE_CRIT in await _roll_keys(client, cid, "attack", item_id=wid)
    r = await client.post(f"/characters/{cid}/items/{wid}/attack", json={"die": 10, "options": [ASSASSINATE_CRIT]})
    assert r.status_code == 200, r.text
    assert r.json()["is_critical"] is True and len(r.json()["damage_rolls"]) == 2  # 1d8 raddoppiato


async def test_assassinate_critical_is_not_applied_without_the_confirmation(client):
    cid = await _rogue(client, 3, "assassin")
    wid = await _rapier(client, cid)
    r = await client.post(f"/characters/{cid}/items/{wid}/attack", json={"die": 10})
    assert r.json()["is_critical"] is False and len(r.json()["damage_rolls"]) == 1


async def test_assassinate_doubles_the_sneak_attack_dice_too(client):
    cid = await _rogue(client, 5, "assassin")
    wid = await _rapier(client, cid)
    hit = await _hit(client, cid, wid, options=[ASSASSINATE_ADV, ASSASSINATE_CRIT])
    block = (await _damage(client, cid, hit, SNEAK)).json()["option_result"]
    assert len(block["extra_rolls"]) == 6  # 3d6 raddoppiati


async def test_assassinate_needs_the_assassin(client):
    cid = await _rogue(client, 5, "thief")
    wid = await _rapier(client, cid)
    keys = await _roll_keys(client, cid, "attack", item_id=wid)
    assert ASSASSINATE_ADV not in keys and ASSASSINATE_CRIT not in keys


# ---------------------------------------------------------------------------
# Maestro Infiltrato
# ---------------------------------------------------------------------------

async def test_infiltration_expertise_spends_25_gold_and_writes_the_identity_in_the_notes(client):
    cid = await _rogue(client, 9, "assassin")
    await _gold(client, cid, 100)
    row = await _ability(client, cid, INFILTRATION)
    assert [t["key"] for t in row["use_texts"]] == ["identity"]
    r = await _use(client, cid, INFILTRATION, params={"identity": "Marco il mercante"})
    assert r.status_code == 200, r.text
    assert await _gold(client, cid) == 75
    notes = await _notes(client, cid)
    assert len(notes) == 1 and "Marco il mercante" in notes[0]["title"] and "25" in notes[0]["body"]


async def test_infiltration_expertise_refuses_without_the_gold_and_writes_nothing(client):
    cid = await _rogue(client, 9, "assassin")
    await _gold(client, cid, 24)
    r = await _use(client, cid, INFILTRATION, params={"identity": "Marco"})
    assert r.status_code == 409 and r.json()["detail"] == "insufficient_funds"
    assert await _gold(client, cid) == 24 and not await _notes(client, cid)


@pytest.mark.parametrize("name", ["", "   ", "x" * 81])
async def test_infiltration_expertise_needs_a_name_of_reasonable_length(client, name):
    cid = await _rogue(client, 9, "assassin")
    await _gold(client, cid, 100)
    r = await _use(client, cid, INFILTRATION, params={"identity": name})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_text"
    assert await _gold(client, cid) == 100 and not await _notes(client, cid)


async def test_infiltration_expertise_refuses_the_name_of_an_identity_already_made(client):
    cid = await _rogue(client, 9, "assassin")
    await _gold(client, cid, 100)
    assert (await _use(client, cid, INFILTRATION, params={"identity": "Marco"})).status_code == 200
    again = await _use(client, cid, INFILTRATION, params={"identity": "Marco"})
    assert again.status_code == 409 and again.json()["detail"]["code"] == "identity_exists"
    assert await _gold(client, cid) == 75


async def test_infiltration_expertise_takes_the_gold_out_of_a_container_when_the_purse_is_short(client):
    cid = await _rogue(client, 9, "assassin")
    await _gold(client, cid, 10)
    r = await client.post(f"/characters/{cid}/items", json={"name": "Borsa", "item_type": "gear", "item_metadata": {
        "container": {"capacity_lb": 20, "coins": {"gold": 30}}}})
    assert r.status_code == 201, r.text
    assert (await _use(client, cid, INFILTRATION, params={"identity": "Marco"})).status_code == 200
    assert (await _full(client, cid))["coin_totals"]["gold"] == 15


# ---------------------------------------------------------------------------
# Impostore
# ---------------------------------------------------------------------------

async def test_impostor_gives_advantage_on_deception_only(client):
    cid = await _rogue(client, 13, "assassin")
    assert IMPOSTOR_ADV in await _roll_keys(client, cid, "skill", skill="deception")
    assert IMPOSTOR_ADV not in await _roll_keys(client, cid, "skill", skill="persuasion")
    body = await _skill_roll(client, cid, "deception", IMPOSTOR_ADV, dice=[3, 16])
    assert body["mode_applied"] == "advantage" and body["die"] == 16


async def test_impostor_needs_the_assassin_at_level_13(client):
    assert IMPOSTOR_ADV not in await _roll_keys(client, await _rogue(client, 12, "assassin"), "skill", skill="deception")
    assert IMPOSTOR_ADV not in await _roll_keys(client, await _rogue(client, 13, "thief"), "skill", skill="deception")


# ---------------------------------------------------------------------------
# Colpo Mortale
# ---------------------------------------------------------------------------

async def test_death_strike_shows_the_dc_and_doubles_the_damage_when_the_save_fails(client):
    cid = await _rogue(client, 17, "assassin", dexterity=16)  # CD 8 + 3 + 6
    wid = await _rapier(client, cid)
    assert DEATH in await _roll_keys(client, cid, "attack", item_id=wid)
    r = await client.post(f"/characters/{cid}/items/{wid}/attack",
                          json={"die": 10, "defer_damage": True, "options": [DEATH]})
    assert r.status_code == 200, r.text
    hit = r.json()
    effect = hit["option_result"]["effects"][0]
    assert "17" in effect["it"] and "17" in effect["en"] and "Costituzione" in effect["it"]
    assert DEATH_FAILED in await _roll_keys(client, cid, "attack", item_id=wid)
    doubled = await _damage(client, cid, hit, DEATH_FAILED)
    assert doubled.status_code == 200, doubled.text
    assert doubled.json()["damage_total"] == 2 * hit["damage_total"]


async def test_death_strike_doubles_the_sneak_attack_dice_as_well(client):
    cid = await _rogue(client, 17, "assassin", dexterity=16)
    wid = await _rapier(client, cid)
    r = await client.post(f"/characters/{cid}/items/{wid}/attack",
                          json={"mode": "advantage", "dice": [10, 12], "defer_damage": True, "options": [DEATH]})
    hit = r.json()
    done = (await _damage(client, cid, hit, SNEAK, DEATH_FAILED)).json()
    assert done["damage_total"] == 2 * (hit["damage_total"] + done["option_result"]["extra_total"])


async def test_death_strike_double_needs_the_prompt_before_the_roll(client):
    cid = await _rogue(client, 17, "assassin")
    wid = await _rapier(client, cid)
    hit = await _hit(client, cid, wid)
    refused = await _damage(client, cid, hit, DEATH_FAILED)
    assert refused.status_code == 409 and refused.json()["detail"]["code"] == "option_unavailable"


async def test_death_strike_needs_the_assassin_at_level_17(client):
    for cid in (await _rogue(client, 16, "assassin"), await _rogue(client, 17, "thief")):
        wid = await _rapier(client, cid)
        assert DEATH not in await _roll_keys(client, cid, "attack", item_id=wid)


async def test_death_strike_row_shows_the_dc_ability(client):
    row = await _ability(client, await _rogue(client, 17, "assassin", dexterity=16), DEATH)
    assert row["dc"] == 8 + 6 + 3
