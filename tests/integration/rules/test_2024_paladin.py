"""Paladino 2024 (Task 37, parte A): tabelle, Imposizione delle Mani (anche su altri e con le condizioni del Tocco
Ristoratore), Maestria, Stile di Combattimento e Guerriero Benedetto, Punizione del Paladino (slot e lancio gratuito),
Percezione del Divino, Incanalare Divinità, Destriero Fedele, le aure, Abiurare i Nemici, Assalti Radianti e multiclasse.
Valori dalla scheda ``docs/superpowers/rules/2024/classes/paladin.md``."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from core.db.models import Character, SessionParticipant
from core.rules.auras import projected_auras
from core.rules.catalog import features_for
from core.rules.proficiencies import class_proficiencies
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, seed_session
from tests.integration.rules.test_2014_bard import _ability, _choice, _full, _keys_of, _resolve, _roll_keys, _states, _use
from tests.integration.rules.test_2014_fighter_styles import _item
from tests.integration.rules.test_2014_monk_ki import _damage as _unarmed_damage, _hit as _unarmed_hit
from tests.integration.rules.test_2014_paladin import _hurt, _new_turn, _rest, _turn
from tests.integration.rules.test_2014_paladin_combat import _attack, _damage, _deferred, _listed, _slots, _smite_dice, _sword
from tests.integration.rules.test_2014_paladin_round1_loh import _give, _hero_hp, _hero_state, _pool

LOH, CD, DS, ABJURE = "paladin.lay_on_hands", "paladin.channel_divinity", "paladin.divine_sense", "paladin.abjure_foes"
PS, STEED = "paladin.paladins_smite", "paladin.faithful_steed"
SMITE, FREE = "paladin.divine_smite", "paladin.divine_smite_free"
FIEND, FIEND_FREE = "paladin.divine_smite_fiend", "paladin.divine_smite_fiend_free"
RADIANT = "paladin.radiant_strikes"
PREPARED = (2, 3, 4, 5, 6, 6, 7, 7, 9, 9, 10, 10, 11, 11, 12, 12, 14, 14, 15, 15)
SLOTS = {1: (2,), 2: (2,), 3: (3,), 5: (4, 2), 9: (4, 3, 2), 13: (4, 3, 3, 1), 17: (4, 3, 3, 3, 1), 19: (4, 3, 3, 3, 2)}
STYLES = {"archery", "blind_fighting", "defense", "dueling", "great_weapon", "interception", "protection", "thrown_weapon",
          "two_weapon", "unarmed", "blessed_warrior"}


async def _paladin24(client, level=5, **scores) -> int:
    body = {"name": "Paladino", "initial_class": {"class_name": "paladin", "level": level, "subclass": None}}
    r = await client.post("/characters", json=body)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    for ability, value in scores.items():
        r = await client.patch(f"/characters/{cid}/ability_scores/{ability}", json={"value": value})
        assert r.status_code == 200, r.text
    return cid


async def _table24(client, factory, level=6, **scores):
    """Una serata con il paladino 2024 (GM) e un eroe: ``(session_id, paladin, hero)``."""
    sid, hero = await seed_session(factory)
    as_user(GM_ID)
    paladin = await _paladin24(client, level, **scores)
    async with factory() as s:
        part = (await s.execute(select(SessionParticipant).where(SessionParticipant.user_id == GM_ID))).scalar_one()
        part.character_id = paladin
        await s.commit()
    as_user(PLAYER_ID)
    return sid, paladin, hero


async def _conditions(client, cid, **conditions) -> dict:
    r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": conditions})
    assert r.status_code == 200, r.text
    return r.json()["conditions"]


async def _melee_keys(client, cid, wid=None, **query) -> list[str]:
    """Le opzioni di un attacco in mischia: con un'arma, o senz'armi se ``wid`` manca."""
    if wid is None:
        r = await client.get(f"/characters/{cid}/roll-options", params={"roll": "attack", "attack_mode": "melee", **query})
        assert r.status_code == 200, r.text
        return [o["key"] for o in r.json()]
    return [o["key"] for o in await _listed(client, cid, wid, **query)]


# ---------------------------------------------------------------------------
# Tabelle, righe di sola regola, PF, competenze, livelli
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level", range(1, 21))
async def test_prepared_spells_follow_the_2024_table_and_there_are_no_cantrips(client, level):
    limits = (await _full(client, await _paladin24(client, level)))["spellcasting"]["limits"][0]
    assert (limits["cantrips_limit"] or 0, limits["prepared_limit"]) == (0, PREPARED[level - 1])


@pytest.mark.parametrize("level", sorted(SLOTS))
async def test_spell_slots_follow_the_half_caster_table_from_level_1(client, level):
    slots = tuple(s["total"] for s in sorted((await _full(client, await _paladin24(client, level)))["spell_slots"], key=lambda s: s["level"]))
    assert slots == SLOTS[level]


async def test_hit_points_use_the_d10(client):
    full = await _full(client, await _paladin24(client, 3))
    assert full["classes"][0]["hit_die"] == 10 and full["hit_points"] == 10 + 6 + 6


def test_class_and_multiclass_proficiencies():
    first = class_proficiencies("2024", "paladin", False)
    assert set(first.armor) == {"light", "medium", "heavy", "shields"} and set(first.weapons) == {"simple", "martial"}
    assert set(first.saves) == {"wisdom", "charisma"} and first.skills_count == 2
    multi = class_proficiencies("2024", "paladin", True)
    assert set(multi.armor) == {"light", "medium", "shields"} and multi.weapons == ("martial",)
    assert not multi.saves and not multi.skills_count


@pytest.mark.parametrize("level,asi", [(4, [4]), (16, [4, 8, 12, 16]), (19, [4, 8, 12, 16])])
async def test_asi_at_4_8_12_16_and_the_19th_is_an_epic_boon(client, level, asi):
    pending = (await _full(client, await _paladin24(client, level)))["pending_choices"]
    assert sorted(c["level"] for c in pending if c["kind"] == "asi") == asi
    assert any(c["kind"] == "epic_boon" for c in pending) == (level == 19)


@pytest.mark.parametrize("level,present", [
    (1, {"lay_on_hands"}), (2, {"paladins_smite"}), (3, {"divine_sense", "channel_divinity"}), (5, {"extra_attack", "faithful_steed"}),
    (6, {"aura_of_protection"}), (9, {"abjure_foes"}), (10, {"aura_of_courage"}), (11, {"radiant_strikes"}),
])
async def test_features_appear_at_their_level_and_rules_only_rows_stay_off_the_sheet(client, level, present):
    keys = await _keys_of(client, await _paladin24(client, level))
    assert {f"paladin.{k}" for k in present} <= keys
    low = await _keys_of(client, await _paladin24(client, level - 1)) if level > 1 else set()
    assert not {f"paladin.{k}" for k in present} & low
    assert not keys & {"paladin.core_traits", "paladin.spellcasting", "paladin.paladin_subclass", "paladin.ability_score_improvement",
                       "paladin.epic_boon", "paladin.multiclassing", "paladin.equipment"}


def test_every_base_mapping_title_has_its_row_with_both_languages():
    titles = {f.source_title for f in features_for("2024", "paladin")}
    mapping = open("docs/superpowers/rules/mapping/2024/paladin.md", encoding="utf-8").read().splitlines()[4:]
    wanted = [line.split("|")[1].strip() for line in mapping if line.startswith("|")]
    base = [t for t in wanted if not any(w in t for w in ("Devozione", "Gloria", "Antichi", "Vendetta", "Giuramento"))
            or t.startswith("Multiclasse")]
    assert len(base) == 21 and [t for t in base if t not in titles] == []
    assert all(f.summary["it"] and f.summary["en"] and len(f.summary["it"]) <= 200 for f in features_for("2024", "paladin"))


# ---------------------------------------------------------------------------
# Imposizione delle Mani
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level", [1, 5, 20])
async def test_lay_on_hands_is_a_pool_of_five_per_level_on_a_bonus_action(client, level):
    row = await _ability(client, await _paladin24(client, level), LOH)
    assert (row["max_uses"], row["uses"], row["action_type"], row["restoration_type"]) == (5 * level, 5 * level, "bonus_action", "long_rest")


async def test_lay_on_hands_heals_yourself_with_the_chosen_points_on_the_bonus_action(client, test_session_factory):
    cid = await _paladin24(client, 5)
    await _hurt(test_session_factory, cid, 3)
    r = await _use(client, cid, LOH, amount=7, params={"mode": "self"})
    assert r.status_code == 200, r.text
    assert r.json()["healed"] == 7 and (await _full(client, cid))["current_hit_points"] == 10
    assert (await _ability(client, cid, LOH))["uses"] == 18
    turn = await _turn(client, cid)
    assert turn["bonus_used"] is True and turn["action_used"] is False


async def test_the_pool_comes_back_with_a_long_rest(client):
    cid = await _paladin24(client, 5)
    assert (await _use(client, cid, LOH, amount=10, params={"mode": "self"})).status_code == 200
    await _rest(client, cid, "long")
    assert (await _ability(client, cid, LOH))["uses"] == 25


async def test_five_points_remove_poisoned_without_healing(client, test_session_factory):
    cid = await _paladin24(client, 5)
    await _hurt(test_session_factory, cid, 3)
    await _conditions(client, cid, poisoned=True)
    r = await _use(client, cid, LOH, amount=5, params={"mode": "cure_self", "cure_poisoned": True})
    assert r.status_code == 200, r.text
    full = await _full(client, cid)
    assert not full["conditions"].get("poisoned") and full["current_hit_points"] == 3
    assert (await _ability(client, cid, LOH))["uses"] == 20


async def test_a_cure_costs_exactly_five_points_per_condition_and_needs_a_condition(client):
    cid = await _paladin24(client, 5)
    for amount, toggles in ((4, True), (10, True), (5, False)):
        r = await _use(client, cid, LOH, amount=amount, params={"mode": "cure_self", **({"cure_poisoned": True} if toggles else {})})
        assert r.status_code in (409, 422), (amount, toggles)
    assert (await _ability(client, cid, LOH))["uses"] == 25 and (await _turn(client, cid))["bonus_used"] is False


async def test_restoring_touch_adds_six_conditions_at_level_14_and_each_costs_five(client):
    cid = await _paladin24(client, 14)
    await _conditions(client, cid, poisoned=True, blinded=True, stunned=True, prone=True)
    params = {"mode": "cure_self", "cure_poisoned": True, "cure_blinded": True, "cure_stunned": True}
    r = await _use(client, cid, LOH, amount=15, params=params)
    assert r.status_code == 200, r.text
    left = (await _full(client, cid))["conditions"]
    assert not any(left.get(c) for c in ("poisoned", "blinded", "stunned")) and left.get("prone") is True
    assert (await _ability(client, cid, LOH))["uses"] == 70 - 15


async def test_restoring_touch_conditions_are_not_available_before_level_14(client):
    cid = await _paladin24(client, 13)
    await _conditions(client, cid, blinded=True)
    r = await _use(client, cid, LOH, amount=5, params={"mode": "cure_self", "cure_blinded": True})
    assert r.status_code in (409, 422) and (await _full(client, cid))["conditions"].get("blinded") is True
    assert {t["key"] for t in (await _ability(client, cid, LOH))["use_toggles"]} == {"cure_poisoned"}
    assert len((await _ability(client, await _paladin24(client, 14), LOH))["use_toggles"]) == 7


async def test_lay_on_hands_heals_a_seated_ally_and_spends_the_pool_and_the_bonus_action(client, test_session_factory):
    _, paladin, hero = await _table24(client, test_session_factory, level=5)
    await _hero_hp(test_session_factory, hero, 5)
    as_user(GM_ID)
    r = await _give(client, paladin, hero, 8)
    assert r.status_code == 200, r.text
    assert r.json()["received"] == {"name": "Eroe", "healed": 8}
    assert await _pool(client, paladin) == 17 and (await _turn(client, paladin))["bonus_used"] is True
    assert (await _hero_state(test_session_factory, hero))[0] == 13


async def test_a_cure_on_a_seated_ally_removes_only_the_chosen_condition_task48(client, test_session_factory):
    """Task 48 (estende R42): sul PG della serata si tolgono le condizioni scelte e ammesse, non i PF né altro."""
    _, paladin, hero = await _table24(client, test_session_factory, level=5)
    await _hero_hp(test_session_factory, hero, 20, conditions={"poisoned": True, "prone": True})
    as_user(GM_ID)
    r = await _give(client, paladin, hero, 5, mode="cure_other", cure_poisoned=True)
    assert r.status_code == 200, r.text
    assert r.json()["notes"] == [] and r.json()["removal"]
    hp, conditions = await _hero_state(test_session_factory, hero)
    assert hp == 20 and conditions.get("poisoned") is False and conditions.get("prone") is True
    assert await _pool(client, paladin) == 20


async def test_a_cure_on_someone_outside_the_evening_is_a_note_for_the_gm(client, test_session_factory):
    _, paladin, _ = await _table24(client, test_session_factory, level=5)
    as_user(GM_ID)
    r = await _give(client, paladin, None, 5, mode="cure_other", cure_poisoned=True)
    assert r.status_code == 200 and "Da togliere alla creatura" in r.json()["removal"][0]["it"]
    assert await _pool(client, paladin) == 20


# ---------------------------------------------------------------------------
# Incanalare Divinità e Percezione del Divino
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,uses", [(2, None), (3, 2), (10, 2), (11, 3), (20, 3)])
async def test_channel_divinity_uses_follow_the_level(client, level, uses):
    row = await _ability(client, await _paladin24(client, level), CD)
    assert (row["max_uses"] if row else None) == uses


async def test_a_short_rest_returns_one_use_and_a_long_rest_all_of_them(client):
    cid = await _paladin24(client, 11)
    for _ in range(3):
        assert (await _use(client, cid, DS)).status_code == 200
        await client.post(f"/characters/{cid}/turn/use", json={"slot": "bonus", "used": False})
    assert (await _ability(client, cid, CD))["uses"] == 0
    await _rest(client, cid, "short")
    assert (await _ability(client, cid, CD))["uses"] == 1
    await _rest(client, cid, "long")
    assert (await _ability(client, cid, CD))["uses"] == 3


async def test_divine_sense_is_a_bonus_action_that_spends_a_use_and_lasts_ten_minutes(client):
    cid = await _paladin24(client, 3)
    r = await _use(client, cid, DS)
    assert r.status_code == 200, r.text
    state = next(s for s in await _states(client, cid) if s["key"] == "divine_sense")
    assert state["rounds_left"] == 100 and state["data"]["range_m"] == 18
    assert (await _ability(client, cid, CD))["uses"] == 1
    turn = await _turn(client, cid)
    assert turn["bonus_used"] is True and turn["action_used"] is False


async def test_divine_sense_ends_when_incapacitated(client):
    cid = await _paladin24(client, 3)
    assert (await _use(client, cid, DS)).status_code == 200
    await _conditions(client, cid, incapacitated=True)
    assert not any(s["key"] == "divine_sense" for s in await _states(client, cid))


async def test_divine_sense_is_refused_without_uses_and_keeps_the_bonus_action(client):
    cid = await _paladin24(client, 3)
    for _ in range(2):
        assert (await _use(client, cid, DS)).status_code == 200
        await client.post(f"/characters/{cid}/turn/use", json={"slot": "bonus", "used": False})
    r = await _use(client, cid, DS)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_uses" and (await _turn(client, cid))["bonus_used"] is False


@pytest.mark.parametrize("cleric_first,cleric,paladin,holder,uses", [
    (True, 6, 5, "cleric.channel_divinity", 3), (False, 6, 5, "cleric.channel_divinity", 3),
    (True, 5, 11, CD, 3), (False, 5, 11, CD, 3), (True, 5, 5, None, 2), (False, 5, 5, None, 2),
])
async def test_channel_divinity_is_one_pool_with_the_cleric_in_both_orders(client, cleric_first, cleric, paladin, holder, uses):
    first, second = (("cleric", cleric), ("paladin", paladin)) if cleric_first else (("paladin", paladin), ("cleric", cleric))
    r = await client.post("/characters", json={"name": "Mix", "initial_class": {"class_name": first[0], "level": first[1], "subclass": None}})
    cid = r.json()["id"]
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": second[0], "level": second[1], "hit_die": 8})
    assert r.status_code == 201, r.text
    rows = [a for a in (await _full(client, cid))["abilities"] if a["feature_key"] in (CD, "cleric.channel_divinity")]
    assert len(rows) == 1 and rows[0]["max_uses"] == uses
    assert holder is None or rows[0]["feature_key"] == holder
    assert (await _use(client, cid, DS)).status_code == 200 and (await _use(client, cid, "cleric.turn_undead")).status_code == 200
    assert (await _ability(client, cid, rows[0]["feature_key"]))["uses"] == uses - 2


# ---------------------------------------------------------------------------
# Abiurare i Nemici
# ---------------------------------------------------------------------------

async def test_abjure_foes_is_a_magic_action_that_spends_a_use_and_frightens_on_a_failed_wisdom_save(client):
    cid = await _paladin24(client, 9, charisma=16)
    r = await _use(client, cid, ABJURE)
    assert r.status_code == 200 and r.json()["targets"] == [ABJURE], r.text
    effect = (await client.get(f"/characters/{cid}/target-effects/{ABJURE}")).json()["result"]
    assert (effect["condition"], effect["save_ability"], effect["save_dc"], effect["rounds"]) == ("frightened", "wisdom", 8 + 4 + 3, 10)
    assert effect["note"] == "abjure_foes" and (await _ability(client, cid, CD))["uses"] == 1
    turn = await _turn(client, cid)
    assert turn["action_used"] is True and turn["bonus_used"] is False
    assert "3" in r.json()["message"]["it"] and "3" in r.json()["message"]["en"]


async def test_abjure_foes_targets_at_least_one_creature(client):
    cid = await _paladin24(client, 9, charisma=8)
    assert "1 creatura" in (await _use(client, cid, ABJURE)).json()["message"]["it"]


# ---------------------------------------------------------------------------
# Maestria nelle Armi, Stile di Combattimento, Guerriero Benedetto
# ---------------------------------------------------------------------------

async def test_weapon_mastery_is_a_choice_of_two_kinds_from_level_1(client):
    choice = _choice(await _full(client, await _paladin24(client, 1)), "weapon_mastery")
    assert choice["count"] == 2 and choice["options"]


async def test_the_fighting_style_is_chosen_at_level_2_among_ten_styles_and_blessed_warrior(client):
    assert _choice(await _full(client, await _paladin24(client, 1)), "fighting_style") is None
    choice = _choice(await _full(client, await _paladin24(client, 2)), "fighting_style")
    assert choice["count"] == 1 and {o["key"] for o in choice["options"]} == STYLES
    assert all(o["name"]["it"] and o["name"]["en"] and o["summary"]["it"] for o in choice["options"])


async def test_the_style_rows_belong_to_the_paladin_and_a_chosen_style_works(client):
    keys = {f.key for f in features_for("2024", "paladin")}
    assert {"paladin.style_defense", "paladin.style_interception", "paladin.style_blessed_warrior"} <= keys
    assert not any(k.startswith("fighter.") for k in keys)
    assert all(m.source.startswith("feature:paladin.") for f in features_for("2024", "paladin") for m in f.modifiers
               if f.key.startswith("paladin.style_"))
    cid = await _paladin24(client, 2)
    assert (await _resolve(client, cid, "fighting_style", ["unarmed"])).status_code == 200
    assert "paladin.style_unarmed" in await _keys_of(client, cid)


async def test_blessed_warrior_asks_for_two_cleric_cantrips(client):
    cid = await _paladin24(client, 2)
    assert (await _resolve(client, cid, "fighting_style", ["blessed_warrior"])).status_code == 200
    pick = _choice(await _full(client, cid), "blessed_warrior_cantrip")
    assert pick["count"] == 2 and pick["spell_pick"]["list"] == "cleric" and pick["spell_pick"]["max_level"] == 0
    assert pick["spell_pick"]["free"] is True


# ---------------------------------------------------------------------------
# Punizione del Paladino
# ---------------------------------------------------------------------------

async def test_the_paladins_smite_gives_divine_smite_and_one_free_cast_per_long_rest(client):
    cid = await _paladin24(client, 2)
    row = await _ability(client, cid, PS)
    assert (row["max_uses"], row["uses"], row["restoration_type"]) == (1, 1, "long_rest")
    assert "divine-smite" in {s["srd_index"] for s in (await client.get(f"/characters/{cid}/spells")).json()}
    assert PS not in await _keys_of(client, await _paladin24(client, 1))


async def test_smite_offers_two_dice_at_slot_one_plus_one_per_level_with_no_cap(client):
    cid = await _paladin24(client, 17)
    assert _smite_dice(await _listed(client, cid, await _sword(client, cid))) == {1: "2d8", 2: "3d8", 3: "4d8", 4: "5d8", 5: "6d8"}


async def test_the_free_smite_costs_no_slot_takes_the_bonus_action_and_adds_two_radiant_dice(client):
    cid = await _paladin24(client, 5)
    wid = await _sword(client, cid)
    hit = await _deferred(client, cid, wid)
    r = await _damage(client, cid, hit, [FREE])
    assert r.status_code == 200, r.text
    block = r.json()["option_result"]
    assert len(block["extra_rolls"]) == 2 and all(1 <= v <= 8 for v in block["extra_rolls"])
    assert r.json()["damage_total"] == hit["damage_total"] + sum(block["extra_rolls"])
    assert any("radios" in e["it"].lower() for e in block["effects"])
    assert await _slots(client, cid) == {1: 0, 2: 0} and (await _ability(client, cid, PS))["uses"] == 0
    assert (await _turn(client, cid))["bonus_used"] is True


async def test_the_free_smite_is_gone_when_spent_and_comes_back_with_a_long_rest(client):
    cid = await _paladin24(client, 5)
    wid = await _sword(client, cid)
    assert (await _damage(client, cid, await _deferred(client, cid, wid), [FREE])).status_code == 200
    await _new_turn(client, cid)
    assert FREE not in await _melee_keys(client, cid, wid, attack_mode="melee", grip="one")
    await _rest(client, cid, "long")
    assert FREE in await _melee_keys(client, cid, wid, attack_mode="melee", grip="one")


async def test_the_slot_smite_spends_the_slot_and_the_bonus_action_and_marks_the_slot_spell(client):
    cid = await _paladin24(client, 5)
    wid = await _sword(client, cid)
    r = await _damage(client, cid, await _deferred(client, cid, wid), [SMITE], **{SMITE: {"slot_level": 2}})
    assert r.status_code == 200, r.text
    assert len(r.json()["option_result"]["extra_rolls"]) == 3 and await _slots(client, cid) == {1: 0, 2: 1}
    turn = await _turn(client, cid)
    assert turn["bonus_used"] is True and turn["spell_slot_cast"] is True and (await _ability(client, cid, PS))["uses"] == 1


async def test_a_smite_needs_the_bonus_action(client):
    cid = await _paladin24(client, 5)
    wid = await _sword(client, cid)
    await client.post(f"/characters/{cid}/turn/use", json={"slot": "bonus", "used": True})
    assert not {SMITE, FREE} & set(await _melee_keys(client, cid, wid, attack_mode="melee", grip="one"))


async def test_a_slot_smite_is_not_offered_after_another_slot_spell_this_turn_but_the_free_one_is(client):
    cid = await _paladin24(client, 5)
    wid = await _sword(client, cid)
    r = await client.post(f"/characters/{cid}/turn/use", json={"slot": "spell_slot", "used": True})
    assert r.status_code == 200, r.text
    keys = await _melee_keys(client, cid, wid, attack_mode="melee", grip="one")
    assert SMITE not in keys and FREE in keys


async def test_smite_is_for_melee_weapons_and_unarmed_strikes_not_ranged_or_thrown(client):
    cid = await _paladin24(client, 5)
    wid = await _sword(client, cid)
    bow = await _item(client, cid, "Arco", damage_dice="1d8", weapon_type="ranged", properties=["ammunition"])
    axe = await _item(client, cid, "Accetta", damage_dice="1d6", weapon_type="melee", properties=["thrown"])
    assert {SMITE, FREE} <= set(await _melee_keys(client, cid, wid, attack_mode="melee", grip="one"))
    assert {SMITE, FREE} <= set(await _melee_keys(client, cid))
    assert not {SMITE, FREE} & set(await _melee_keys(client, cid, bow))
    assert not {SMITE, FREE} & set(await _melee_keys(client, cid, axe, attack_mode="thrown", grip="one"))


async def test_smite_on_an_unarmed_strike_and_the_critical_doubles_the_dice(client):
    cid = await _paladin24(client, 5)
    hit = await _unarmed_hit(client, cid, die=20)
    r = await _unarmed_damage(client, cid, hit, FREE)
    assert r.status_code == 200, r.text
    assert len(r.json()["option_result"]["extra_rolls"]) == 4


async def test_a_smite_against_an_undead_or_fiend_adds_a_die_and_needs_the_smite(client):
    cid = await _paladin24(client, 5)
    wid = await _sword(client, cid)
    hit = await _deferred(client, cid, wid)
    alone = await _damage(client, cid, hit, [FIEND_FREE])
    assert alone.status_code == 409 and alone.json()["detail"]["code"] == "option_unavailable"
    assert (await _ability(client, cid, PS))["uses"] == 1
    r = await _damage(client, cid, hit, [FREE, FIEND_FREE])
    assert r.status_code == 200, r.text
    assert len(r.json()["option_result"]["extra_rolls"]) == 3 and (await _ability(client, cid, PS))["uses"] == 0
    other = await _paladin24(client, 5)
    r = await _damage(client, other, await _deferred(client, other, await _sword(client, other)), [SMITE, FIEND], **{SMITE: {"slot_level": 1}})
    assert r.status_code == 200 and len(r.json()["option_result"]["extra_rolls"]) == 3


async def test_only_one_of_the_two_smites_per_attack(client):
    cid = await _paladin24(client, 5)
    wid = await _sword(client, cid)
    r = await _damage(client, cid, await _deferred(client, cid, wid), [SMITE, FREE], **{SMITE: {"slot_level": 1}})
    assert r.status_code == 409 and await _slots(client, cid) == {1: 0, 2: 0} and (await _ability(client, cid, PS))["uses"] == 1


# ---------------------------------------------------------------------------
# Assalti Radianti
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,dice", [(10, 0), (11, 1), (20, 1)])
async def test_radiant_strikes_add_a_radiant_die_to_melee_weapon_hits_from_level_11(client, level, dice):
    cid = await _paladin24(client, level)
    body = (await _attack(client, cid, await _sword(client, cid))).json()
    block = body.get("option_result") or {}
    assert len(block.get("extra_rolls", [])) == dice
    if dice:
        assert RADIANT in block["keys"] and any("radios" in e["it"].lower() for e in block["effects"])
        assert body["damage_total"] == sum(body["damage_rolls"]) + body["damage_bonus"] + sum(block["extra_rolls"])


async def test_radiant_strikes_also_work_unarmed_double_on_a_critical_and_skip_ranged_attacks(client):
    cid = await _paladin24(client, 11)
    bow = await _item(client, cid, "Arco", damage_dice="1d8", weapon_type="ranged", properties=["ammunition"])
    assert len((await _attack(client, cid, await _sword(client, cid), die=20)).json()["option_result"]["extra_rolls"]) == 2
    assert (await _attack(client, cid, bow)).json().get("option_result") is None
    assert len((await _unarmed_hit(client, cid, die=10))["option_result"]["extra_rolls"]) == 1


async def test_radiant_strikes_stack_with_a_smite(client):
    cid = await _paladin24(client, 11)
    hit = await _deferred(client, cid, await _sword(client, cid))
    r = await _damage(client, cid, hit, [FREE])
    assert r.status_code == 200 and len(r.json()["option_result"]["extra_rolls"]) == 3


# ---------------------------------------------------------------------------
# Destriero Fedele
# ---------------------------------------------------------------------------

async def test_faithful_steed_gives_find_steed_and_one_free_cast_per_long_rest(client):
    cid = await _paladin24(client, 5)
    spells = {s["srd_index"]: s for s in (await client.get(f"/characters/{cid}/spells")).json()}
    assert "find-steed" in spells and spells["find-steed"]["casting_time"] == "1 azione"
    r = await _use(client, cid, STEED, params={"name": "Lampo"})
    assert r.status_code == 200, r.text
    assert (await _ability(client, cid, STEED))["uses"] == 0
    assert (await _turn(client, cid))["action_used"] is True  # il lancio costa l'azione (manuale: Action)
    assert await _slots(client, cid) == {1: 0, 2: 0}
    steed = next(c for c in (await client.get(f"/characters/{cid}/companions")).json() if c["feature_key"] == STEED)
    assert (steed["name"], steed["armor_class"], steed["max_hp"], steed["current_hp"]) == ("Lampo", 12, 25, 25)
    assert (await _use(client, cid, STEED)).status_code == 409
    await _rest(client, cid, "long")
    assert (await _ability(client, cid, STEED))["uses"] == 1


async def test_faithful_steed_needs_the_action(client):
    cid = await _paladin24(client, 5)
    await client.post(f"/characters/{cid}/turn/use", json={"slot": "action", "used": True})
    assert (await _use(client, cid, STEED)).status_code == 409
    assert (await _ability(client, cid, STEED))["uses"] == 1


async def test_divine_smite_cannot_be_cast_from_the_spell_list_only_after_a_hit(client):
    """Una «Lancia» da elenco spenderebbe uno slot senza danno e bloccherebbe la vera Punizione del turno."""
    cid = await _paladin24(client, 5)
    smite = next(s for s in (await client.get(f"/characters/{cid}/spells")).json() if s["srd_index"] == "divine-smite")
    r = await client.post(f"/characters/{cid}/spells/{smite['id']}/use", json={"slot_level": 1, "confirm": []})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "smite_on_hit"
    assert await _slots(client, cid) == {1: 0, 2: 0} and (await _turn(client, cid))["spell_slot_cast"] is False


# ---------------------------------------------------------------------------
# Aure
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,charisma,bonus", [(5, 16, 0), (6, 16, 3), (6, 8, 1), (20, 20, 5)])
async def test_aura_of_protection_adds_charisma_with_a_minimum_of_one_to_every_save(client, level, charisma, bonus):
    flat = (await _full(client, await _paladin24(client, level, charisma=charisma)))["computed"]["save_flat"]
    assert set(flat.values()) == {bonus}


@pytest.mark.parametrize("condition", ["incapacitated", "stunned", "paralyzed"])
async def test_the_aura_of_protection_is_inactive_while_incapacitated(client, condition):
    cid = await _paladin24(client, 6, charisma=16)
    await _conditions(client, cid, **{condition: True})
    assert set((await _full(client, cid))["computed"]["save_flat"].values()) == {0}
    await _conditions(client, cid, **{condition: False})
    assert set((await _full(client, cid))["computed"]["save_flat"].values()) == {3}


async def test_an_ally_is_offered_the_aura_and_loses_it_when_the_paladin_is_incapacitated(client, test_session_factory):
    _, paladin, hero = await _table24(client, test_session_factory, charisma=16)
    assert "aura:protection" in await _roll_keys(client, hero, "save", ability="dexterity")
    as_user(GM_ID)
    await _conditions(client, paladin, stunned=True)
    as_user(PLAYER_ID)
    assert "aura:protection" not in await _roll_keys(client, hero, "save", ability="dexterity")


async def test_the_aura_range_is_3_m_and_9_m_from_level_18(client, test_session_factory):
    ranges = {}
    for level in (17, 18):
        cid = await _paladin24(client, level)
        async with test_session_factory() as s:
            char = (await s.execute(select(Character).where(Character.id == cid).execution_options(populate_existing=True))).scalar_one()
            await s.refresh(char, ["classes", "ability_scores", "items", "abilities"])
            ranges[level] = [a["range_ft"] for a in projected_auras(char)]
    assert ranges == {17: [10], 18: [30]}


async def test_aura_of_courage_makes_the_paladin_immune_to_frightened_from_level_10(client):
    for level, frightened in ((9, True), (10, None)):
        cid = await _paladin24(client, level)
        conditions = await _conditions(client, cid, frightened=True, prone=True)
        assert conditions.get("frightened") == frightened and conditions["prone"] is True


async def test_aura_of_courage_stops_while_the_paladin_is_incapacitated(client):
    cid = await _paladin24(client, 10)
    await _conditions(client, cid, stunned=True)
    assert (await _conditions(client, cid, frightened=True)).get("frightened") is True


async def test_aura_of_courage_is_shown_to_the_gm_and_the_group(client):
    cid = await _paladin24(client, 10)
    assert any(s["key"] == "aura_of_courage" for s in await _states(client, cid))


# ---------------------------------------------------------------------------
# Attacco Extra, multiclasse e cambio di edizione
# ---------------------------------------------------------------------------

def test_extra_attack_gives_two_attacks_from_level_5_and_no_more():
    rows = [f for f in features_for("2024", "paladin") if f.attacks_per_action]
    assert [(f.key, f.level, f.attacks_per_action) for f in rows] == [("paladin.extra_attack", 5, 2)]


async def test_multiclass_slots_count_half_the_paladin_levels_rounded_up(client):
    cid = await _paladin24(client, 3)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "cleric", "level": 3, "hit_die": 8})
    assert r.status_code == 201, r.text
    slots = tuple(s["total"] for s in sorted((await _full(client, cid))["spell_slots"], key=lambda s: s["level"]))
    assert slots == (4, 3, 2)  # 2 (3 per eccesso, la metà) + 3 = livello 5


async def test_a_2014_paladin_that_becomes_2024_gets_the_2024_rows_and_keeps_its_spent_points(client):
    r = await client.post("/characters", json={"name": "Vecchio", "initial_class": {"class_name": "paladin", "level": 5, "subclass": None}})
    cid = r.json()["id"]
    assert (await _use(client, cid, LOH, amount=10, params={"mode": "self"})).status_code == 200
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    keys = await _keys_of(client, cid)
    assert {PS, STEED, DS, CD, LOH} <= keys and "paladin.divine_health" not in keys and "paladin.cleansing_touch" not in keys
    assert (await _ability(client, cid, LOH))["uses"] == 15 and (await _ability(client, cid, CD))["max_uses"] == 2
