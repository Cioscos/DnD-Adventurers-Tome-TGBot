"""Paladino 2014 (Task 25): progressione, Percezione del Divino, Imposizione delle Mani, Incanalare Divinità, Attacco Extra,
Tocco Purificatore, competenze, PF, incantesimi e righe di sola regola."""
from __future__ import annotations

import pytest

from core.db.models import Character
from core.rules.catalog import features_for
from core.rules.proficiencies import class_proficiencies
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, seed_session
from tests.integration.rules.test_2014_bard import _ability, _full, _keys_of, _roll_keys, _states, _use

OATHS = {"devotion": "Giuramento di Devozione", "ancients": "Giuramento degli Antichi", "vengeance": "Giuramento di Vendetta"}
DS, LOH, CD, CT = "paladin.divine_sense", "paladin.lay_on_hands", "paladin.channel_divinity", "paladin.cleansing_touch"


async def _paladin(client, level=5, oath=None, **scores) -> int:
    body = {"name": "Paladino", "initial_class": {"class_name": "paladin", "level": level, "subclass": OATHS.get(oath)}}
    r = await client.post("/characters", json=body)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    for ability, value in scores.items():
        r = await client.patch(f"/characters/{cid}/ability_scores/{ability}", json={"value": value})
        assert r.status_code == 200, r.text
    return cid


async def _turn(client, cid) -> dict:
    return (await client.get(f"/characters/{cid}/turn-state")).json()["turn"]


async def _hurt(factory, cid, hp) -> None:
    async with factory() as s:
        char = await s.get(Character, cid)
        char.current_hit_points = hp
        await s.commit()


async def _hp(client, cid) -> int:
    return (await _full(client, cid))["current_hit_points"]


async def _rest(client, cid, kind) -> None:
    r = await client.post(f"/characters/{cid}/rest", json={"rest_type": kind, "confirm_early": True})
    assert r.status_code == 200, r.text


async def _new_turn(client, cid) -> None:
    r = await client.post(f"/characters/{cid}/turn/new")
    assert r.status_code == 200, r.text


def _on(full: dict, key: str) -> bool:
    return any(s["key"] == key for s in full["active_states"])


# ---------------------------------------------------------------------------
# Progressione, PF, competenze, incantesimi
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,slots", [
    (2, {1: 2}), (3, {1: 3}), (5, {1: 4, 2: 2}), (9, {1: 4, 2: 3, 3: 2}), (13, {1: 4, 2: 3, 3: 3, 4: 1}),
    (17, {1: 4, 2: 3, 3: 3, 4: 3, 5: 1}), (19, {1: 4, 2: 3, 3: 3, 4: 3, 5: 2}), (20, {1: 4, 2: 3, 3: 3, 4: 3, 5: 2})])
async def test_slots_follow_the_half_caster_table(client, level, slots):
    cid = await _paladin(client, level)
    assert {s["level"]: s["total"] for s in (await _full(client, cid))["spell_slots"]} == slots


async def test_a_level_1_paladin_has_no_spell_slots_and_a_level_2_one_has_two(client):
    assert (await _full(client, await _paladin(client, 1)))["spell_slots"] == []
    slots = (await _full(client, await _paladin(client, 2)))["spell_slots"]
    assert {s["level"]: s["total"] for s in slots} == {1: 2}


@pytest.mark.parametrize("level,charisma,cap", [(2, 16, 4), (5, 16, 5), (5, 8, 1), (3, 10, 1), (20, 18, 14)])
async def test_prepared_spells_are_charisma_plus_half_the_level_with_a_minimum_of_one(client, level, charisma, cap):
    cid = await _paladin(client, level, charisma=charisma)
    assert (await _full(client, cid))["spellcasting"]["prepared_cap"] == cap


async def test_spell_dc_and_attack_use_charisma(client):
    cid = await _paladin(client, 5, charisma=16)  # competenza +3, Carisma +3
    (stats,) = (await _full(client, cid))["spellcasting"]["casters"]
    assert (stats["ability"], stats["save_dc"], stats["attack_bonus"]) == ("charisma", 8 + 3 + 3, 3 + 3)


