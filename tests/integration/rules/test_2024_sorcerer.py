"""Stregone 2024 (Task 40, parte A): tabelle, competenze, Stregoneria Innata, Fonte di Magia, Metamagia (le dieci opzioni),
Ripristino Stregonesco, Stregoneria Incarnata, Apoteosi Arcana e multiclasse. Valori da ``docs/superpowers/rules/2024/classes/sorcerer.md``."""
from __future__ import annotations

import pytest

from core.rules.catalog import features_for
from core.rules.proficiencies import class_proficiencies
from tests.integration.rules.test_2014_bard import _ability, _full, _keys_of, _roll_keys, _states, _use
from tests.integration.rules.test_2014_fighter_eldritch_knight import _spell
from tests.integration.rules.test_2014_paladin import _new_turn, _rest, _turn
from tests.integration.rules.test_2014_sorcerer import SP, _points, _set_points, _slots

INNATE, CREATE, CONVERT = "sorcerer.innate_sorcery", "sorcerer.font_create_slot", "sorcerer.font_convert_slot"
RESTORATION = "sorcerer.sorcerous_restoration"
OPTIONS = ["careful", "distant", "empowered", "extended", "heightened", "quickened", "seeking", "subtle", "transmuted", "twinned"]
CAREFUL, DISTANT, EMPOWERED, EXTENDED, HEIGHTENED, QUICKENED, SEEKING, SUBTLE, TRANSMUTED, TWINNED = (
    f"sorcerer.metamagic_{k}" for k in OPTIONS)
SLOTS = {1: (2,), 2: (3,), 3: (4, 2), 4: (4, 3), 5: (4, 3, 2), 7: (4, 3, 3, 1), 10: (4, 3, 3, 3, 2), 17: (4, 3, 3, 3, 2, 1, 1, 1, 1),
         20: (4, 3, 3, 3, 3, 2, 2, 1, 1)}
PREPARED = (2, 4, 6, 7, 9, 10, 11, 12, 14, 15, 16, 16, 17, 17, 18, 18, 19, 20, 21, 22)
SKILLS = {"arcana", "deception", "insight", "intimidation", "persuasion", "religion"}
CREATE_COSTS = {1: (2, 2), 2: (3, 3), 3: (5, 5), 4: (6, 7), 5: (7, 9)}  # livello dello slot -> (punti, livello minimo da stregone)


async def _sorcerer24(client, level=5, **scores) -> int:
    body = {"name": "Stregone", "initial_class": {"class_name": "sorcerer", "level": level, "subclass": None}}
    r = await client.post("/characters", json=body)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    for ability, value in scores.items():
        r = await client.patch(f"/characters/{cid}/ability_scores/{ability}", json={"value": value})
        assert r.status_code == 200, r.text
    return cid


def _pending(full: dict) -> dict | None:
    return next((c for c in full["pending_choices"] if c.get("group") == "metamagic"), None)


async def _caster24(client, level=10, *picks: str, **scores) -> int:
    """Uno stregone 2024 con le opzioni indicate (le altre scelte sono riempite con altre qualsiasi)."""
    cid = await _sorcerer24(client, level, **{"charisma": 18, **scores})
    choice = _pending(await _full(client, cid))
    chosen = list(picks) + [k for k in OPTIONS if k not in picks]
    r = await client.post(f"/characters/{cid}/choices/{choice['id']}/resolve", json={"kind": "class_option", "options": chosen[:choice["count"]]})
    assert r.status_code == 200, r.text
    return cid


async def _cast(client, cid, spell, *options, slot_level=None, **inputs):
    body = {"options": list(options), "option_inputs": inputs}
    if slot_level is not None:
        body["slot_level"] = slot_level
    return await client.post(f"/characters/{cid}/spells/{spell}/use", json=body)


async def _damage(client, cid, spell, *options, **body):
    r = await client.post(f"/characters/{cid}/spells/{spell}/roll_damage", json={"options": list(options), **body})
    assert r.status_code == 200, r.text
    return r.json()


async def _innate_on(client, cid) -> None:
    r = await _use(client, cid, INNATE)
    assert r.status_code == 200, r.text
    await _new_turn(client, cid)


# ---------------------------------------------------------------------------
# Tabelle, PF, competenze, righe di sola regola
# ---------------------------------------------------------------------------

async def test_hit_points_use_the_d6(client):
    full = await _full(client, await _sorcerer24(client, 3))
    assert full["classes"][0]["hit_die"] == 6 and full["hit_points"] == 6 + 4 + 4


