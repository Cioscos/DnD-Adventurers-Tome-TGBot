"""Ranger 2024 (Task 38, parte A): tabelle, Nemico Prescelto con Hunter's Mark, Maestria nelle Armi, Esploratore Abile, Stile di
Combattimento e Guerriero Druidico, Vagabondo, Maestria, Instancabile, Cacciatore Implacabile, Velo della Natura, Cacciatore
Preciso, Sensi Ferini, Sterminatore di Nemici e multiclasse. Valori da ``docs/superpowers/rules/2024/classes/ranger.md``."""
from __future__ import annotations

import pytest

from core.rules.catalog import features_for
from core.rules.proficiencies import class_proficiencies
from tests.integration.rules.test_2014_bard import _ability, _choice, _full, _keys_of, _resolve, _skills, _sword, _use
from tests.integration.rules.test_2014_barbarian import _armor
from tests.integration.rules.test_2014_paladin import _new_turn, _rest, _turn
from tests.integration.rules.test_2014_paladin_combat import _attack, _listed, _slots
from tests.integration.rules.test_2024_paladin import _conditions

FE, TIRELESS, VEIL = "ranger.favored_enemy", "ranger.tireless", "ranger.natures_veil"
MARK, PRECISE = "ranger.hunters_mark_damage", "ranger.precise_hunter"
PREPARED = (2, 3, 4, 5, 6, 6, 7, 7, 9, 9, 10, 10, 11, 11, 12, 12, 14, 14, 15, 15)
SLOTS = {1: (2,), 2: (2,), 3: (3,), 5: (4, 2), 9: (4, 3, 2), 13: (4, 3, 3, 1), 17: (4, 3, 3, 3, 1), 19: (4, 3, 3, 3, 2)}
STYLES = {"archery", "blind_fighting", "defense", "dueling", "great_weapon", "interception", "protection", "thrown_weapon",
          "two_weapon", "unarmed", "druidic_warrior"}


async def _ranger24(client, level=5, **scores) -> int:
    body = {"name": "Ranger", "initial_class": {"class_name": "ranger", "level": level, "subclass": None}}
    r = await client.post("/characters", json=body)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    for ability, value in scores.items():
        r = await client.patch(f"/characters/{cid}/ability_scores/{ability}", json={"value": value})
        assert r.status_code == 200, r.text
    return cid


async def _spell_id(client, cid, index) -> int:
    return next(s["id"] for s in (await client.get(f"/characters/{cid}/spells")).json() if s["srd_index"] == index)


async def _cast_mark(client, cid):
    """Hunter's Mark con uno slot: la concentrazione è sul marchio."""
    r = await client.post(f"/characters/{cid}/spells/{await _spell_id(client, cid, 'hunters-mark')}/use", json={"slot_level": 1})
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# Tabelle, righe di sola regola, PF, competenze, livelli
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level", range(1, 21))
async def test_prepared_spells_follow_the_2024_table_and_there_are_no_cantrips(client, level):
    limits = (await _full(client, await _ranger24(client, level)))["spellcasting"]["limits"][0]
    assert (limits["cantrips_limit"] or 0, limits["prepared_limit"]) == (0, PREPARED[level - 1])


@pytest.mark.parametrize("level", sorted(SLOTS))
async def test_spell_slots_follow_the_half_caster_table_from_level_1(client, level):
    slots = tuple(s["total"] for s in sorted((await _full(client, await _ranger24(client, level)))["spell_slots"], key=lambda s: s["level"]))
    assert slots == SLOTS[level]


async def test_hit_points_use_the_d10(client):
    full = await _full(client, await _ranger24(client, 3))
    assert full["classes"][0]["hit_die"] == 10 and full["hit_points"] == 10 + 6 + 6


