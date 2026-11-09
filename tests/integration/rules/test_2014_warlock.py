"""Warlock 2014 (Task 29): progressione, Magia del Patto, Dono del Patto, scelta delle suppliche, Arcanum Mistico,
Maestro dell'Occulto."""
from __future__ import annotations

import pytest

from core.rules.catalog import features_for
from core.rules.proficiencies import class_proficiencies
from core.rules.spellcasting import known_limits
from tests.integration.rules.test_2014_bard import _ability, _full, _keys_of, _use
from tests.integration.rules.test_2014_fighter_eldritch_knight import _spell
from tests.integration.rules.test_2014_paladin import _rest, _turn

PATRONS = {"archfey": "Il Signore Fatato", "fiend": "L'Immondo", "great_old_one": "Il Grande Antico"}
PACT = {1: (1, 1), 2: (2, 1), 3: (2, 2), 5: (2, 3), 7: (2, 4), 9: (2, 5), 10: (2, 5), 11: (3, 5), 16: (3, 5), 17: (4, 5), 20: (4, 5)}
CANTRIPS = {1: 2, 3: 2, 4: 3, 9: 3, 10: 4, 20: 4}
KNOWN = {1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 7, 7: 8, 8: 9, 9: 10, 10: 10, 11: 11, 12: 11, 13: 12, 14: 12, 15: 13, 16: 13, 17: 14, 18: 14, 19: 15, 20: 15}
INVOCATIONS_BY_LEVEL = {1: None, 2: 2, 4: 2, 5: 3, 6: 3, 7: 4, 9: 5, 11: 5, 12: 6, 15: 7, 18: 8, 20: 8}
MASTER = "warlock.eldritch_master"


async def _warlock(client, level=5, patron=None, **scores) -> int:
    body = {"name": "Warlock", "initial_class": {"class_name": "warlock", "level": level, "subclass": PATRONS.get(patron)}}
    r = await client.post("/characters", json=body)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    for ability, value in scores.items():
        r = await client.patch(f"/characters/{cid}/ability_scores/{ability}", json={"value": value})
        assert r.status_code == 200, r.text
    return cid


def _choice(full: dict, group: str) -> dict | None:
    return next((c for c in full["pending_choices"] if c.get("group") == group), None)


async def _resolve(client, cid, group, options):
    choice = _choice(await _full(client, cid), group)
    return await client.post(f"/characters/{cid}/choices/{choice['id']}/resolve", json={"kind": "class_option", "options": options})


async def _pact_slots(client, cid) -> list[dict]:
    return [s for s in (await _full(client, cid))["spell_slots"] if s["is_pact"] and s["total"]]


async def _set_used(client, cid, slot_id, used) -> None:
    r = await client.patch(f"/characters/{cid}/spell_slots/{slot_id}", json={"used": used})
    assert r.status_code == 200, r.text


async def _with_blast(client, cid) -> None:
    await _spell(client, cid, "Deflagrazione occulta", 0, srd_index="eldritch-blast", attack_save="ATK", damage_dice="1d10", damage_type="force")


# ---------------------------------------------------------------------------
# Progressione, PF, competenze
# ---------------------------------------------------------------------------

async def test_hit_points_use_the_d8_and_follow_constitution(client):
    full = await _full(client, await _warlock(client, 3))
    assert full["classes"][0]["hit_die"] == 8 and full["hit_points"] == 8 + 5 + 5


@pytest.mark.parametrize("level,constitution", [(1, 14), (12, 10), (20, 16)])
async def test_a_character_created_at_a_high_level_gets_the_hit_points_of_every_level(client, level, constitution):
    full = await _full(client, await _warlock(client, level, constitution=constitution))
    con = (constitution - 10) // 2
    assert full["hit_points"] == 8 + con + (level - 1) * (5 + con)


def test_class_proficiencies_first_class_and_multiclass():
    first = class_proficiencies("2014", "warlock", False)
    assert set(first.armor) == {"light"} and set(first.weapons) == {"simple"} and not first.tools
    assert set(first.saves) == {"wisdom", "charisma"} and first.skills_count == 2
    assert set(first.skills_from) == {"arcana", "deception", "history", "intimidation", "investigation", "nature", "religion"}
    multi = class_proficiencies("2014", "warlock", True)
    assert set(multi.armor) == {"light"} and set(multi.weapons) == {"simple"} and not multi.saves and multi.skills_count == 0