def test_class_and_multiclass_proficiencies():
    first = class_proficiencies("2024", "sorcerer", False)
    assert not first.armor and not first.tools and set(first.weapons) == {"simple"} and set(first.saves) == {"constitution", "charisma"}
    assert first.skills_count == 2 and set(first.skills_from) == SKILLS
    multi = class_proficiencies("2024", "sorcerer", True)
    assert not multi.armor and not multi.weapons and not multi.saves and multi.skills_count == 0


@pytest.mark.parametrize("level,asi", [(4, [4]), (12, [4, 8, 12]), (16, [4, 8, 12, 16]), (19, [4, 8, 12, 16])])
async def test_asi_at_4_8_12_16_and_the_19th_is_an_epic_boon(client, level, asi):
    pending = (await _full(client, await _sorcerer24(client, level)))["pending_choices"]
    assert sorted(c["level"] for c in pending if c["kind"] == "asi") == asi
    assert any(c["kind"] == "epic_boon" for c in pending) == (level == 19)


async def test_rules_only_rows_stay_off_the_sheet(client):
    keys = await _keys_of(client, await _sorcerer24(client, 20))
    assert not keys & {f"sorcerer.{k}" for k in (
        "core_traits", "spellcasting", "metamagic", "sorcerer_subclass", "ability_score_improvement", "epic_boon", "multiclassing")}
    assert {INNATE, SP, CREATE, CONVERT, RESTORATION, "sorcerer.sorcery_incarnate", "sorcerer.arcane_apotheosis"} <= keys


@pytest.mark.parametrize("level,key", [(1, "innate_sorcery"), (2, "sorcery_points"), (2, "font_create_slot"), (2, "font_convert_slot"),
                                       (5, "sorcerous_restoration"), (7, "sorcery_incarnate"), (20, "arcane_apotheosis"),
                                       *((2, f"metamagic_{k}") for k in OPTIONS)])
def test_a_row_appears_exactly_at_its_level(level, key):
    assert {f.key: f for f in features_for("2024", "sorcerer")}[f"sorcerer.{key}"].level == level


def test_every_base_mapping_title_has_its_row_with_both_languages():
    titles = {f.source_title for f in features_for("2024", "sorcerer")}
    mapping = open("docs/superpowers/rules/mapping/2024/sorcerer.md", encoding="utf-8").read().splitlines()[4:]
    wanted = [line.split("|")[1].strip() for line in mapping if line.startswith("|")]
    base = [t for t in wanted if "(Stregone " in t or "(Metamagia, " in t or t.startswith("Multiclasse")]
    assert len(base) == 22 and [t for t in base if t not in titles] == []
    assert all(f.summary["it"] and f.summary["en"] and len(f.summary["it"]) <= 200 for f in features_for("2024", "sorcerer"))


async def test_the_2014_only_rows_are_gone_after_the_switch_to_2024(client):
    body = {"name": "Vecchio", "initial_class": {"class_name": "sorcerer", "level": 10, "subclass": None}}
    cid = (await client.post("/characters", json=body)).json()["id"]
    old = await _keys_of(client, cid)
    assert {"sorcerer.flexible_casting_create", "sorcerer.flexible_casting_convert"} <= old and INNATE not in old
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    keys = await _keys_of(client, cid)
    assert not keys & {"sorcerer.flexible_casting_create", "sorcerer.flexible_casting_convert"} and {INNATE, CREATE, CONVERT, SP} <= keys


@pytest.mark.parametrize("level", list(SLOTS))
async def test_slots_cantrips_and_prepared_follow_the_table(client, level):
    full = await _full(client, await _sorcerer24(client, level))
    totals = tuple(s["total"] for s in sorted(full["spell_slots"], key=lambda s: s["level"]) if s["total"])
    assert totals == SLOTS[level]
    limits = full["spellcasting"]["limits"][0]
    assert (limits["cantrips_limit"], limits["prepared_limit"]) == (6 if level >= 10 else 5 if level >= 4 else 4, PREPARED[level - 1])


# ---------------------------------------------------------------------------
# Stregoneria Innata e Stregoneria Incarnata
# ---------------------------------------------------------------------------

async def test_innate_sorcery_has_two_uses_that_come_back_with_a_long_rest(client):
    cid = await _sorcerer24(client, 1)
    row = await _ability(client, cid, INNATE)
    assert (row["max_uses"], row["uses"], row["restoration_type"]) == (2, 2, "long_rest")
    assert (await _use(client, cid, INNATE)).status_code == 200
    assert (await _ability(client, cid, INNATE))["uses"] == 1
    await _rest(client, cid, "long")
    assert (await _ability(client, cid, INNATE))["uses"] == 2