def test_class_and_multiclass_proficiencies():
    first = class_proficiencies("2024", "ranger", False)
    assert set(first.armor) == {"light", "medium", "shields"} and set(first.weapons) == {"simple", "martial"}
    assert set(first.saves) == {"strength", "dexterity"} and first.skills_count == 3
    assert set(first.skills_from) == {"animal_handling", "athletics", "insight", "investigation", "nature", "perception", "stealth", "survival"}
    multi = class_proficiencies("2024", "ranger", True)
    assert set(multi.armor) == {"light", "medium", "shields"} and multi.weapons == ("martial",)
    assert not multi.saves and multi.skills_count == 1


@pytest.mark.parametrize("level,asi", [(4, [4]), (16, [4, 8, 12, 16]), (19, [4, 8, 12, 16])])
async def test_asi_at_4_8_12_16_and_the_19th_is_an_epic_boon(client, level, asi):
    pending = (await _full(client, await _ranger24(client, level)))["pending_choices"]
    assert sorted(c["level"] for c in pending if c["kind"] == "asi") == asi
    assert any(c["kind"] == "epic_boon" for c in pending) == (level == 19)


async def test_rules_only_rows_stay_off_the_sheet(client):
    keys = await _keys_of(client, await _ranger24(client, 20))
    assert not keys & {"ranger.core_traits", "ranger.spellcasting", "ranger.ranger_subclass", "ranger.ability_score_improvement",
                       "ranger.epic_boon", "ranger.multiclassing", "ranger.equipment", "ranger.foe_slayer"}
    assert {FE, TIRELESS, VEIL, "ranger.extra_attack", "ranger.roving"} <= keys


@pytest.mark.parametrize("level,key", [(1, "favored_enemy"), (2, "deft_explorer"), (5, "extra_attack"), (6, "roving"), (9, "expertise"),
                                       (10, "tireless"), (13, "relentless_hunter"), (14, "natures_veil"), (17, "precise_hunter"),
                                       (18, "feral_senses"), (20, "foe_slayer")])
def test_a_row_appears_exactly_at_its_level(level, key):
    rows = {f.key: f for f in features_for("2024", "ranger")}
    assert rows[f"ranger.{key}"].level == level


def test_every_base_mapping_title_has_its_row_with_both_languages():
    titles = {f.source_title for f in features_for("2024", "ranger")}
    mapping = open("docs/superpowers/rules/mapping/2024/ranger.md", encoding="utf-8").read().splitlines()[4:]
    wanted = [line.split("|")[1].strip() for line in mapping if line.startswith("|")]
    base = [t for t in wanted if "(Ranger " in t or t.startswith("Multiclasse")]
    assert len(base) == 20 and [t for t in base if t not in titles] == []
    assert all(f.summary["it"] and f.summary["en"] and len(f.summary["it"]) <= 200 for f in features_for("2024", "ranger"))


# ---------------------------------------------------------------------------
# Nemico Prescelto e Hunter's Mark
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,uses", [(1, 2), (4, 2), (5, 3), (8, 3), (9, 4), (12, 4), (13, 5), (16, 5), (17, 6), (20, 6)])
async def test_favored_enemy_uses_follow_the_table(client, level, uses):
    row = await _ability(client, await _ranger24(client, level), FE)
    assert (row["max_uses"], row["uses"]) == (uses, uses) and row["restoration_type"] == "long_rest"


async def test_hunters_mark_is_always_prepared_outside_the_cap(client):
    cid = await _ranger24(client, 1)
    mark = next(s for s in (await client.get(f"/characters/{cid}/spells")).json() if s["srd_index"] == "hunters-mark")
    assert mark["always_prepared"] is True and mark["is_concentration"] is True and mark["casting_time"] == "1 azione bonus"
    limits = (await _full(client, cid))["spellcasting"]["limits"][0]
    assert limits["prepared_limit"] == 2 and limits["prepared_count"] == 0