async def test_hit_points_use_the_d10_and_follow_constitution(client):
    cid = await _paladin(client, 3)
    full = await _full(client, cid)
    assert full["classes"][0]["hit_die"] == 10
    assert full["hit_points"] == 10 + 6 + 6  # 10 + COS al 1°, poi la media 6 (COS 10)


def test_class_proficiencies_first_class_and_multiclass():
    first = class_proficiencies("2014", "paladin", False)
    assert set(first.armor) == {"light", "medium", "heavy", "shields"} and set(first.weapons) == {"simple", "martial"}
    assert set(first.saves) == {"wisdom", "charisma"} and first.skills_count == 2
    assert set(first.skills_from) == {"athletics", "insight", "intimidation", "medicine", "persuasion", "religion"}
    multi = class_proficiencies("2014", "paladin", True)
    assert set(multi.armor) == {"light", "medium", "shields"} and set(multi.weapons) == {"simple", "martial"} and not multi.saves


def test_extra_attack_is_two_attacks_from_level_5_and_does_not_grow():
    extra = [f for f in features_for("2014", "paladin") if f.attacks_per_action]
    assert [(f.level, f.attacks_per_action) for f in extra] == [(5, 2)]


async def test_attacks_allowed_follow_extra_attack_and_the_best_class_wins(client):
    assert (await client.get(f"/characters/{await _paladin(client, 4)}/turn-state")).json()["attacks_allowed"] == 1
    assert (await client.get(f"/characters/{await _paladin(client, 5)}/turn-state")).json()["attacks_allowed"] == 2
    fighter = await _paladin(client, 5)
    r = await client.post(f"/characters/{fighter}/classes", json={"class_name": "fighter", "level": 5, "hit_die": 10})
    assert r.status_code == 201, r.text
    assert (await client.get(f"/characters/{fighter}/turn-state")).json()["attacks_allowed"] == 2  # non si somma


async def test_rules_only_rows_do_not_clutter_the_sheet(client):
    keys = await _keys_of(client, await _paladin(client, 20, "devotion"))
    assert not keys & {f"paladin.{k}" for k in (
        "hit_points", "proficiencies", "equipment", "fighting_style", "spellcasting", "sacred_oath",
        "ability_score_improvement", "multiclassing", "devotion_spells_5", "devotion_spells_17")}


@pytest.mark.parametrize("level,pending", [(3, 0), (4, 1), (6, 1), (8, 2), (11, 2), (12, 3), (14, 3), (16, 4), (18, 4), (19, 5), (20, 5)])
async def test_asi_choices_are_pending_at_levels_4_8_12_16_and_19_only(client, level, pending):
    full = await _full(client, await _paladin(client, level))
    assert len([c for c in full["pending_choices"] if c.get("kind") == "asi"]) == pending


# ---------------------------------------------------------------------------
# Percezione del Divino
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("charisma,uses", [(16, 4), (10, 1), (8, 1), (20, 6)])
async def test_divine_sense_uses_are_one_plus_charisma_with_a_minimum_of_one(client, charisma, uses):
    row = await _ability(client, await _paladin(client, 1, charisma=charisma), DS)
    assert (row["max_uses"], row["uses"], row["restoration_type"]) == (uses, uses, "long_rest")


async def test_divine_sense_follows_a_charisma_change(client):
    cid = await _paladin(client, 3, charisma=10)
    assert (await _ability(client, cid, DS))["max_uses"] == 1
    await client.patch(f"/characters/{cid}/ability_scores/charisma", json={"value": 18})
    assert (await _ability(client, cid, DS))["max_uses"] == 5


async def test_divine_sense_is_an_action_that_spends_a_use_and_lasts_to_the_end_of_the_next_turn(client):
    cid = await _paladin(client, 1, charisma=14)
    r = await _use(client, cid, DS)
    assert r.status_code == 200, r.text
    assert (await _ability(client, cid, DS))["uses"] == 2 and (await _turn(client, cid))["action_used"] is True
    assert _on(await _full(client, cid), "divine_sense")
    again = await _use(client, cid, DS)
    assert again.status_code == 409 and again.json()["detail"]["code"] == "turn_slot_used"
    await _new_turn(client, cid)
    assert _on(await _full(client, cid), "divine_sense")  # vale fino alla fine del turno che segue
    await _new_turn(client, cid)
    assert not _on(await _full(client, cid), "divine_sense")