async def test_innate_sorcery_is_a_bonus_action_that_lasts_one_minute(client):
    cid = await _sorcerer24(client, 1)
    assert (await _use(client, cid, INNATE)).status_code == 200
    state = next(s for s in await _states(client, cid) if s["key"] == "innate_sorcery")
    assert state["rounds_left"] == 10 and (await _turn(client, cid))["bonus_used"] is True
    assert (await _use(client, cid, INNATE)).status_code == 409


async def _spell_row(client, cid, spell) -> dict:
    return next(s for s in (await client.get(f"/characters/{cid}/spells")).json() if s["id"] == spell)


async def test_innate_sorcery_adds_one_to_the_dc_of_sorcerer_spells_only_while_it_lasts(client):
    cid = await _sorcerer24(client, 5, charisma=16)
    spell = await _spell(client, cid, "Ragnatela", 2, attack_save="DEX")
    assert (await _spell_row(client, cid, spell))["save_dc"] == 8 + 3 + 3
    await _use(client, cid, INNATE)
    assert (await _spell_row(client, cid, spell))["save_dc"] == 8 + 3 + 3 + 1
    await _rest(client, cid, "long")
    assert (await _spell_row(client, cid, spell))["save_dc"] == 8 + 3 + 3


async def test_innate_sorcery_gives_advantage_on_sorcerer_spell_attacks(client):
    cid = await _sorcerer24(client, 5)
    spell = await _spell(client, cid, "Raggio di gelo", 0, attack_save="ATK", damage_dice="1d8", damage_type="cold")
    r = await client.post(f"/characters/{cid}/spells/{spell}/attack", json={"mode": "normal", "dice": [12]})
    assert r.json()["mode_applied"] == "normal"
    await _use(client, cid, INNATE)
    r = await client.post(f"/characters/{cid}/spells/{spell}/attack", json={"mode": "normal", "dice": [12, 5]})
    assert r.status_code == 200 and r.json()["mode_applied"] == "advantage" and r.json()["to_hit_die"] == 12


async def test_innate_sorcery_leaves_the_spells_of_another_class_alone(client):
    cid = await _sorcerer24(client, 5, charisma=16, intelligence=16)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "wizard", "level": 3})
    assert r.status_code in (200, 201), r.text
    sorc, wiz = sorted((await _full(client, cid))["classes"], key=lambda c: c["class_name"] != "sorcerer")
    mine = await _spell(client, cid, "Mio", 0, attack_save="ATK", class_id=sorc["id"])
    other = await _spell(client, cid, "Suo", 0, attack_save="ATK", class_id=wiz["id"])
    web = await _spell(client, cid, "Suo CD", 2, attack_save="DEX", class_id=wiz["id"])
    dc = (await _spell_row(client, cid, web))["save_dc"]
    await _use(client, cid, INNATE)
    assert (await _spell_row(client, cid, web))["save_dc"] == dc
    for spell, mode, dice in ((mine, "advantage", [12, 5]), (other, "normal", [12])):
        r = await client.post(f"/characters/{cid}/spells/{spell}/attack", json={"mode": "normal", "dice": dice})
        assert r.status_code == 200, r.text
        assert r.json()["mode_applied"] == mode, spell


async def test_sorcery_incarnate_pays_two_points_when_no_use_is_left(client):
    cid = await _sorcerer24(client, 7)
    assert "sorcerer.sorcery_incarnate" in await _keys_of(client, cid)
    row = await _ability(client, cid, INNATE)
    r = await client.patch(f"/characters/{cid}/abilities/{row['id']}", json={"uses": 0})
    assert r.status_code == 200, r.text
    assert (await _use(client, cid, INNATE)).status_code == 409 and await _points(client, cid) == 7
    r = await _use(client, cid, INNATE, params={"restore": True})
    assert r.status_code == 200, r.text
    assert await _points(client, cid) == 5 and (await _ability(client, cid, INNATE))["uses"] == 0
    assert any(s["key"] == "innate_sorcery" for s in await _states(client, cid))