async def test_the_free_cast_costs_a_use_the_bonus_action_and_no_slot_and_starts_the_concentration(client):
    cid = await _ranger24(client, 1)
    sid = await _spell_id(client, cid, "hunters-mark")
    r = await _use(client, cid, FE)
    assert r.status_code == 200, r.text
    assert (await _ability(client, cid, FE))["uses"] == 1
    r = await client.post(f"/characters/{cid}/spells/{sid}/use", json={"free_cast": True})
    assert r.status_code == 200, r.text
    full = await _full(client, cid)
    assert full["concentrating_spell_id"] == sid and await _slots(client, cid) == {1: 0}
    assert (await _turn(client, cid))["bonus_used"] is True
    again = await client.post(f"/characters/{cid}/spells/{sid}/use", json={"free_cast": True})
    assert again.status_code == 409 and again.json()["detail"]["code"] == "free_cast_unavailable"


async def test_the_free_cast_is_refused_without_the_use_and_the_normal_cast_still_costs_a_slot(client):
    cid = await _ranger24(client, 1)
    sid = await _spell_id(client, cid, "hunters-mark")
    r = await client.post(f"/characters/{cid}/spells/{sid}/use", json={"free_cast": True})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "free_cast_unavailable"
    await _cast_mark(client, cid)
    assert await _slots(client, cid) == {1: 1} and (await _ability(client, cid, FE))["uses"] == 2


async def test_the_use_is_refused_when_none_are_left_or_the_bonus_action_is_spent_or_one_is_pending_and_a_long_rest_returns_them(client):
    cid = await _ranger24(client, 1)
    sid = await _spell_id(client, cid, "hunters-mark")
    for _ in range(2):
        assert (await _use(client, cid, FE)).status_code == 200
        assert (await _use(client, cid, FE)).status_code == 409  # l'autorizzazione è già data: nessun uso a vuoto
        assert (await client.post(f"/characters/{cid}/spells/{sid}/use", json={"free_cast": True})).status_code == 200
        assert (await _use(client, cid, FE)).status_code == 409  # l'azione bonus è spesa
        await _new_turn(client, cid)
    r = await _use(client, cid, FE)
    assert r.status_code == 409 and (await _ability(client, cid, FE))["uses"] == 0
    await _rest(client, cid, "long")
    assert (await _ability(client, cid, FE))["uses"] == 2
    await client.post(f"/characters/{cid}/turn/use", json={"slot": "bonus", "used": True})
    assert (await _use(client, cid, FE)).status_code == 409
    assert (await _ability(client, cid, FE))["uses"] == 2


async def test_hunters_mark_adds_a_die_only_while_concentrating_on_it_d6_then_d10_at_level_20(client):
    cid = await _ranger24(client, 19)
    wid = await _sword(client, cid)
    assert MARK not in [o["key"] for o in await _listed(client, cid, wid)]
    await _cast_mark(client, cid)
    assert next(o for o in await _listed(client, cid, wid) if o["key"] == MARK)["dice"] == "1d6"
    body = await _attack(client, cid, wid, options=[MARK])
    block = body.json()["option_result"]
    assert len(block["extra_rolls"]) == 1 and 1 <= block["extra_rolls"][0] <= 6
    top = await _ranger24(client, 20)
    wid = await _sword(client, top)
    await _cast_mark(client, top)
    assert next(o for o in await _listed(client, top, wid) if o["key"] == MARK)["dice"] == "1d10"


# ---------------------------------------------------------------------------
# Maestria nelle Armi, Esploratore Abile, Stile di Combattimento, Guerriero Druidico
# ---------------------------------------------------------------------------

async def test_weapon_mastery_is_a_choice_of_two_kinds_from_level_1(client):
    choice = _choice(await _full(client, await _ranger24(client, 1)), "weapon_mastery")
    assert choice["count"] == 2 and choice["options"]