async def test_rules_only_rows_do_not_clutter_the_sheet_and_the_old_pact_counter_is_gone(client):
    keys = await _keys_of(client, await _warlock(client, 20, "fiend"))
    assert not keys & {f"warlock.{k}" for k in (
        "hit_points", "otherworldly_patron", "pact_magic", "eldritch_invocations", "pact_boon", "ability_score_improvement", "multiclassing")}
    assert "warlock.pact_slots" not in keys


@pytest.mark.parametrize("level,pending", [(3, 0), (4, 1), (7, 1), (8, 2), (11, 2), (12, 3), (15, 3), (16, 4), (18, 4), (19, 5), (20, 5)])
async def test_asi_choices_are_pending_at_levels_4_8_12_16_and_19(client, level, pending):
    full = await _full(client, await _warlock(client, level))
    assert len([c for c in full["pending_choices"] if c.get("kind") == "asi"]) == pending


# ---------------------------------------------------------------------------
# Magia del Patto
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level", list(PACT))
async def test_pact_slots_follow_the_table_and_all_have_one_level(client, level):
    full = await _full(client, await _warlock(client, level))
    pact = [s for s in full["spell_slots"] if s["is_pact"] and s["total"]]
    assert [(p["total"], p["level"]) for p in pact] == [PACT[level]]
    assert not [s for s in full["spell_slots"] if not s["is_pact"] and s["total"]]


@pytest.mark.parametrize("level", list(KNOWN))
def test_cantrips_and_known_spells_follow_the_table(level):
    limits = known_limits("2014", "warlock", level)
    assert (limits.cantrips, limits.spells) == (max(v for k, v in CANTRIPS.items() if k <= level), KNOWN[level])


async def test_the_spell_save_dc_and_attack_use_charisma(client):
    cid = await _warlock(client, 5, charisma=18)
    spell = await _spell(client, cid, "Maledizione", 1, attack_save="SAVE")
    listed = next(s for s in (await client.get(f"/characters/{cid}/spells")).json() if s["id"] == spell)
    assert listed["save_dc"] == 8 + 3 + 4 and listed["attack_bonus"] == 3 + 4


async def test_a_lower_level_spell_cast_with_a_pact_slot_spends_the_pact_slot_at_its_level(client):
    cid = await _warlock(client, 5)
    spell = await _spell(client, cid, "Tocco", 1)
    r = await client.post(f"/characters/{cid}/spells/{spell}/use", json={"slot_level": 3})
    assert r.status_code == 200, r.text
    [pact] = await _pact_slots(client, cid)
    assert pact["level"] == 3 and pact["used"] == 1


async def test_pact_slots_return_on_a_short_rest(client):
    cid = await _warlock(client, 5)
    [pact] = await _pact_slots(client, cid)
    await _set_used(client, cid, pact["id"], 2)
    await _rest(client, cid, "short")
    assert (await _pact_slots(client, cid))[0]["used"] == 0


async def test_multiclass_pact_and_regular_slots_are_separate_pools(client):
    cid = await _warlock(client, 5)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "wizard", "level": 5})
    assert r.status_code in (200, 201), r.text
    full = await _full(client, cid)
    pact = next(s for s in full["spell_slots"] if s["is_pact"] and s["total"])
    regular = next(s for s in full["spell_slots"] if not s["is_pact"] and s["level"] == 3 and s["total"])
    assert pact["level"] == 3 and regular["total"] == 2  # i livelli da warlock non contano nel livello combinato
    spell = await _spell(client, cid, "Fulmine", 3)
    # col solo livello: gli slot normali per primi
    await client.post(f"/characters/{cid}/spells/{spell}/use", json={"slot_level": 3})
    full = await _full(client, cid)
    assert next(s for s in full["spell_slots"] if s["id"] == regular["id"])["used"] == 1
    assert next(s for s in full["spell_slots"] if s["id"] == pact["id"])["used"] == 0
    # con slot_id: il pool scelto
    await client.post(f"/characters/{cid}/spells/{spell}/use", json={"slot_id": pact["id"]})
    full = await _full(client, cid)
    assert next(s for s in full["spell_slots"] if s["id"] == pact["id"])["used"] == 1


# ---------------------------------------------------------------------------
# Dono del Patto
# ---------------------------------------------------------------------------