async def test_sorcery_incarnate_is_refused_while_a_use_is_left_or_below_level_7(client):
    cid = await _sorcerer24(client, 7)
    r = await _use(client, cid, INNATE, params={"restore": True})
    assert r.status_code == 409 and await _points(client, cid) == 7 and (await _ability(client, cid, INNATE))["uses"] == 2
    low = await _sorcerer24(client, 6)
    row = await _ability(client, low, INNATE)
    await client.patch(f"/characters/{low}/abilities/{row['id']}", json={"uses": 0})
    assert (await _use(client, low, INNATE, params={"restore": True})).status_code == 409 and await _points(client, low) == 6


# ---------------------------------------------------------------------------
# Fonte di Magia
# ---------------------------------------------------------------------------

async def test_sorcery_points_appear_at_level_2_and_equal_the_sorcerer_level(client):
    assert SP not in await _keys_of(client, await _sorcerer24(client, 1))
    for level in (2, 9, 20):
        row = await _ability(client, await _sorcerer24(client, level), SP)
        assert (row["max_uses"], row["uses"], row["restoration_type"]) == (level, level, "long_rest")


async def test_sorcery_points_come_back_with_a_long_rest_and_not_a_short_one(client):
    cid = await _sorcerer24(client, 9)
    await _set_points(client, cid, 2)
    await _rest(client, cid, "short")
    assert await _points(client, cid) == 2
    await _rest(client, cid, "long")
    assert await _points(client, cid) == 9


@pytest.mark.parametrize("slot,cost,min_level", [(s, c, m) for s, (c, m) in CREATE_COSTS.items()])
async def test_creating_a_slot_costs_the_table_points_from_its_minimum_level(client, slot, cost, min_level):
    cid = await _sorcerer24(client, min_level)
    before = (await _slots(client, cid)).get(slot, (0, 0))
    r = await _use(client, cid, CREATE, params={"slot_level": str(slot)})
    assert r.status_code == 200, r.text
    assert await _points(client, cid) == min_level - cost and (await _slots(client, cid))[slot] == (before[0] + 1, before[1])
    assert (await _turn(client, cid))["bonus_used"] is True
    if min_level > 2:  # un livello sotto il minimo il livello dello slot non è ammesso e nulla si spende
        low = await _sorcerer24(client, min_level - 1)
        r = await _use(client, low, CREATE, params={"slot_level": str(slot)})
        assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_choice"
        assert await _points(client, low) == min_level - 1 and (await _turn(client, low))["bonus_used"] is False


async def test_creating_a_slot_above_level_5_is_refused_and_a_created_slot_vanishes_with_a_long_rest(client):
    cid = await _sorcerer24(client, 12)
    r = await _use(client, cid, CREATE, params={"slot_level": "6"})
    assert r.status_code == 422 and await _points(client, cid) == 12
    assert (await _use(client, cid, CREATE, params={"slot_level": "2"})).status_code == 200
    assert (await _slots(client, cid))[2][0] == 4
    await _rest(client, cid, "long")
    assert (await _slots(client, cid))[2][0] == 3


async def test_converting_a_slot_takes_no_action_and_gives_points_up_to_the_maximum(client):
    cid = await _sorcerer24(client, 9)
    await _set_points(client, cid, 2)
    r = await _use(client, cid, CONVERT, params={"slot_level": "3"})
    assert r.status_code == 200, r.text
    assert await _points(client, cid) == 5 and (await _slots(client, cid))[3] == (3, 1)
    turn = await _turn(client, cid)
    assert turn["bonus_used"] is False and turn["action_used"] is False
    assert (await _use(client, cid, CONVERT, params={"slot_level": "3"})).status_code == 200  # nessuna azione: si ripete
    await _set_points(client, cid, 8)
    assert (await _use(client, cid, CONVERT, params={"slot_level": "3"})).status_code == 200
    assert await _points(client, cid) == 9


async def test_converting_needs_a_free_slot_of_that_level_and_costs_nothing_otherwise(client):
    cid = await _sorcerer24(client, 3)
    await _set_points(client, cid, 1)
    r = await _use(client, cid, CONVERT, params={"slot_level": "3"})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_choice" and await _points(client, cid) == 1


async def test_sorcery_points_depend_only_on_sorcerer_levels(client):
    cid = await _sorcerer24(client, 5)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "wizard", "level": 4})
    assert r.status_code in (200, 201), r.text
    assert (await _ability(client, cid, SP))["max_uses"] == 5


# ---------------------------------------------------------------------------
# Ripristino Stregonesco
# ---------------------------------------------------------------------------