async def test_deft_explorer_asks_for_one_expertise_among_proficient_skills_and_two_languages_at_level_2(client):
    cid = await _ranger24(client, 1)
    assert _choice(await _full(client, cid), "deft_explorer_expertise") is None
    cid = await _ranger24(client, 2)
    await _skills(client, cid, nature=True, stealth=True, survival="expert")
    full = await _full(client, cid)
    expertise, languages = _choice(full, "deft_explorer_expertise"), _choice(full, "deft_explorer_languages")
    assert expertise["count"] == 1 and {o["key"] for o in expertise["options"]} == {"nature", "stealth"}
    assert languages["count"] == 2 and languages["options"]
    assert (await _resolve(client, cid, "deft_explorer_expertise", ["nature"])).status_code == 200
    assert (await _full(client, cid))["skills"]["nature"] == "expert"
    pick = [o["key"] for o in languages["options"][:2]]
    assert (await _resolve(client, cid, "deft_explorer_languages", pick)).status_code == 200
    from core.rules.catalog.y2014.cleric import LANGUAGES
    assert {lang.lower() for lang in (await _full(client, cid))["languages"]} >= {LANGUAGES[p][0].lower() for p in pick}


async def test_the_fighting_style_is_chosen_at_level_2_among_ten_styles_and_druidic_warrior(client):
    assert _choice(await _full(client, await _ranger24(client, 1)), "fighting_style") is None
    choice = _choice(await _full(client, await _ranger24(client, 2)), "fighting_style")
    assert choice["count"] == 1 and {o["key"] for o in choice["options"]} == STYLES
    assert all(o["name"]["it"] and o["name"]["en"] and o["summary"]["it"] for o in choice["options"])


async def test_the_style_rows_belong_to_the_ranger_and_a_chosen_style_works(client):
    keys = {f.key for f in features_for("2024", "ranger")}
    assert {"ranger.style_defense", "ranger.style_interception", "ranger.style_druidic_warrior"} <= keys
    assert not any(k.startswith(("fighter.", "paladin.")) for k in keys)
    assert all(m.source.startswith("feature:ranger.") for f in features_for("2024", "ranger") for m in f.modifiers
               if f.key.startswith("ranger.style_"))
    cid = await _ranger24(client, 2)
    assert (await _resolve(client, cid, "fighting_style", ["unarmed"])).status_code == 200
    assert "ranger.style_unarmed" in await _keys_of(client, cid)


async def test_druidic_warrior_asks_for_two_druid_cantrips_outside_the_limit(client):
    cid = await _ranger24(client, 2)
    assert (await _resolve(client, cid, "fighting_style", ["druidic_warrior"])).status_code == 200
    pick = _choice(await _full(client, cid), "druidic_warrior_cantrip")
    assert pick["count"] == 2 and pick["spell_pick"]["list"] == "druid" and pick["spell_pick"]["max_level"] == 0
    assert pick["spell_pick"]["free"] is True


# ---------------------------------------------------------------------------
# Attacco Extra, Vagabondo, Maestria
# ---------------------------------------------------------------------------

def test_extra_attack_gives_two_attacks_from_level_5_and_no_more():
    rows = [f for f in features_for("2024", "ranger") if f.attacks_per_action]
    assert [(f.key, f.level, f.attacks_per_action) for f in rows] == [("ranger.extra_attack", 5, 2)]


@pytest.mark.parametrize("level,speed,climb", [(5, 30, None), (6, 40, 40), (20, 40, 40)])
async def test_roving_adds_ten_feet_and_gives_climb_and_swim_equal_to_the_speed(client, level, speed, climb):
    computed = (await _full(client, await _ranger24(client, level)))["computed"]
    assert (computed["speed"], computed["climb_speed"], computed["swim_speed"]) == (speed, climb, climb)


async def test_roving_loses_the_ten_feet_in_heavy_armor_but_keeps_climb_and_swim(client):
    cid = await _ranger24(client, 6, strength=18)
    await _armor(client, cid, "heavy")
    computed = (await _full(client, cid))["computed"]
    assert (computed["speed"], computed["climb_speed"], computed["swim_speed"]) == (30, 30, 30)