async def test_divine_sense_says_the_range_and_comes_back_with_a_long_rest(client):
    cid = await _paladin(client, 1, charisma=14)
    state = (await _use(client, cid, DS)).json()["state"]
    assert state["data"]["range_m"] == 18
    await _rest(client, cid, "short")
    assert (await _ability(client, cid, DS))["uses"] == 2
    await _rest(client, cid, "long")
    assert (await _ability(client, cid, DS))["uses"] == 3


async def test_divine_sense_without_uses_is_refused_before_the_action_is_spent(client):
    cid = await _paladin(client, 1, charisma=10)
    assert (await _use(client, cid, DS)).status_code == 200
    await client.post(f"/characters/{cid}/turn/use", json={"slot": "action", "used": False})
    r = await _use(client, cid, DS)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_uses"
    assert (await _turn(client, cid))["action_used"] is False


# ---------------------------------------------------------------------------
# Imposizione delle Mani
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,pool", [(1, 5), (2, 10), (7, 35), (20, 100)])
async def test_lay_on_hands_pool_is_five_times_the_level(client, level, pool):
    row = await _ability(client, await _paladin(client, level), LOH)
    assert (row["max_uses"], row["uses"], row["restoration_type"]) == (pool, pool, "long_rest")
    assert row["has_on_use"] and row["choose_amount"] and row["action_type"] == "action"


async def test_lay_on_hands_heals_the_paladin_by_the_amount_spent(client, test_session_factory):
    cid = await _paladin(client, 5)
    await _hurt(test_session_factory, cid, 10)
    r = await _use(client, cid, LOH, amount=7, params={"mode": "self"})
    assert r.status_code == 200, r.text
    assert r.json()["healed"] == 7 and await _hp(client, cid) == 17
    assert (await _ability(client, cid, LOH))["uses"] == 25 - 7 and (await _turn(client, cid))["action_used"] is True


async def test_lay_on_hands_on_another_creature_only_spends_the_pool(client, test_session_factory):
    cid = await _paladin(client, 5)
    await _hurt(test_session_factory, cid, 10)
    r = await _use(client, cid, LOH, amount=8, params={"mode": "other"})
    assert r.status_code == 200, r.text
    assert r.json()["healed"] == 0 and await _hp(client, cid) == 10 and (await _ability(client, cid, LOH))["uses"] == 17


async def test_lay_on_hands_cures_one_disease_or_poison_per_five_points_and_heals_nothing(client, test_session_factory):
    cid = await _paladin(client, 5)
    await _hurt(test_session_factory, cid, 10)
    await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"poisoned": True}})  # una condizione assente non costa
    r = await _use(client, cid, LOH, amount=1, params=_cure(["poisoned", "disease"]))  # due voci: dieci punti
    assert r.status_code == 200, r.text
    assert r.json()["healed"] == 0 and await _hp(client, cid) == 10 and (await _ability(client, cid, LOH))["uses"] == 15


def _cure(conditions) -> dict:
    """Task 48: stesso corpo `removal` degli incantesimi; il server calcola il costo (5 punti per voce)."""
    return {"mode": "cure", "removal": {"targets": ["self"], "conditions": conditions}}


@pytest.mark.parametrize("amount", [1, 4, 6, 12])
async def test_lay_on_hands_cure_costs_five_per_item_whatever_amount_is_sent(client, amount):
    cid = await _paladin(client, 5)
    r = await _use(client, cid, LOH, amount=amount, params=_cure(["disease"]))
    assert r.status_code == 200 and (await _ability(client, cid, LOH))["uses"] == 20 and (await _turn(client, cid))["action_used"] is True