async def test_sorcerous_restoration_gives_back_up_to_half_the_level_once_between_long_rests(client):
    assert RESTORATION not in await _keys_of(client, await _sorcerer24(client, 4))
    cid = await _sorcerer24(client, 11)
    row = await _ability(client, cid, RESTORATION)
    assert (row["max_uses"], row["restoration_type"]) == (1, "long_rest")
    await _set_points(client, cid, 3)
    r = await _use(client, cid, RESTORATION, params={"points": "6"})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_choice" and await _points(client, cid) == 3
    r = await _use(client, cid, RESTORATION, params={"points": "5"})
    assert r.status_code == 200, r.text
    assert await _points(client, cid) == 8 and (await _turn(client, cid))["bonus_used"] is False
    assert (await _use(client, cid, RESTORATION, params={"points": "1"})).status_code == 409
    await _rest(client, cid, "long")
    await _set_points(client, cid, 1)
    assert (await _use(client, cid, RESTORATION, params={"points": "2"})).status_code == 200 and await _points(client, cid) == 3


async def test_sorcerous_restoration_never_passes_the_maximum_and_is_refused_at_full_points(client):
    cid = await _sorcerer24(client, 10)
    assert (await _use(client, cid, RESTORATION, params={"points": "1"})).status_code == 409
    assert (await _ability(client, cid, RESTORATION))["uses"] == 1
    await _set_points(client, cid, 8)
    assert (await _use(client, cid, RESTORATION, params={"points": "5"})).status_code == 200
    assert await _points(client, cid) == 10


# ---------------------------------------------------------------------------
# Metamagia: la scelta
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,count", [(1, None), (2, 2), (9, 2), (10, 4), (16, 4), (17, 6), (20, 6)])
async def test_metamagic_options_known_follow_the_level(client, level, count):
    pending = _pending(await _full(client, await _sorcerer24(client, level)))
    assert (pending["count"] if pending else None) == count


async def test_the_ten_options_are_offered_each_with_a_name_and_a_summary(client):
    choice = _pending(await _full(client, await _sorcerer24(client, 2)))
    assert {o["key"] for o in choice["options"]} == set(OPTIONS)
    assert all(o["name"]["it"] and o["name"]["en"] and 0 < len(o["summary"]["it"]) <= 200 for o in choice["options"])


async def test_each_chosen_option_becomes_a_row_and_one_can_be_replaced_at_any_level(client):
    cid = await _caster24(client, 2, "twinned", "quickened")
    keys = await _keys_of(client, cid)
    assert {TWINNED, QUICKENED} <= keys and not keys & {SUBTLE, DISTANT, EXTENDED, HEIGHTENED, EMPOWERED, CAREFUL, SEEKING, TRANSMUTED}
    klass = (await _full(client, cid))["classes"][0]
    state = (await client.get(f"/characters/{cid}/classes/{klass['id']}/options/metamagic")).json()
    assert state["replaceable"] is True and {o["key"] for o in state["chosen"]} == {"twinned", "quickened"}
    r = await client.post(f"/characters/{cid}/classes/{klass['id']}/options/replace",
                          json={"group": "metamagic", "old_key": "twinned", "new_key": "seeking"})
    assert r.status_code == 200, r.text
    assert SEEKING in await _keys_of(client, cid) and TWINNED not in await _keys_of(client, cid)


async def test_an_option_not_chosen_is_never_offered_at_the_cast(client):
    cid = await _caster24(client, 2, "subtle")
    spell = await _spell(client, cid, "Raggio di gelo", 0, attack_save="ATK")
    keys = await _roll_keys(client, cid, "cast", spell_id=spell)
    assert SUBTLE in keys and not set(keys) & {TWINNED, QUICKENED, DISTANT}


# ---------------------------------------------------------------------------
# Metamagia: costi e regola «una sola opzione per incantesimo»
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("option,key,cost,extra", [
    ("subtle", SUBTLE, 1, {"components": "V, S"}), ("distant", DISTANT, 1, {"range_area": "36 m"}),
    ("extended", EXTENDED, 1, {"duration": "1 ora"}), ("heightened", HEIGHTENED, 2, {"attack_save": "DEX"}),
    ("careful", CAREFUL, 1, {"attack_save": "DEX"}), ("quickened", QUICKENED, 2, {}),
    ("twinned", TWINNED, 1, {"srd_index": "charm-person"})])
