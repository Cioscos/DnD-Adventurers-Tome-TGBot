"""Ladro 2014, Mistificatore Arcano (Task 27): incantesimi da terzo di incantatore e vincolo di scuola, Gioco di Prestigio
della Mano Magica, Imboscata Magica, Ingannatore Versatile e Ladro di Incantesimi."""
from __future__ import annotations

import pytest

from core.rules.spellcasting import known_limits
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user
from tests.integration.rules.test_2014_barbarian_round1 import _in_encounter
from tests.integration.rules.test_2014_bard import _ability, _full, _keys_of, _roll_keys, _use
from tests.integration.rules.test_2014_fighter_eldritch_knight import KNOWN, SLOTS, _cast, _spell
from tests.integration.rules.test_2014_paladin import _new_turn, _turn
from tests.integration.rules.test_2014_rogue import _rapier, _rogue

HAND, AMBUSH, VERSATILE, THIEF = "rogue.mage_hand_legerdemain", "rogue.magical_ambush", "rogue.versatile_trickster", "rogue.spell_thief"
AMBUSH_CAST, VERSATILE_ADV = "rogue.magical_ambush_cast", "rogue.versatile_trickster_advantage"


async def _trickster(client, level=9, **scores) -> int:
    return await _rogue(client, level, "arcane_trickster", **scores)


async def _with_hand(client, cid) -> int:
    return await _spell(client, cid, "Mano magica", 0, srd_index="mage-hand")


# ---------------------------------------------------------------------------
# Incantesimi da terzo di incantatore e vincolo di scuola
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level", list(SLOTS))
async def test_arcane_trickster_slots_cantrips_and_known_follow_the_table(client, level):
    full = await _full(client, await _trickster(client, level))
    totals = tuple(s["total"] for s in sorted(full["spell_slots"], key=lambda s: s["level"]) if s["total"])
    assert totals == SLOTS[level]
    limits = full["spellcasting"]["limits"][0]
    assert (limits["cantrips_limit"], limits["known_limit"]) == (4 if level >= 10 else 3, KNOWN[level])


@pytest.mark.parametrize("level,cantrips", [(2, 0), (3, 3), (9, 3), (10, 4), (20, 4)])
def test_cantrips_follow_the_rogue_table(level, cantrips):
    assert known_limits("2014", "rogue", level).cantrips == cantrips


@pytest.mark.parametrize("archetype", [None, "thief", "assassin"])
async def test_a_rogue_who_is_not_a_trickster_does_not_cast(client, archetype):
    full = await _full(client, await _rogue(client, 10, archetype))
    assert not [s for s in full["spell_slots"] if s["total"]] and full["spellcasting"]["limits"] == []
    assert full["spellcasting"]["casters"] == []


async def test_the_trickster_casts_with_intelligence_without_choosing_it(client):
    caster = (await _full(client, await _trickster(client, 7, intelligence=16)))["spellcasting"]["casters"][0]
    assert caster["ability"] == "intelligence" and caster["save_dc"] == 8 + 3 + 3 and caster["attack_bonus"] == 3 + 3


async def test_the_trickster_slots_add_a_third_of_the_rogue_levels_to_other_casters(client):
    cid = await _trickster(client, 9)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "wizard", "level": 4, "hit_die": 6})
    assert r.status_code == 201, r.text
    totals = {s["level"]: s["total"] for s in (await _full(client, cid))["spell_slots"] if s["total"]}
    assert totals == {1: 4, 2: 3, 3: 3, 4: 1}  # livello di incantatore 3 + 4 = 7


async def test_a_rogue_added_to_another_class_without_the_archetype_adds_no_slots(client):
    cid = await _rogue(client, 9, "thief")
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "wizard", "level": 4, "hit_die": 6})
    assert r.status_code == 201, r.text
    assert {s["level"]: s["total"] for s in (await _full(client, cid))["spell_slots"] if s["total"]} == {1: 4, 2: 3}