async def test_the_pact_boon_is_chosen_at_level_3_among_chain_blade_and_tome(client):
    assert _choice(await _full(client, await _warlock(client, 2)), "pact_boon") is None
    choice = _choice(await _full(client, await _warlock(client, 3)), "pact_boon")
    assert choice["count"] == 1 and {o["key"] for o in choice["options"]} == {"chain", "blade", "tome"}
    assert all(o["name"]["it"] and o["name"]["en"] and 0 < len(o["summary"]["it"]) <= 200 for o in choice["options"])


@pytest.mark.parametrize("boon", ["chain", "blade", "tome"])
async def test_only_the_chosen_boon_becomes_a_row_and_it_cannot_be_replaced(client, boon):
    cid = await _warlock(client, 3)
    r = await _resolve(client, cid, "pact_boon", [boon])
    assert r.status_code == 200, r.text
    keys = await _keys_of(client, cid)
    assert {f"warlock.pact_of_the_{b}" for b in ("chain", "blade", "tome")} & keys == {f"warlock.pact_of_the_{boon}"}
    assert _choice(r.json(), "pact_boon") is None
    klass = (await _full(client, cid))["classes"][0]
    other = next(b for b in ("chain", "blade", "tome") if b != boon)
    r = await client.post(f"/characters/{cid}/classes/{klass['id']}/options/replace", json={"group": "pact_boon", "old_key": boon, "new_key": other})
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Suppliche: quante, quali, sostituzione
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,count", list(INVOCATIONS_BY_LEVEL.items()))
async def test_invocations_known_follow_the_level(client, level, count):
    choice = _choice(await _full(client, await _warlock(client, level)), "invocations")
    assert (choice["count"] if choice else None) == count


async def test_the_offered_invocations_respect_level_boon_and_cantrip_prerequisites(client):
    cid = await _warlock(client, 2)
    offered = {o["key"] for o in _choice(await _full(client, cid), "invocations")["options"]}
    assert "armor_of_shadows" in offered and "beguiling_influence" in offered
    assert not offered & {"mire_the_mind", "ascendant_step", "lifedrinker", "thirsting_blade", "chains_of_carceri", "agonizing_blast",
                          "book_of_ancient_secrets", "voice_of_the_chain_master"}
    await _with_blast(client, cid)
    offered = {o["key"] for o in _choice(await _full(client, cid), "invocations")["options"]}
    assert {"agonizing_blast", "repelling_blast", "eldritch_spear"} <= offered
    assert all(o["name"]["it"] and o["name"]["en"] and 0 < len(o["summary"]["it"]) <= 200
               for o in _choice(await _full(client, cid), "invocations")["options"])


async def test_pact_gated_and_level_gated_invocations_appear_when_their_prerequisites_are_met(client):
    cid = await _warlock(client, 9)
    await _resolve(client, cid, "pact_boon", ["blade"])
    offered = {o["key"] for o in _choice(await _full(client, cid), "invocations")["options"]}
    assert {"thirsting_blade", "mire_the_mind", "one_with_shadows", "ascendant_step", "otherworldly_leap", "minions_of_chaos"} <= offered
    assert not offered & {"lifedrinker", "chains_of_carceri", "voice_of_the_chain_master", "book_of_ancient_secrets", "master_of_myriad_forms"}
    cid = await _warlock(client, 15)
    await _resolve(client, cid, "pact_boon", ["chain"])
    offered = {o["key"] for o in _choice(await _full(client, cid), "invocations")["options"]}
    assert {"chains_of_carceri", "voice_of_the_chain_master", "master_of_myriad_forms", "visions_of_distant_realms"} <= offered
    assert not offered & {"thirsting_blade", "lifedrinker", "book_of_ancient_secrets"}


async def test_an_invocation_that_fails_its_prerequisite_is_refused(client):
    cid = await _warlock(client, 2)
    assert (await _resolve(client, cid, "invocations", ["armor_of_shadows", "mire_the_mind"])).status_code == 422
    assert (await _resolve(client, cid, "invocations", ["armor_of_shadows", "agonizing_blast"])).status_code == 422
    assert (await _resolve(client, cid, "invocations", ["armor_of_shadows", "beast_speech"])).status_code == 200


