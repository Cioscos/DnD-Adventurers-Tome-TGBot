"""Stregone 2014 (Task 28): progressione, PF, Fonte di Magia, Incantesimi Flessibili, Ripristino Stregonesco."""
from __future__ import annotations

import pytest

from core.rules.catalog import features_for
from core.rules.proficiencies import class_proficiencies
from tests.integration.rules.test_2014_bard import _ability, _full, _keys_of, _use
from tests.integration.rules.test_2014_paladin import _rest, _turn

SP, CREATE, CONVERT = "sorcerer.sorcery_points", "sorcerer.flexible_casting_create", "sorcerer.flexible_casting_convert"
ORIGINS = {"draconic": "Discendenza Draconica", "wild_magic": "Magia Selvaggia"}
SLOT_COST = {1: 2, 2: 3, 3: 5, 4: 6, 5: 7}
SLOTS = {1: (2,), 2: (3,), 3: (4, 2), 4: (4, 3), 5: (4, 3, 2), 6: (4, 3, 3), 7: (4, 3, 3, 1), 8: (4, 3, 3, 2),
         9: (4, 3, 3, 3, 1), 10: (4, 3, 3, 3, 2), 11: (4, 3, 3, 3, 2, 1), 13: (4, 3, 3, 3, 2, 1, 1),
         15: (4, 3, 3, 3, 2, 1, 1, 1), 17: (4, 3, 3, 3, 2, 1, 1, 1, 1), 18: (4, 3, 3, 3, 3, 1, 1, 1, 1),
         19: (4, 3, 3, 3, 3, 2, 1, 1, 1), 20: (4, 3, 3, 3, 3, 2, 2, 1, 1)}
KNOWN = (2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 12, 13, 13, 14, 14, 15, 15, 15, 15)


async def _sorcerer(client, level=5, origin=None, **scores) -> int:
    body = {"name": "Stregone", "initial_class": {"class_name": "sorcerer", "level": level, "subclass": ORIGINS.get(origin)}}
    r = await client.post("/characters", json=body)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    for ability, value in scores.items():
        r = await client.patch(f"/characters/{cid}/ability_scores/{ability}", json={"value": value})
        assert r.status_code == 200, r.text
    return cid


async def _slots(client, cid) -> dict[int, tuple[int, int]]:
    return {s["level"]: (s["total"], s["used"]) for s in (await _full(client, cid))["spell_slots"] if not s["is_pact"]}


async def _points(client, cid) -> int:
    return (await _ability(client, cid, SP))["uses"]


async def _set_points(client, cid, uses) -> None:
    row = await _ability(client, cid, SP)
    r = await client.patch(f"/characters/{cid}/abilities/{row['id']}", json={"uses": uses})
    assert r.status_code == 200, r.text


# ---------------------------------------------------------------------------
# Progressione, PF, competenze
# ---------------------------------------------------------------------------

async def test_hit_points_use_the_d6_and_follow_constitution(client):
    full = await _full(client, await _sorcerer(client, 3))
    assert full["classes"][0]["hit_die"] == 6 and full["hit_points"] == 6 + 4 + 4


def test_class_proficiencies_first_class_and_multiclass():
    first = class_proficiencies("2014", "sorcerer", False)
    assert not first.armor and not first.tools and set(first.saves) == {"constitution", "charisma"}
    assert first.skills_count == 2 and set(first.skills_from) == {"arcana", "deception", "insight", "intimidation", "persuasion", "religion"}
    multi = class_proficiencies("2014", "sorcerer", True)
    assert not multi.armor and not multi.weapons and not multi.saves and multi.skills_count == 0


async def test_rules_only_rows_do_not_clutter_the_sheet(client):
    keys = await _keys_of(client, await _sorcerer(client, 20, "draconic"))
    assert not keys & {f"sorcerer.{k}" for k in (
        "hit_points", "proficiencies", "equipment", "spellcasting", "sorcerous_origin", "metamagic",
        "ability_score_improvement", "sorcerous_restoration", "multiclassing")}


@pytest.mark.parametrize("level,pending", [(3, 0), (4, 1), (7, 1), (8, 2), (11, 2), (12, 3), (15, 3), (16, 4), (18, 4), (19, 5), (20, 5)])
async def test_asi_choices_are_pending_at_levels_4_8_12_16_and_19(client, level, pending):
    full = await _full(client, await _sorcerer(client, level))
    assert len([c for c in full["pending_choices"] if c.get("kind") == "asi"]) == pending