@pytest.mark.parametrize("level,free", [(3, 1), (7, 1), (8, 2), (13, 2), (14, 3), (19, 3), (20, 4)])
async def test_the_spells_outside_enchantment_and_illusion_are_limited_to_the_free_picks(client, level, free):
    limits = (await _full(client, await _trickster(client, level)))["spellcasting"]["limits"][0]
    assert limits["school_free_limit"] == free and limits["school_names"] == ["enchantment", "illusion"]
    assert limits["school_outside_count"] == 0


async def test_only_the_spells_outside_the_two_schools_count_for_the_trickster(client):
    cid = await _trickster(client, 3)
    await _spell(client, cid, "Charme", 1, school="enchantment")
    await _spell(client, cid, "Immagine silenziosa", 1, school="illusion")
    await _spell(client, cid, "Dardo", 1, school="evocation")
    limits = (await _full(client, cid))["spellcasting"]["limits"][0]
    assert limits["school_outside_count"] == 1 and limits["school_free_limit"] == 1
    await _spell(client, cid, "Scudo", 1, school="abjuration")
    limits = (await _full(client, cid))["spellcasting"]["limits"][0]
    assert limits["school_outside_count"] == 2 > limits["school_free_limit"]


async def test_the_school_limit_is_not_shared_with_the_eldritch_knight(client):
    cid = await _trickster(client, 3)
    await _spell(client, cid, "Scudo", 1, school="abjuration")
    await _spell(client, cid, "Dardo", 1, school="evocation")
    assert (await _full(client, cid))["spellcasting"]["limits"][0]["school_outside_count"] == 2


# ---------------------------------------------------------------------------
# Gioco di Prestigio della Mano Magica
# ---------------------------------------------------------------------------

async def test_the_trickster_features_come_at_their_levels(client):
    for level, keys in ((3, {HAND}), (9, {AMBUSH}), (13, {VERSATILE}), (17, {THIEF})):
        before = await _keys_of(client, await _trickster(client, level - 1 if level > 3 else 2))
        after = await _keys_of(client, await _trickster(client, level))
        assert not before & keys and keys <= after, level


async def test_a_rogue_of_another_archetype_has_no_trickster_features(client):
    keys = await _keys_of(client, await _rogue(client, 17, "thief"))
    assert not keys & {HAND, AMBUSH, VERSATILE, THIEF}


async def test_legerdemain_is_a_bonus_action_that_needs_mage_hand(client):
    cid = await _trickster(client, 3)
    assert (await _ability(client, cid, HAND))["action_type"] == "bonus_action"
    refused = await _use(client, cid, HAND)
    assert refused.status_code == 409 and refused.json()["detail"]["code"] == "feature_unavailable"
    assert (await _turn(client, cid))["bonus_used"] is False
    await _with_hand(client, cid)
    r = await _use(client, cid, HAND)
    assert r.status_code == 200, r.text
    assert "mage_hand_control" in r.json()["notes"] and (await _turn(client, cid))["bonus_used"] is True
    again = await _use(client, cid, HAND)
    assert again.status_code == 409 and again.json()["detail"]["code"] == "turn_slot_used"


async def test_legerdemain_recognises_mage_hand_by_name_too(client):
    cid = await _trickster(client, 3)
    await _spell(client, cid, "Mage Hand", 0)
    assert (await _use(client, cid, HAND)).status_code == 200


# ---------------------------------------------------------------------------
# Imboscata Magica
# ---------------------------------------------------------------------------

async def test_magical_ambush_marks_the_target_for_a_save_spell(client):
    cid = await _trickster(client, 9)
    web = await _spell(client, cid, "Ragnatela", 2, attack_save="DEX")
    ray = await _spell(client, cid, "Raggio di fuoco", 0, attack_save="ATK")
    assert AMBUSH_CAST in await _roll_keys(client, cid, "cast", spell_id=web)
    assert AMBUSH_CAST not in await _roll_keys(client, cid, "cast", spell_id=ray)  # senza TS non c'è nulla da svantaggiare
    r = await _cast(client, cid, web, slot_level=2, options=[AMBUSH_CAST])
    assert r.status_code == 200, r.text
    block = r.json()["option_result"]
    assert block["targets"] == [AMBUSH_CAST] and "svantaggio" in block["effects"][0]["it"]
    effect = (await client.get(f"/characters/{cid}/target-effects/{AMBUSH_CAST}")).json()["result"]
    assert effect["condition"] == "custom:magical_ambush" and effect["ends_at"] == {"anchor": "source", "edge": "end", "count": 1}