async def test_each_chosen_invocation_becomes_a_row_and_the_others_do_not(client):
    cid = await _warlock(client, 2)
    await _resolve(client, cid, "invocations", ["armor_of_shadows", "beast_speech"])
    keys = await _keys_of(client, cid)
    assert {"warlock.armor_of_shadows", "warlock.beast_speech"} <= keys and "warlock.eldritch_sight" not in keys


async def test_an_invocation_can_be_replaced_with_one_that_meets_the_prerequisites(client):
    cid = await _warlock(client, 2)
    await _resolve(client, cid, "invocations", ["armor_of_shadows", "beast_speech"])
    klass = (await _full(client, cid))["classes"][0]
    replace = lambda old, new: client.post(f"/characters/{cid}/classes/{klass['id']}/options/replace",  # noqa: E731
                                           json={"group": "invocations", "old_key": old, "new_key": new})
    assert (await replace("beast_speech", "mire_the_mind")).status_code == 422
    assert (await replace("beast_speech", "eldritch_sight")).status_code == 200
    keys = await _keys_of(client, cid)
    assert "warlock.eldritch_sight" in keys and "warlock.beast_speech" not in keys


async def test_the_third_and_later_picks_add_to_the_old_ones(client):
    cid = await _warlock(client, 2)
    await _resolve(client, cid, "invocations", ["armor_of_shadows", "beast_speech"])
    klass = (await _full(client, cid))["classes"][0]
    await client.patch(f"/characters/{cid}/classes/{klass['id']}", json={"level": 5})
    choice = _choice(await _full(client, cid), "invocations")
    assert choice["count"] == 1 and not {"armor_of_shadows", "beast_speech"} & {o["key"] for o in choice["options"]}


# ---------------------------------------------------------------------------
# Maestro dell'Occulto
# ---------------------------------------------------------------------------

async def test_eldritch_master_exists_only_from_level_20_with_one_use(client):
    assert MASTER not in await _keys_of(client, await _warlock(client, 19))
    row = await _ability(client, await _warlock(client, 20), MASTER)
    assert row["max_uses"] == 1 and row["restoration_type"] == "long_rest"


async def test_eldritch_master_returns_every_spent_pact_slot_and_comes_back_on_a_long_rest(client):
    cid = await _warlock(client, 20)
    for slot in await _pact_slots(client, cid):
        await _set_used(client, cid, slot["id"], slot["total"])
    r = await _use(client, cid, MASTER)
    assert r.status_code == 200, r.text
    assert [s["used"] for s in await _pact_slots(client, cid)] == [0]
    assert (await _ability(client, cid, MASTER))["uses"] == 0
    assert (await _use(client, cid, MASTER)).status_code == 409
    assert (await _turn(client, cid))["action_used"] is False  # un minuto di invocazione: non costa l'azione del turno
    await _rest(client, cid, "long")
    assert (await _ability(client, cid, MASTER))["uses"] == 1


async def test_the_catalog_has_a_row_for_every_option_group_member():
    specs = features_for("2014", "warlock")
    options = {s.option_key for s in specs if s.option_group == "invocations"}
    assert len(options) == 32 and {s.option_key for s in specs if s.option_group == "pact_boon"} == {"chain", "blade", "tome"}


# ---------------------------------------------------------------------------
# Import da Beyond
# ---------------------------------------------------------------------------

async def test_beyond_pact_boon_and_invocations_find_the_catalog_choices_even_when_the_boon_comes_with_them(test_session_factory):
    from api.routers.transfer import _apply_class_options
    from api.services.ddb_import import ImportReport
    from core.rules.sample_characters import build_rules_character

    async with test_session_factory() as s:
        char = await build_rules_character(s, {"name": "x", "edition": "2014", "classes": [("warlock", 9, "Il Signore Fatato", 8)]}, 1)
        char.classes[0].options = {}
        report = ImportReport()
        names = ("Pact of the Blade", "Thirsting Blade", "Agonizing Blast", "Armor of Shadows", "Beast Speech", "Mystery")
        _apply_class_options(char, [{"class_index": 0, "name": n} for n in names], report, "it")
        options = char.classes[0].options
        assert options["pact_boon"] == ["blade"]
        assert options["invocations"] == ["thirsting_blade", "agonizing_blast", "armor_of_shadows", "beast_speech"]
        assert [e.name for e in report.approximated] == ["Mystery"]