async def test_expertise_at_level_9_asks_for_two_proficient_skills_without_expertise(client):
    cid = await _ranger24(client, 9)
    await _skills(client, cid, nature=True, stealth=True, survival=True, perception="expert")
    choice = _choice(await _full(client, cid), "expertise")
    assert choice["count"] == 2 and {o["key"] for o in choice["options"]} == {"nature", "stealth", "survival"}
    assert (await _resolve(client, cid, "expertise", ["nature", "stealth"])).status_code == 200
    skills = (await _full(client, cid))["skills"]
    assert skills["nature"] == skills["stealth"] == "expert" and skills["survival"] is True


# ---------------------------------------------------------------------------
# Instancabile
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("wisdom,uses", [(8, 1), (10, 1), (14, 2), (20, 5)])
async def test_tireless_uses_equal_the_wisdom_modifier_with_a_minimum_of_one(client, wisdom, uses):
    row = await _ability(client, await _ranger24(client, 10, wisdom=wisdom), TIRELESS)
    assert (row["max_uses"], row["restoration_type"]) == (uses, "long_rest")


async def test_tireless_uses_follow_a_wisdom_change(client):
    cid = await _ranger24(client, 10, wisdom=14)
    assert (await _ability(client, cid, TIRELESS))["max_uses"] == 2
    r = await client.patch(f"/characters/{cid}/ability_scores/wisdom", json={"value": 18})
    assert r.status_code == 200
    assert (await _ability(client, cid, TIRELESS))["max_uses"] == 4


@pytest.mark.parametrize("wisdom,mod", [(16, 3), (8, -1)])
async def test_tireless_gives_temporary_hit_points_of_1d8_plus_wisdom_minimum_one_with_the_magic_action(client, wisdom, mod):
    cid = await _ranger24(client, 10, wisdom=wisdom)
    r = await _use(client, cid, TIRELESS)
    assert r.status_code == 200, r.text
    full = await _full(client, cid)
    assert 1 <= full["temp_hp"] <= 8 + mod and full["temp_hp"] >= max(1, 1 + mod)
    assert (await _turn(client, cid))["action_used"] is True
    assert (await _use(client, cid, TIRELESS)).status_code == 409  # l'azione è spesa


async def test_a_short_rest_lowers_exhaustion_by_one_for_a_level_10_ranger_only(client):
    late, early = await _ranger24(client, 10), await _ranger24(client, 9)
    for cid in (late, early):
        await _conditions(client, cid, exhaustion=3)
        await _rest(client, cid, "short")
    assert (await _full(client, late))["conditions"]["exhaustion"] == 2
    assert (await _full(client, early))["conditions"]["exhaustion"] == 3
    preview = (await client.get(f"/characters/{late}/rest/preview", params={"rest_type": "short"})).json()
    assert preview["exhaustion_change"] == -1


async def test_a_long_rest_lowers_exhaustion_only_once_and_returns_the_uses(client):
    cid = await _ranger24(client, 10)
    await _conditions(client, cid, exhaustion=3)
    await _use(client, cid, TIRELESS)
    await _rest(client, cid, "long")
    assert (await _full(client, cid))["conditions"]["exhaustion"] == 2
    assert (await _ability(client, cid, TIRELESS))["uses"] == (await _ability(client, cid, TIRELESS))["max_uses"]


# ---------------------------------------------------------------------------
# Cacciatore Implacabile, Velo della Natura, Cacciatore Preciso, Sensi Ferini
# ---------------------------------------------------------------------------

async def _hit(client, cid, damage=6):
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": damage})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.parametrize("level,asked", [(12, True), (13, False)])
async def test_relentless_hunter_skips_the_concentration_save_on_hunters_mark(client, level, asked):
    cid = await _ranger24(client, level)
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 60})
    await _cast_mark(client, cid)
    assert ((await _hit(client, cid)).get("concentration_save") is not None) == asked