async def test_each_cast_option_spends_the_points_of_the_2024_table(client, option, key, cost, extra):
    cid = await _caster24(client, 10, option)
    spell = await _spell(client, cid, "Prova", 1, **extra)
    assert key in await _roll_keys(client, cid, "cast", spell_id=spell)
    r = await _cast(client, cid, spell, key, slot_level=1)
    assert r.status_code == 200, r.text
    assert await _points(client, cid) == 10 - cost and r.json()["option_result"]["keys"] == [key]


async def test_a_second_cast_option_for_the_same_spell_is_refused_without_paying(client):
    cid = await _caster24(client, 6, "subtle", "distant")
    spell = await _spell(client, cid, "Dardo", 1, range_area="36 m", components="V, S")
    r = await _cast(client, cid, spell, SUBTLE, DISTANT, slot_level=1)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "option_unavailable" and await _points(client, cid) == 6


async def test_two_options_are_allowed_only_at_level_7_with_innate_sorcery_active(client):
    cid = await _caster24(client, 10, "subtle", "distant")
    spell = await _spell(client, cid, "Dardo", 1, range_area="36 m", components="V, S")
    assert (await _cast(client, cid, spell, SUBTLE, DISTANT, slot_level=1)).status_code == 409
    await _use(client, cid, INNATE)
    r = await _cast(client, cid, spell, SUBTLE, DISTANT, slot_level=1)
    assert r.status_code == 200, r.text
    assert await _points(client, cid) == 8 and set(r.json()["option_result"]["keys"]) == {SUBTLE, DISTANT}
    third = await _cast(client, cid, spell, SUBTLE, DISTANT, EXTENDED, slot_level=1)
    assert third.status_code == 409


async def test_below_level_7_innate_sorcery_does_not_allow_a_second_option(client):
    cid = await _caster24(client, 6, "subtle", "distant")
    await _use(client, cid, INNATE)
    spell = await _spell(client, cid, "Dardo", 1, range_area="36 m", components="V, S")
    assert (await _cast(client, cid, spell, SUBTLE, DISTANT, slot_level=1)).status_code == 409


async def test_an_option_is_not_offered_without_enough_points(client):
    cid = await _caster24(client, 10, "heightened")
    spell = await _spell(client, cid, "Ragnatela", 2, attack_save="DEX")
    await _set_points(client, cid, 1)
    assert HEIGHTENED not in await _roll_keys(client, cid, "cast", spell_id=spell)
    await _set_points(client, cid, 2)
    assert HEIGHTENED in await _roll_keys(client, cid, "cast", spell_id=spell)


# ---------------------------------------------------------------------------
# Apoteosi Arcana
# ---------------------------------------------------------------------------

async def test_arcane_apotheosis_makes_one_option_per_turn_free_with_innate_sorcery(client):
    cid = await _caster24(client, 20, "subtle", "distant")
    spell = await _spell(client, cid, "Dardo", 0, range_area="36 m", components="V, S")
    assert (await _cast(client, cid, spell, SUBTLE)).status_code == 200
    assert await _points(client, cid) == 19  # senza Innata attiva si paga
    await _use(client, cid, INNATE)
    await _new_turn(client, cid)
    assert (await _cast(client, cid, spell, SUBTLE)).status_code == 200
    assert await _points(client, cid) == 19  # gratuita
    assert (await _cast(client, cid, spell, DISTANT)).status_code == 200
    assert await _points(client, cid) == 18  # la seconda del turno costa
    await _new_turn(client, cid)
    assert (await _cast(client, cid, spell, DISTANT)).status_code == 200
    assert await _points(client, cid) == 18  # un turno nuovo, di nuovo gratuita


async def test_with_two_options_in_one_cast_only_the_first_is_free(client):
    cid = await _caster24(client, 20, "subtle", "distant")
    await _use(client, cid, INNATE)
    spell = await _spell(client, cid, "Dardo", 0, range_area="36 m", components="V, S")
    r = await _cast(client, cid, spell, SUBTLE, DISTANT)
    assert r.status_code == 200, r.text
    assert await _points(client, cid) == 19


# ---------------------------------------------------------------------------
# Le dieci opzioni
# ---------------------------------------------------------------------------

async def test_careful_spell_spares_as_many_creatures_as_the_charisma_modifier_and_says_no_damage(client):
    cid = await _caster24(client, 5, "careful", charisma=14)
    spell = await _spell(client, cid, "Palla di fuoco", 3, attack_save="DEX")
    r = await _cast(client, cid, spell, CAREFUL, slot_level=3)
    text = r.json()["option_result"]["effects"][0]
    assert "2 " in text["it"] and "nessun danno" in text["it"].lower() and "no damage" in text["en"].lower()