async def test_magical_ambush_is_per_spell_and_needs_the_archetype_at_level_9(client):
    cid = await _trickster(client, 8)
    web = await _spell(client, cid, "Ragnatela", 2, attack_save="DEX")
    assert AMBUSH_CAST not in await _roll_keys(client, cid, "cast", spell_id=web)
    thief = await _rogue(client, 9, "thief")
    web = await _spell(client, thief, "Ragnatela", 2, attack_save="DEX")
    assert AMBUSH_CAST not in await _roll_keys(client, thief, "cast", spell_id=web)


# ---------------------------------------------------------------------------
# Ingannatore Versatile
# ---------------------------------------------------------------------------

async def test_versatile_trickster_gives_advantage_on_attacks_until_the_end_of_the_turn(client):
    cid = await _trickster(client, 13)
    await _with_hand(client, cid)
    wid = await _rapier(client, cid)
    assert VERSATILE_ADV not in await _roll_keys(client, cid, "attack", item_id=wid)
    r = await _use(client, cid, VERSATILE)
    assert r.status_code == 200, r.text
    assert (await _turn(client, cid))["bonus_used"] is True
    assert VERSATILE_ADV in await _roll_keys(client, cid, "attack", item_id=wid)
    hit = await client.post(f"/characters/{cid}/items/{wid}/attack", json={"dice": [3, 14], "options": [VERSATILE_ADV]})
    assert hit.status_code == 200, hit.text
    assert hit.json()["mode_applied"] == "advantage" and hit.json()["to_hit_die"] == 14
    assert VERSATILE_ADV in await _roll_keys(client, cid, "attack", item_id=wid)  # vale per ogni attacco del turno
    await _new_turn(client, cid)
    assert VERSATILE_ADV not in await _roll_keys(client, cid, "attack", item_id=wid)


async def test_versatile_trickster_ends_with_the_turn_of_whoever_acts_in_an_encounter(client, test_session_factory, monkeypatch):
    sid, cid = await _in_encounter(client, test_session_factory, monkeypatch)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "rogue", "level": 13, "hit_die": 8,
                                                              "subclass": "Mistificatore Arcano"})
    assert r.status_code == 201, r.text
    await _with_hand(client, cid)
    wid = await _rapier(client, cid)
    assert (await _use(client, cid, VERSATILE)).status_code == 200
    as_user(GM_ID)
    assert (await client.post(f"/sessions/{sid}/encounter/next-turn")).status_code == 200  # finisce il turno del ladro
    as_user(PLAYER_ID)
    assert VERSATILE_ADV not in await _roll_keys(client, cid, "attack", item_id=wid)
    assert "versatile_trickster" not in {s["key"] for s in (await _full(client, cid))["active_states"] or []}


async def test_versatile_trickster_needs_mage_hand(client):
    cid = await _trickster(client, 13)
    refused = await _use(client, cid, VERSATILE)
    assert refused.status_code == 409 and refused.json()["detail"]["code"] == "feature_unavailable"
    assert (await _turn(client, cid))["bonus_used"] is False


async def test_versatile_trickster_is_visible_to_the_gm_and_the_group_as_a_state(client):
    cid = await _trickster(client, 13)
    await _with_hand(client, cid)
    await _use(client, cid, VERSATILE)
    state = next(s for s in (await _full(client, cid))["active_states"] if s["key"] == "versatile_trickster")
    assert state["data"]["others"] == [VERSATILE]


# ---------------------------------------------------------------------------
# Ladro di Incantesimi
# ---------------------------------------------------------------------------

async def _steal(client, cid, name="Palla di fuoco", level=3, stolen=True):
    return await _use(client, cid, THIEF, params={"stolen": stolen, "spell": name, "spell_level": str(level)})