@pytest.mark.parametrize("level", list(SLOTS))
async def test_slots_cantrips_and_known_follow_the_table(client, level):
    full = await _full(client, await _sorcerer(client, level))
    totals = tuple(s["total"] for s in sorted(full["spell_slots"], key=lambda s: s["level"]) if s["total"])
    assert totals == SLOTS[level]
    limits = full["spellcasting"]["limits"][0]
    assert (limits["cantrips_limit"], limits["known_limit"]) == (6 if level >= 10 else 5 if level >= 4 else 4, KNOWN[level - 1])


# ---------------------------------------------------------------------------
# Fonte di Magia
# ---------------------------------------------------------------------------

async def test_sorcery_points_appear_at_level_2_and_equal_the_sorcerer_level(client):
    assert SP not in await _keys_of(client, await _sorcerer(client, 1))
    for level in (2, 9, 20):
        row = await _ability(client, await _sorcerer(client, level), SP)
        assert (row["max_uses"], row["uses"], row["restoration_type"]) == (level, level, "long_rest")


async def test_sorcery_points_come_back_with_a_long_rest_and_not_a_short_one(client):
    cid = await _sorcerer(client, 9)
    await _set_points(client, cid, 2)
    await _rest(client, cid, "short")
    assert await _points(client, cid) == 2
    await _rest(client, cid, "long")
    assert await _points(client, cid) == 9


async def test_sorcery_points_depend_only_on_sorcerer_levels(client):
    cid = await _sorcerer(client, 5)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "wizard", "level": 4})
    assert r.status_code in (200, 201), r.text
    assert (await _ability(client, cid, SP))["max_uses"] == 5


# ---------------------------------------------------------------------------
# Ripristino Stregonesco
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,missing,back", [(19, 6, 0), (20, 6, 4), (20, 2, 2)])
async def test_sorcerous_restoration_gives_back_up_to_four_points_on_a_short_rest_from_level_20(client, level, missing, back):
    cid = await _sorcerer(client, level)
    await _set_points(client, cid, level - missing)
    await _rest(client, cid, "short")
    assert await _points(client, cid) == level - missing + back


async def test_sorcerous_restoration_is_listed_in_the_rest_preview(client):
    cid = await _sorcerer(client, 20)
    await _set_points(client, cid, 10)
    r = await client.get(f"/characters/{cid}/rest/preview", params={"rest_type": "short"})
    assert "Punti Stregoneria" in r.json()["abilities"]


# ---------------------------------------------------------------------------
# Incantesimi Flessibili: Creare Slot Incantesimo
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("slot,cost", list(SLOT_COST.items()))
async def test_creating_a_slot_costs_the_table_points_and_adds_a_slot(client, slot, cost):
    cid = await _sorcerer(client, 12)
    before = (await _slots(client, cid)).get(slot, (0, 0))
    r = await _use(client, cid, CREATE, params={"slot_level": str(slot)})
    assert r.status_code == 200, r.text
    assert await _points(client, cid) == 12 - cost
    assert (await _slots(client, cid))[slot] == (before[0] + 1, before[1])
    assert (await _turn(client, cid))["bonus_used"] is True


async def test_the_created_slot_can_be_a_level_the_class_table_does_not_give_yet(client, test_session_factory):
    from core.db.models import Ability
    cid = await _sorcerer(client, 4)
    async with test_session_factory() as s:  # i punti di una scheda scritta a mano
        row = await s.get(Ability, (await _ability(client, cid, SP))["id"])
        row.max_uses = row.uses = 10
        await s.commit()
    assert 3 not in await _slots(client, cid)
    r = await _use(client, cid, CREATE, params={"slot_level": "3"})
    assert r.status_code == 200, r.text
    assert (await _slots(client, cid))[3] == (1, 0)
    await _rest(client, cid, "long")
    assert 3 not in await _slots(client, cid)


async def test_creating_a_slot_above_level_5_is_refused_and_costs_nothing(client):
    cid = await _sorcerer(client, 12)
    r = await _use(client, cid, CREATE, params={"slot_level": "6"})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_choice"
    assert await _points(client, cid) == 12 and (await _turn(client, cid))["bonus_used"] is False


async def test_creating_a_slot_without_enough_points_is_refused_and_keeps_the_bonus_action(client):
    cid = await _sorcerer(client, 6)
    await _set_points(client, cid, 4)
    r = await _use(client, cid, CREATE, params={"slot_level": "3"})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_uses"
    assert await _points(client, cid) == 4 and (await _turn(client, cid))["bonus_used"] is False


async def test_creating_a_slot_needs_the_bonus_action(client):
    cid = await _sorcerer(client, 12)
    assert (await _use(client, cid, CREATE, params={"slot_level": "1"})).status_code == 200
    r = await _use(client, cid, CREATE, params={"slot_level": "1"})
    assert r.status_code == 409 and await _points(client, cid) == 10