async def test_extended_spell_gives_advantage_on_the_saves_to_keep_that_concentration(client):
    cid = await _caster24(client, 6, "extended")
    spell = await _spell(client, cid, "Benedizione", 1, duration="Concentrazione, fino a 1 minuto", is_concentration=True)
    plain = await _spell(client, cid, "Scudo", 1, duration="Concentrazione, fino a 1 minuto", is_concentration=True)
    assert (await _cast(client, cid, plain, slot_level=1)).status_code == 200
    await _new_turn(client, cid)
    r = await client.post(f"/characters/{cid}/concentration/save", json={"damage": 10, "mode": "normal", "dice": [10]})
    assert r.json().get("mode_applied", r.json().get("mode")) == "normal"
    assert (await _cast(client, cid, spell, EXTENDED, slot_level=1)).status_code == 200
    assert (await _full(client, cid))["settings"]["concentration_rounds_left"] == 20
    r = await client.post(f"/characters/{cid}/concentration/save", json={"damage": 10, "mode": "normal", "dice": [10, 4]})
    assert r.json().get("mode_applied", r.json().get("mode")) == "advantage"


async def test_quickened_spell_is_refused_after_a_spell_of_level_1_or_more_this_turn_but_not_after_a_cantrip(client):
    cid = await _caster24(client, 6, "quickened")
    cantrip = await _spell(client, cid, "Luce", 0)
    spell = await _spell(client, cid, "Charme", 1)
    assert (await _cast(client, cid, cantrip)).status_code == 200
    assert QUICKENED in await _roll_keys(client, cid, "cast", spell_id=spell)
    assert (await _cast(client, cid, spell, QUICKENED, slot_level=1)).status_code == 200
    turn = await _turn(client, cid)
    assert turn["bonus_used"] is True and turn["action_used"] is False and await _points(client, cid) == 4
    await _new_turn(client, cid)
    assert (await _cast(client, cid, spell, slot_level=1)).status_code == 200
    other = await _spell(client, cid, "Altro", 1)
    assert QUICKENED not in await _roll_keys(client, cid, "cast", spell_id=other)
    r = await _cast(client, cid, other, QUICKENED, slot_level=1, **{})
    assert r.status_code == 409 and await _points(client, cid) == 4


async def test_seeking_spell_rerolls_the_d20_of_a_missed_spell_attack_for_one_point(client):
    cid = await _caster24(client, 6, "seeking")
    spell = await _spell(client, cid, "Raggio di gelo", 0, attack_save="ATK", damage_dice="1d8", damage_type="cold")
    await client.post(f"/characters/{cid}/spells/{spell}/attack", json={"die": 3})
    assert SEEKING in await _roll_keys(client, cid, "attack", spell_id=spell)
    r = await client.post(f"/characters/{cid}/last-roll/options", json={"options": [SEEKING], "mode": "normal", "dice": [17]})
    assert r.status_code == 200, r.text
    assert r.json()["die"] == 17 and await _points(client, cid) == 5


async def test_seeking_spell_combines_with_another_option_on_the_same_spell(client):
    cid = await _caster24(client, 6, "seeking", "subtle")
    spell = await _spell(client, cid, "Raggio", 0, attack_save="ATK", damage_dice="1d8", damage_type="cold", components="V, S")
    r = await client.post(f"/characters/{cid}/spells/{spell}/attack", json={"die": 3, "cast_options": [SUBTLE]})
    assert r.status_code == 200, r.text
    r = await client.post(f"/characters/{cid}/last-roll/options", json={"options": [SEEKING], "mode": "normal", "dice": [15]})
    assert r.status_code == 200 and await _points(client, cid) == 4


@pytest.mark.parametrize("original,offered", [("fire", True), ("thunder", True), ("poison", True), ("necrotic", False), ("force", False), (None, False)])
async def test_transmuted_spell_is_offered_only_when_the_damage_is_one_of_the_six(client, original, offered):
    cid = await _caster24(client, 6, "transmuted")
    spell = await _spell(client, cid, "Fiamma", 1, attack_save="DEX", damage_dice="2d6", **({"damage_type": original} if original else {}))
    keys = await _roll_keys(client, cid, "spell_damage", spell_id=spell)
    changes = [k for k in keys if k.startswith(TRANSMUTED)]
    assert bool(changes) == offered
    if offered:  # non verso il tipo che il danno già ha
        assert f"{TRANSMUTED}_{original}" not in changes and len(changes) == 5