async def test_lay_on_hands_needs_a_known_mode_and_enough_points(client):
    cid = await _paladin(client, 2)  # riserva 10
    assert (await _use(client, cid, LOH, amount=3)).status_code == 422
    assert (await _use(client, cid, LOH, amount=3, params={"mode": "elsewhere"})).status_code == 422
    r = await _use(client, cid, LOH, amount=11, params={"mode": "self"})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_uses"
    assert (await _ability(client, cid, LOH))["uses"] == 10 and (await _turn(client, cid))["action_used"] is False


async def test_lay_on_hands_returns_with_a_long_rest_and_not_a_short_one(client):
    cid = await _paladin(client, 5)
    await _use(client, cid, LOH, amount=10, params={"mode": "other"})
    await _rest(client, cid, "short")
    assert (await _ability(client, cid, LOH))["uses"] == 15
    await _rest(client, cid, "long")
    assert (await _ability(client, cid, LOH))["uses"] == 25


async def test_lay_on_hands_pool_follows_a_level_change_and_keeps_the_legacy_key(client):
    cid = await _paladin(client, 3)
    klass = (await _full(client, cid))["classes"][0]
    await client.patch(f"/characters/{cid}/classes/{klass['id']}", json={"level": 4})
    assert (await _ability(client, cid, LOH))["max_uses"] == 20


# ---------------------------------------------------------------------------
# Incanalare Divinità
# ---------------------------------------------------------------------------

async def test_channel_divinity_starts_at_level_3_with_one_use_for_a_short_rest(client):
    assert CD not in await _keys_of(client, await _paladin(client, 2))
    cid = await _paladin(client, 3, "devotion")
    row = await _ability(client, cid, CD)
    assert (row["max_uses"], row["restoration_type"], row["has_on_use"]) == (1, "short_rest", False)
    assert (await _ability(client, await _paladin(client, 20, "vengeance"), CD))["max_uses"] == 1  # non scala


async def _paladin_cleric(client, cleric_level) -> int:
    cid = await _paladin(client, 3, "devotion")
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "cleric", "level": cleric_level, "hit_die": 8})
    assert r.status_code == 201, r.text
    return cid


async def _channel_rows(client, cid) -> dict[str, tuple[int, int]]:
    return {a["feature_key"]: (a["uses"], a["max_uses"]) for a in (await _full(client, cid))["abilities"]
            if a["feature_key"] in (CD, "cleric.channel_divinity")}


async def test_a_second_class_with_channel_divinity_adds_no_use_and_both_effects_spend_the_same_one(client):
    cid = await _paladin_cleric(client, 2)
    assert await _channel_rows(client, cid) == {CD: (1, 1)}  # a parità tiene la riga la prima classe
    assert (await _use(client, cid, "cleric.turn_undead")).status_code == 200
    assert await _channel_rows(client, cid) == {CD: (0, 1)}
    await client.post(f"/characters/{cid}/turn/use", json={"slot": "action", "used": False})
    r = await _use(client, cid, "paladin.turn_the_unholy")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_uses"
    await _rest(client, cid, "short")
    assert await _channel_rows(client, cid) == {CD: (1, 1)}


async def test_the_class_that_gives_more_uses_holds_the_pool_and_the_oath_option_spends_it(client):
    cid = await _paladin_cleric(client, 6)
    assert await _channel_rows(client, cid) == {"cleric.channel_divinity": (2, 2)}
    assert (await _use(client, cid, "paladin.turn_the_unholy")).status_code == 200
    assert await _channel_rows(client, cid) == {"cleric.channel_divinity": (1, 2)}
    row = next(a for a in (await _full(client, cid))["abilities"] if a["feature_key"] == "paladin.turn_the_unholy")
    assert row["spends_left"] == 1


async def test_short_rest_returns_the_channel_divinity_use(client):
    cid = await _paladin(client, 3, "devotion")
    await _use(client, cid, "paladin.turn_the_unholy")
    assert (await _ability(client, cid, CD))["uses"] == 0
    await _rest(client, cid, "short")
    assert (await _ability(client, cid, CD))["uses"] == 1