async def test_the_created_slot_is_spendable_and_vanishes_with_a_long_rest(client):
    cid = await _sorcerer(client, 5)
    await _use(client, cid, CREATE, params={"slot_level": "2"})
    spell = (await client.post(f"/characters/{cid}/spells", json={"name": "Raggio", "level": 2, "casting_time": "1 azione"})).json()["id"]
    for _ in range(4):
        assert (await client.post(f"/characters/{cid}/spells/{spell}/use", json={"slot_level": 2})).status_code == 200
    assert (await _slots(client, cid))[2] == (4, 4)
    await _rest(client, cid, "long")
    assert (await _slots(client, cid))[2] == (3, 0)


async def test_the_created_slot_survives_a_level_up_until_the_long_rest(client):
    cid = await _sorcerer(client, 5)
    await _use(client, cid, CREATE, params={"slot_level": "2"})
    klass = (await _full(client, cid))["classes"][0]
    await client.patch(f"/characters/{cid}/classes/{klass['id']}", json={"level": 6})
    assert (await _slots(client, cid))[2] == (4, 0)
    await _rest(client, cid, "long")
    assert (await _slots(client, cid))[2] == (3, 0)


# ---------------------------------------------------------------------------
# Incantesimi Flessibili: Convertire uno Slot in Punti
# ---------------------------------------------------------------------------

async def test_converting_a_slot_spends_it_and_gives_points_equal_to_its_level(client):
    cid = await _sorcerer(client, 9)
    await _set_points(client, cid, 2)
    r = await _use(client, cid, CONVERT, params={"slot_level": "3"})
    assert r.status_code == 200, r.text
    assert await _points(client, cid) == 5 and (await _slots(client, cid))[3] == (3, 1)
    assert (await _turn(client, cid))["bonus_used"] is True


async def test_converted_points_never_exceed_the_maximum(client):
    cid = await _sorcerer(client, 5)
    await _set_points(client, cid, 4)
    assert (await _use(client, cid, CONVERT, params={"slot_level": "3"})).status_code == 200
    assert await _points(client, cid) == 5 and (await _slots(client, cid))[3] == (2, 1)


async def test_converting_needs_a_free_slot_of_that_level_and_costs_nothing_otherwise(client):
    cid = await _sorcerer(client, 3)
    await _set_points(client, cid, 1)
    r = await _use(client, cid, CONVERT, params={"slot_level": "3"})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_choice"
    assert await _points(client, cid) == 1 and (await _turn(client, cid))["bonus_used"] is False


async def test_converting_is_a_bonus_action(client):
    cid = await _sorcerer(client, 9)
    await _set_points(client, cid, 0)
    assert (await _use(client, cid, CONVERT, params={"slot_level": "1"})).status_code == 200
    r = await _use(client, cid, CONVERT, params={"slot_level": "1"})
    assert r.status_code == 409 and await _points(client, cid) == 1


def test_every_row_of_the_catalog_is_for_the_2014_sorcerer():
    assert features_for("2014", "sorcerer") and all(f.edition == "2014" and f.class_key == "sorcerer" for f in features_for("2014", "sorcerer"))


# ---------------------------------------------------------------------------
# Giro di correzione 1: spesa atomica (I6), chiavi degli slot creati (M3), PF della Resilienza Draconica (I5)
# ---------------------------------------------------------------------------

async def test_two_simultaneous_creations_pay_for_one_slot_only(client):
    import asyncio
    cid = await _sorcerer(client, 10)
    await _set_points(client, cid, 5)
    before = (await _slots(client, cid))[3][0]
    first, second = await asyncio.gather(*(_use(client, cid, CREATE, params={"slot_level": "3"}) for _ in range(2)))
    assert sorted((first.status_code, second.status_code)) == [200, 409], (first.text, second.text)
    assert await _points(client, cid) == 0 and (await _slots(client, cid))[3][0] == before + 1


@pytest.mark.parametrize("raw,kept", [({"12": 1}, {}), ({"23": 1, "2345": 2}, {}), ({"3": 1, "6": 1, "0": 1, "": 1}, {"3": 1}),
                                      ({"1": 1, "5": 2}, {"1": 1, "5": 2})])
def test_created_slot_keys_are_levels_one_to_five_only(raw, kept):
    from core.rules.created_slots import clean_created_slots
    assert clean_created_slots(raw) == kept


async def test_a_new_draconic_sorcerer_starts_at_the_effective_maximum(client):
    for level in (1, 18):
        cid = await _sorcerer(client, level, "draconic")
        full = await _full(client, cid)
        assert full["current_hit_points"] == full["computed"]["hp_max_effective"] > full["hit_points"]