async def test_spell_thief_is_one_reaction_use_per_long_rest_with_the_spell_dc(client):
    cid = await _trickster(client, 17, intelligence=16)
    row = await _ability(client, cid, THIEF)
    assert (row["action_type"], row["max_uses"], row["restoration_type"]) == ("reaction", 1, "long_rest")
    assert row["dc"] == 8 + 6 + 3


async def test_a_successful_theft_adds_the_spell_for_eight_hours_and_spends_reaction_and_use(client):
    cid = await _trickster(client, 17)
    r = await _steal(client, cid)
    assert r.status_code == 200, r.text
    assert (await _turn(client, cid))["reaction_used"] is True and (await _ability(client, cid, THIEF))["uses"] == 0
    full = await _full(client, cid)
    stolen = next(s for s in full["spells"] if s["name"] == "Palla di fuoco")
    assert stolen["level"] == 3 and stolen["is_prepared"] is True
    state = next(s for s in full["active_states"] if s["key"] == "spell_thief")
    assert state["rounds_left"] == 4800  # 8 ore


async def test_a_theft_whose_save_succeeded_only_spends_the_use(client):
    cid = await _trickster(client, 17)
    r = await _steal(client, cid, stolen=False)
    assert r.status_code == 200, r.text
    full = await _full(client, cid)
    assert not (full["spells"] or []) and not [s for s in (full["active_states"] or []) if s["key"] == "spell_thief"]
    assert (await _ability(client, cid, THIEF))["uses"] == 0


@pytest.mark.parametrize("name,level", [("", 3), ("   ", 3), ("x" * 81, 3)])
async def test_a_theft_needs_a_spell_name_of_reasonable_length(client, name, level):
    cid = await _trickster(client, 17)
    r = await _steal(client, cid, name, level)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_text"
    assert (await _ability(client, cid, THIEF))["uses"] == 1 and (await _turn(client, cid))["reaction_used"] is False


@pytest.mark.parametrize("level", ["0", "5", "x"])
async def test_a_theft_cannot_take_a_spell_the_trickster_has_no_slot_for(client, level):
    cid = await _trickster(client, 17)  # slot fino al 3°
    r = await _use(client, cid, THIEF, params={"stolen": True, "spell": "Desiderio", "spell_level": level})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_choice"
    assert (await _ability(client, cid, THIEF))["uses"] == 1 and not ((await _full(client, cid))["spells"] or [])


async def test_the_stolen_spell_goes_away_at_the_long_rest_and_the_state_with_it(client):
    cid = await _trickster(client, 17)
    await _steal(client, cid)
    await _spell(client, cid, "Mano magica", 0)
    r = await client.post(f"/characters/{cid}/rest", json={"rest_type": "long", "confirm_early": True})
    assert r.status_code == 200, r.text
    full = await _full(client, cid)
    assert [s["name"] for s in full["spells"]] == ["Mano magica"]
    assert not [s for s in (full["active_states"] or []) if s["key"] == "spell_thief"]
    assert (await _ability(client, cid, THIEF))["uses"] == 1


async def test_the_stolen_spell_stays_through_a_short_rest(client):
    cid = await _trickster(client, 17)
    await _steal(client, cid)
    await client.post(f"/characters/{cid}/rest", json={"rest_type": "short"})
    assert [s["name"] for s in (await _full(client, cid))["spells"]] == ["Palla di fuoco"]


async def test_the_stolen_spell_goes_away_when_the_state_is_closed_by_hand(client):
    cid = await _trickster(client, 17)
    await _steal(client, cid)
    r = await client.delete(f"/characters/{cid}/active-states/spell_thief")
    assert r.status_code in (200, 204), r.text
    assert not (await _full(client, cid))["spells"]


async def test_a_stolen_spell_can_be_cast_with_a_slot_of_its_level(client):
    cid = await _trickster(client, 17)
    await _steal(client, cid)
    spell = next(s for s in (await _full(client, cid))["spells"] if s["name"] == "Palla di fuoco")
    r = await _cast(client, cid, spell["id"], slot_level=3)
    assert r.status_code == 200, r.text