# ---------------------------------------------------------------------------
# Tocco Purificatore
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("charisma,uses", [(10, 1), (8, 1), (16, 3), (20, 5)])
async def test_cleansing_touch_uses_are_charisma_with_a_minimum_of_one(client, charisma, uses):
    row = await _ability(client, await _paladin(client, 14, charisma=charisma), CT)
    assert (row["max_uses"], row["restoration_type"], row["action_type"]) == (uses, "long_rest", "action")


async def test_cleansing_touch_is_not_there_before_level_14(client):
    assert CT not in await _keys_of(client, await _paladin(client, 13))


async def test_cleansing_touch_ends_a_condition_on_the_paladin_when_asked(client):
    cid = await _paladin(client, 14, charisma=14)
    await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"charmed": True}})
    full = await _full(client, cid)
    row = next(a for a in full["abilities"] if a["feature_key"] == CT)
    assert [o["key"] for o in row["removal"]["conditions"]] == ["charmed"] and row["removal"]["optional"]
    r = await _use(client, cid, CT, params={"removal": {"targets": ["self"], "conditions": ["charmed"]}})
    assert r.status_code == 200, r.text
    assert not (await _full(client, cid))["conditions"].get("charmed")
    assert (await _ability(client, cid, CT))["uses"] == 1 and (await _turn(client, cid))["action_used"] is True


async def test_cleansing_touch_on_another_creature_spends_a_use_and_the_action_only(client):
    cid = await _paladin(client, 14, charisma=14)
    r = await _use(client, cid, CT)
    assert r.status_code == 200, r.text
    assert (await _ability(client, cid, CT))["uses"] == 1 and (await _turn(client, cid))["action_used"] is True


async def test_cleansing_touch_refuses_a_condition_the_paladin_does_not_have(client):
    cid = await _paladin(client, 14, charisma=14)
    r = await _use(client, cid, CT, params={"removal": {"targets": ["self"], "conditions": ["charmed"]}})
    assert r.status_code == 422
    assert (await _ability(client, cid, CT))["uses"] == 2 and (await _turn(client, cid))["action_used"] is False


# ---------------------------------------------------------------------------
# Salute Divina e Giuramento Sacro
# ---------------------------------------------------------------------------

def test_divine_health_is_a_passive_row_from_level_3():
    row = next(f for f in features_for("2014", "paladin") if f.key == "paladin.divine_health")
    assert (row.level, row.passive) == (3, True) and row.summary["it"] and row.summary["en"]


async def test_the_oath_features_need_a_recognised_oath(client):
    keys = {o: await _keys_of(client, await _paladin(client, 20, o)) for o in (*OATHS, None)}
    assert "paladin.sacred_weapon" in keys["devotion"] and "paladin.sacred_weapon" not in keys["ancients"]
    assert "paladin.natures_wrath" in keys["ancients"] and "paladin.natures_wrath" not in keys["vengeance"]
    assert "paladin.vow_of_enmity" in keys["vengeance"] and "paladin.vow_of_enmity" not in keys["devotion"]
    assert not {k for k in keys[None] if k.split(".")[1] in ("sacred_weapon", "natures_wrath", "vow_of_enmity", "holy_nimbus")}
    assert CD in keys[None]  # il pozzo c'è anche senza giuramento riconosciuto


async def test_spent_points_of_the_legacy_keys_survive_the_catalog_and_a_level_up(client):
    cid = await _paladin(client, 5)
    await _use(client, cid, LOH, amount=10, params={"mode": "other"})
    klass = (await _full(client, cid))["classes"][0]
    await client.patch(f"/characters/{cid}/classes/{klass['id']}", json={"level": 6})
    row = await _ability(client, cid, LOH)
    assert (row["max_uses"], row["uses"]) == (30, 20)  # la chiave è quella di prima: gli usi spesi restano


async def test_a_paladin_without_a_style_yet_can_still_pick_it_after_the_catalog_arrives(client):
    cid = await _paladin(client, 6, "ancients")
    choice = next(c for c in (await _full(client, cid))["pending_choices"] if c.get("group") == "fighting_style")
    assert choice["resolvable"] is True and {o["key"] for o in choice["options"]} == {
        "great_weapon", "defense", "dueling", "protection"}