async def test_a_draconic_sorcerer_at_full_health_stays_full_when_levelling_up(client):
    cid = await _sorcerer(client, 1, "draconic")
    klass = (await _full(client, cid))["classes"][0]
    for level in (2, 3, 4):
        r = await client.patch(f"/characters/{cid}/classes/{klass['id']}", json={"level": level})
        assert r.status_code == 200, r.text
        full = await _full(client, cid)
        assert full["current_hit_points"] == full["computed"]["hp_max_effective"], level


async def test_a_wounded_draconic_sorcerer_keeps_the_same_proportion_when_levelling_up(client):
    cid = await _sorcerer(client, 4, "draconic")
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 10})
    klass = (await _full(client, cid))["classes"][0]
    await client.patch(f"/characters/{cid}/classes/{klass['id']}", json={"level": 5})
    full = await _full(client, cid)
    assert 0 < full["current_hit_points"] < full["computed"]["hp_max_effective"]


async def test_the_first_catalog_sync_fills_a_draconic_sorcerer_who_was_at_full_health_and_leaves_a_wounded_one(client, test_session_factory):
    from core.db.models import Character
    from core.rules.feature_sync import RETROFIT_DONE
    from sqlalchemy import select
    healthy, wounded = await _sorcerer(client, 5, "draconic"), await _sorcerer(client, 5, "draconic")
    async with test_session_factory() as s:  # come un personaggio nato prima del catalogo: PF scritti a mano, nessun segno di retrofit
        for cid, current in ((healthy, None), (wounded, 12)):
            char = (await s.execute(select(Character).where(Character.id == cid))).scalar_one()
            char.current_hit_points = char.hit_points if current is None else current
            char.settings = {k: v for k, v in (char.settings or {}).items() if k != RETROFIT_DONE}
        await s.commit()
    from api.services.catalog_migration import migrate_catalog
    assert await migrate_catalog(test_session_factory) >= 2
    full = await _full(client, healthy)
    assert full["current_hit_points"] == full["computed"]["hp_max_effective"]
    assert (await _full(client, wounded))["current_hit_points"] == 12


# ---------------------------------------------------------------------------
# Giro di correzione 2: il flusso del wizard (I5), due Creare Slot insieme (I6)
# ---------------------------------------------------------------------------

async def _wizard_sorcerer(client, level=1) -> tuple[int, int]:
    """Come il wizard di creazione: nessuna sottoclasse, che si sceglie dopo con un PATCH della classe."""
    r = await client.post("/characters", json={"name": "Stregone", "initial_class": {
        "class_name": "sorcerer", "level": level, "hit_die": 6, "spellcasting_ability": "charisma"}})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    return cid, (await _full(client, cid))["classes"][0]["id"]


async def _origin(client, cid, class_id, name):
    r = await client.patch(f"/characters/{cid}/classes/{class_id}", json={"subclass": name})
    assert r.status_code == 200, r.text
    full = r.json()
    return full["current_hit_points"], full["computed"]["hp_max_effective"]


async def test_choosing_the_draconic_origin_after_creation_keeps_a_full_character_full(client):
    cid, class_id = await _wizard_sorcerer(client)
    current, effective = await _origin(client, cid, class_id, ORIGINS["draconic"])
    assert current == effective == (await _full(client, cid))["hit_points"] + 1
    await client.patch(f"/characters/{cid}/classes/{class_id}", json={"level": 5})
    full = await _full(client, cid)
    assert full["current_hit_points"] == full["computed"]["hp_max_effective"]


async def test_choosing_the_draconic_origin_leaves_a_wounded_character_as_it_is(client):
    cid, class_id = await _wizard_sorcerer(client, 4)
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 3})
    current, effective = await _origin(client, cid, class_id, ORIGINS["draconic"])
    assert current == 3 and effective > 3


async def test_changing_the_origin_away_from_draconic_cuts_the_current_hit_points_to_the_new_maximum(client):
    cid, class_id = await _wizard_sorcerer(client, 5)
    await _origin(client, cid, class_id, ORIGINS["draconic"])
    current, effective = await _origin(client, cid, class_id, ORIGINS["wild_magic"])
    assert current == effective == (await _full(client, cid))["hit_points"]


async def test_two_simultaneous_creations_with_points_for_both_pay_for_one_slot_only(client):
    import asyncio
    cid = await _sorcerer(client, 10)
    await _set_points(client, cid, 10)
    before = (await _slots(client, cid))[3][0]
    first, second = await asyncio.gather(*(_use(client, cid, CREATE, params={"slot_level": "3"}) for _ in range(2)))
    assert sorted((first.status_code, second.status_code)) == [200, 409], (first.text, second.text)
    assert await _points(client, cid) == 5 and (await _slots(client, cid))[3][0] == before + 1