async def test_transmuted_spell_changes_the_damage_type_in_the_result_for_one_point(client):
    cid = await _caster24(client, 6, "transmuted")
    spell = await _spell(client, cid, "Fiamma", 1, attack_save="DEX", damage_dice="2d6", damage_type="fire")
    result = await _damage(client, cid, spell, f"{TRANSMUTED}_cold", casting_level=1)
    assert result["damage_type"] == "cold" and result["parts"][0]["type"] == "cold" and await _points(client, cid) == 5


async def test_twinned_spell_is_offered_only_for_spells_that_gain_a_target_with_a_higher_slot(client):
    cid = await _caster24(client, 6, "twinned")
    ok = await _spell(client, cid, "Charme", 1, srd_index="charm-person")
    no = await _spell(client, cid, "Palla", 3, srd_index="fireball")
    assert TWINNED in await _roll_keys(client, cid, "cast", spell_id=ok) and TWINNED not in await _roll_keys(client, cid, "cast", spell_id=no)
    r = await _cast(client, cid, ok, TWINNED, slot_level=1)
    assert r.status_code == 200 and "2" in r.json()["option_result"]["effects"][0]["it"] and await _points(client, cid) == 5


async def test_empowered_spell_rerolls_up_to_the_charisma_modifier_dice_and_adds_to_another_option(client):
    cid = await _caster24(client, 6, "empowered", "careful", charisma=16)
    spell = await _spell(client, cid, "Palla di fuoco", 3, attack_save="DEX", damage_dice="8d6", damage_type="fire")
    assert (await _cast(client, cid, spell, CAREFUL, slot_level=3)).status_code == 200
    await _damage(client, cid, spell, casting_level=3, main_rolls=[1] * 8)
    option = next(o for o in (await client.get(f"/characters/{cid}/roll-options", params={"roll": "spell_damage", "spell_id": spell})).json()
                  if o["key"] == EMPOWERED)
    assert option["reroll_limit"] == 3 and option["cost"]["amount"] == 1
    r = await client.post(f"/characters/{cid}/last-damage/options", json={"options": [EMPOWERED], "option_inputs": {}, "reroll": [0, 1, 2, 3]})
    assert r.status_code == 409 and await _points(client, cid) == 5
    r = await client.post(f"/characters/{cid}/last-damage/options", json={"options": [EMPOWERED], "option_inputs": {}, "reroll": [0, 1, 2]})
    assert r.status_code == 200, r.text
    assert await _points(client, cid) == 4


async def test_metamagic_points_come_back_with_a_long_rest(client):
    cid = await _caster24(client, 5, "careful")
    spell = await _spell(client, cid, "Palla di fuoco", 2, attack_save="DEX")
    await _cast(client, cid, spell, CAREFUL, slot_level=2)
    assert await _points(client, cid) == 4
    await _rest(client, cid, "long")
    assert await _points(client, cid) == 5


# ---------------------------------------------------------------------------
# Multiclasse e importazione
# ---------------------------------------------------------------------------

async def test_multiclass_uses_the_multiclass_slot_table_and_prepares_per_class(client):
    cid = await _sorcerer24(client, 5)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "wizard", "level": 4})
    assert r.status_code in (200, 201), r.text
    full = await _full(client, cid)
    totals = tuple(s["total"] for s in sorted(full["spell_slots"], key=lambda s: s["level"]) if s["total"])
    assert totals == (4, 3, 3, 3, 1)  # incantatore 9
    limits = {c["class_name"]: c for c in full["spellcasting"]["limits"]}
    assert limits["sorcerer"]["prepared_limit"] == 9 and limits["wizard"]["prepared_limit"] == 7


async def test_beyond_metamagic_options_find_the_catalog_choices(test_session_factory):
    from api.routers.transfer import _apply_class_options
    from api.services.ddb_import import ImportReport
    from core.rules.sample_characters import build_rules_character

    async with test_session_factory() as s:
        spec = {"name": "x", "edition": "2024", "classes": [("Stregone", 10, None, 6)]}
        char = await build_rules_character(s, spec, 1)
        report = ImportReport()
        _apply_class_options(char, [{"class_index": 0, "name": n} for n in ("Careful Spell", "Seeking Spell", "Transmuted Spell", "Mystery")],
                             report, "it")
        assert char.classes[0].options == {"metamagic": ["careful", "seeking", "transmuted"]}
        assert [e.name for e in report.approximated] == ["Mystery"]