async def test_relentless_hunter_does_not_protect_another_concentration_spell(client):
    cid = await _ranger24(client, 13)
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 60})
    spell = await client.post(f"/characters/{cid}/spells", json={"name": "Benedizione", "level": 1, "is_concentration": True,
                                                                  "is_prepared": True, "srd_index": "bless"})
    assert spell.status_code == 201, spell.text
    r = await client.post(f"/characters/{cid}/spells/{spell.json()['id']}/use", json={"slot_level": 1})
    assert r.status_code == 200, r.text
    assert (await _hit(client, cid)).get("concentration_save") is not None


@pytest.mark.parametrize("wisdom,uses", [(8, 1), (16, 3)])
async def test_natures_veil_makes_you_invisible_until_the_end_of_the_next_turn_and_uses_follow_wisdom(client, wisdom, uses):
    cid = await _ranger24(client, 14, wisdom=wisdom)
    assert (await _ability(client, cid, VEIL))["max_uses"] == uses
    r = await _use(client, cid, VEIL)
    assert r.status_code == 200, r.text
    assert (await _full(client, cid))["conditions"].get("invisible") is True
    assert (await _turn(client, cid))["bonus_used"] is True and (await _ability(client, cid, VEIL))["uses"] == uses - 1
    await _new_turn(client, cid)
    assert (await _full(client, cid))["conditions"].get("invisible") is True  # il prossimo turno non l'ha ancora chiuso
    await _new_turn(client, cid)
    assert not (await _full(client, cid))["conditions"].get("invisible")


async def test_natures_veil_needs_the_bonus_action_and_a_long_rest_returns_the_uses(client):
    cid = await _ranger24(client, 14, wisdom=8)
    assert (await _use(client, cid, VEIL)).status_code == 200
    await _new_turn(client, cid)
    assert (await _use(client, cid, VEIL)).status_code == 409
    await _rest(client, cid, "long")
    assert (await _ability(client, cid, VEIL))["uses"] == 1


async def test_precise_hunter_offers_advantage_on_the_marked_creature_only_from_level_17_while_concentrating(client):
    low, high = await _ranger24(client, 16), await _ranger24(client, 17)
    for cid in (low, high):
        wid = await _sword(client, cid)
        assert PRECISE not in [o["key"] for o in await _listed(client, cid, wid)]
        await _cast_mark(client, cid)
    assert PRECISE not in [o["key"] for o in await _listed(client, low, await _sword(client, low))]
    option = next(o for o in await _listed(client, high, await _sword(client, high)) if o["key"] == PRECISE)
    assert option["mode"] == "advantage"


async def test_feral_senses_give_blindsight_to_thirty_feet_from_level_18(client):
    assert (await _full(client, await _ranger24(client, 17)))["computed"]["senses"] == []
    assert (await _full(client, await _ranger24(client, 18)))["computed"]["senses"] == [{"type": "blindsight", "range_ft": 30}]


# ---------------------------------------------------------------------------
# Multiclasse e passaggio dal 2014
# ---------------------------------------------------------------------------

async def test_multiclass_slots_count_half_the_ranger_levels_rounded_up(client):
    cid = await _ranger24(client, 3)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "cleric", "level": 3, "hit_die": 8})
    assert r.status_code == 201, r.text
    slots = tuple(s["total"] for s in sorted((await _full(client, cid))["spell_slots"], key=lambda s: s["level"]))
    assert slots == (4, 3, 2)  # 2 (3 per eccesso, la metà) + 3 = livello 5


async def test_a_2014_ranger_that_becomes_2024_gets_the_2024_rows_and_keeps_its_spent_uses(client):
    r = await client.post("/characters", json={"name": "Vecchio", "initial_class": {"class_name": "ranger", "level": 10, "subclass": None}})
    cid = r.json()["id"]
    assert "ranger.natural_explorer" in await _keys_of(client, cid)
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    keys = await _keys_of(client, cid)
    assert {FE, TIRELESS} <= keys and "ranger.natural_explorer" not in keys and "ranger.primeval_awareness" not in keys
    assert (await _ability(client, cid, FE))["max_uses"] == 4
