"""Guerriero 2014 (Task 23): progressione, Recuperare Energie, Azione Impetuosa, Attacco Extra, Indomito e il Campione."""
from __future__ import annotations

import pytest

from core.db.models import Character
from core.rules.catalog import features_for
from core.rules.proficiencies import class_proficiencies
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, seed_session
from tests.integration.rules.test_2014_bard import _ability, _full, _keys_of, _roll_keys, _use

SUBCLASSES = {"champion": "Campione", "battle_master": "Maestro di Battaglia", "eldritch_knight": "Cavaliere Mistico"}
SW, AS, IND, SD = "fighter.second_wind", "fighter.action_surge", "fighter.indomitable", "fighter.superiority_dice"


async def _fighter(client, level=5, subclass=None, **scores) -> int:
    body = {"name": "Guerriero", "initial_class": {"class_name": "fighter", "level": level, "subclass": SUBCLASSES.get(subclass)}}
    r = await client.post("/characters", json=body)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    for ability, value in scores.items():
        r = await client.patch(f"/characters/{cid}/ability_scores/{ability}", json={"value": value})
        assert r.status_code == 200, r.text
    return cid


async def _turn(client, cid) -> dict:
    return (await client.get(f"/characters/{cid}/turn-state")).json()["turn"]


async def _allowed(client, cid) -> int:
    return (await client.get(f"/characters/{cid}/turn-state")).json()["attacks_allowed"]


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


async def _blade(client, cid, **meta) -> int:
    meta = {"damage_dice": "1d8", "weapon_type": "melee", "properties": [], **meta}
    r = await client.post(f"/characters/{cid}/items", json={"name": "Spada", "item_type": "weapon", "item_metadata": meta})
    assert r.status_code == 201, r.text
    return max(i["id"] for i in r.json()["items"])


async def _attack(client, cid, wid, die=10, **body):
    return await client.post(f"/characters/{cid}/items/{wid}/attack", json={"die": die, **body})


# ---------------------------------------------------------------------------
# Progressione e catalogo
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,uses", [(2, 1), (16, 1), (17, 2), (20, 2)])
async def test_action_surge_uses_follow_the_level(client, level, uses):
    row = await _ability(client, await _fighter(client, level), AS)
    assert (row["max_uses"], row["uses"], row["restoration_type"]) == (uses, uses, "short_rest")


@pytest.mark.parametrize("level,uses", [(9, 1), (12, 1), (13, 2), (16, 2), (17, 3), (20, 3)])
async def test_indomitable_uses_follow_the_level(client, level, uses):
    row = await _ability(client, await _fighter(client, level), IND)
    assert (row["max_uses"], row["restoration_type"]) == (uses, "long_rest")


async def test_levels_below_the_first_use_have_no_row(client):
    keys = await _keys_of(client, await _fighter(client, 1))
    assert SW in keys and AS not in keys
    assert IND not in await _keys_of(client, await _fighter(client, 8))


async def test_the_old_resource_names_are_replaced_by_the_official_ones(client):
    cid = await _fighter(client, 9)
    assert (await _ability(client, cid, SW))["name"] == "Recuperare Energie"
    assert (await _ability(client, cid, AS))["name"] == "Azione Impetuosa"
    assert (await _ability(client, cid, IND))["name"] == "Indomito"


async def test_superiority_dice_exist_only_for_the_battle_master(client):
    for sub in (None, "champion", "eldritch_knight"):
        assert SD not in await _keys_of(client, await _fighter(client, 7, sub))
    assert SD in await _keys_of(client, await _fighter(client, 7, "battle_master"))


async def test_rules_only_rows_do_not_clutter_the_sheet(client):
    keys = await _keys_of(client, await _fighter(client, 20, "champion"))
    assert not keys & {f"fighter.{k}" for k in ("hit_points", "proficiencies", "equipment", "fighting_style", "martial_archetype",
                                                "ability_score_improvement", "multiclassing", "additional_fighting_style",
                                                "extra_attack_11", "extra_attack_20")}


def test_class_proficiencies_first_class_and_multiclass():
    first = class_proficiencies("2014", "fighter", False)
    assert set(first.armor) == {"light", "medium", "heavy", "shields"} and set(first.weapons) == {"simple", "martial"}
    assert set(first.saves) == {"strength", "constitution"} and first.skills_count == 2 and "persuasion" not in first.skills_from
    multi = class_proficiencies("2014", "fighter", True)
    assert set(multi.armor) == {"light", "medium", "shields"} and set(multi.weapons) == {"simple", "martial"} and not multi.saves


async def test_hit_points_use_the_d10_and_follow_constitution(client):
    full = await _full(client, await _fighter(client, 3))
    assert full["classes"][0]["hit_die"] == 10
    assert full["hit_points"] == 10 + 6 + 6  # 10 + COS al 1°, poi la media 6 (COS 10)


@pytest.mark.parametrize("level", [4, 6, 8, 12, 14, 16, 19])
async def test_asi_choice_is_pending_at_each_asi_level(client, level):
    cid = await _fighter(client, level)
    levels = sorted(c["level"] for c in (await _full(client, cid))["pending_choices"] if c["kind"] == "asi")
    assert levels == [lv for lv in (4, 6, 8, 12, 14, 16, 19) if lv <= level]


def test_every_subclass_of_the_sheet_is_in_the_catalog():
    assert {f.subclass for f in features_for("2014", "fighter") if f.subclass} == set(SUBCLASSES)


# ---------------------------------------------------------------------------
# Recuperare Energie
# ---------------------------------------------------------------------------

async def test_second_wind_heals_a_d10_plus_the_fighter_level_and_spends_the_bonus_action(client, test_session_factory, monkeypatch):
    monkeypatch.setattr("api.services.rules_states.random.randint", lambda a, b: 7)
    cid = await _fighter(client, 5)
    await _hurt(test_session_factory, cid, 5)
    body = (await _use(client, cid, SW)).json()
    assert body["rolls"] == [7] and body["healed"] == 7 + 5
    assert await _hp(client, cid) == 5 + 12
    assert (await _turn(client, cid))["bonus_used"] is True
    row = await _ability(client, cid, SW)
    assert row["uses"] == 0 and row["action_type"] == "bonus_action"


async def test_second_wind_adds_the_level_of_the_fighter_not_the_total_level(client, test_session_factory, monkeypatch):
    monkeypatch.setattr("api.services.rules_states.random.randint", lambda a, b: 3)
    cid = await _fighter(client, 5)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "wizard", "level": 4, "hit_die": 6})
    assert r.status_code == 201, r.text
    await _hurt(test_session_factory, cid, 1)
    assert (await _use(client, cid, SW)).json()["healed"] == 3 + 5


async def test_second_wind_never_passes_the_maximum(client, test_session_factory):
    cid = await _fighter(client, 5)
    maximum = (await _full(client, cid))["hit_points"]
    await _hurt(test_session_factory, cid, maximum - 2)
    assert (await _use(client, cid, SW)).json()["healed"] == 2 and await _hp(client, cid) == maximum


async def test_second_wind_is_refused_without_uses_or_with_the_bonus_action_spent_and_costs_nothing(client):
    cid = await _fighter(client, 5)
    await client.post(f"/characters/{cid}/turn/use", json={"slot": "bonus"})
    r = await _use(client, cid, SW)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "turn_slot_used"
    assert (await _ability(client, cid, SW))["uses"] == 1  # il rifiuto non spende l'uso
    await client.post(f"/characters/{cid}/turn/new")
    assert (await _use(client, cid, SW)).status_code == 200
    await client.post(f"/characters/{cid}/turn/new")
    r = await _use(client, cid, SW)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_uses"


@pytest.mark.parametrize("rest", ["short", "long"])
async def test_second_wind_returns_with_a_short_or_a_long_rest(client, rest):
    cid = await _fighter(client, 5)
    await _use(client, cid, SW)
    await _rest(client, cid, rest)
    assert (await _ability(client, cid, SW))["uses"] == 1


# ---------------------------------------------------------------------------
# Azione Impetuosa
# ---------------------------------------------------------------------------

async def test_action_surge_gives_one_more_action_that_can_really_be_spent(client):
    cid = await _fighter(client, 5)
    await client.post(f"/characters/{cid}/turn/use", json={"slot": "action"})
    r = await client.post(f"/characters/{cid}/turn/use", json={"slot": "action"})
    assert r.status_code == 409  # senza Azione Impetuosa la seconda azione non c'è
    assert (await _use(client, cid, AS)).status_code == 200
    turn = await _turn(client, cid)
    assert turn["extra_actions"] == 1 and turn["bonus_used"] is False  # non è un'azione bonus e non la consuma
    assert (await client.post(f"/characters/{cid}/turn/use", json={"slot": "action"})).status_code == 200
    assert (await _turn(client, cid))["extra_actions"] == 0
    assert (await client.post(f"/characters/{cid}/turn/use", json={"slot": "action"})).status_code == 409


async def test_action_surge_does_not_cost_the_action_or_the_bonus_action(client):
    cid = await _fighter(client, 5)
    await _use(client, cid, AS)
    turn = await _turn(client, cid)
    assert (turn["action_used"], turn["bonus_used"], turn["reaction_used"]) == (False, False, False)


async def test_action_surge_gives_a_new_allotment_of_attacks(client):
    cid = await _fighter(client, 5)
    wid = await _blade(client, cid)
    assert (await _attack(client, cid, wid)).status_code == 200 and (await _attack(client, cid, wid)).status_code == 200
    r = await _attack(client, cid, wid)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "attack_limit"
    await _use(client, cid, AS)
    assert await _allowed(client, cid) == 4
    assert (await _attack(client, cid, wid)).status_code == 200 and (await _attack(client, cid, wid)).status_code == 200
    assert (await _attack(client, cid, wid)).json()["detail"]["code"] == "attack_limit"


async def test_action_surge_new_turn_removes_the_unspent_extra_action(client):
    cid = await _fighter(client, 5)
    await _use(client, cid, AS)
    await client.post(f"/characters/{cid}/turn/new")
    assert (await _turn(client, cid))["extra_actions"] == 0


async def test_action_surge_twice_in_one_turn_is_refused_at_17_and_costs_nothing(client):
    cid = await _fighter(client, 17)
    assert (await _use(client, cid, AS)).status_code == 200
    r = await _use(client, cid, AS)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "once_per_turn"
    assert (await _ability(client, cid, AS))["uses"] == 1 and (await _turn(client, cid))["extra_actions"] == 1
    await client.post(f"/characters/{cid}/turn/new")
    assert (await _use(client, cid, AS)).status_code == 200 and (await _ability(client, cid, AS))["uses"] == 0


async def test_action_surge_is_refused_without_uses_and_returns_with_a_short_rest(client):
    cid = await _fighter(client, 5)
    await _use(client, cid, AS)
    await client.post(f"/characters/{cid}/turn/new")
    r = await _use(client, cid, AS)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_uses"
    await _rest(client, cid, "short")
    assert (await _ability(client, cid, AS))["uses"] == 1


# ---------------------------------------------------------------------------
# Attacco Extra
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,attacks", [(1, 1), (4, 1), (5, 2), (10, 2), (11, 3), (19, 3), (20, 4)])
async def test_extra_attacks_follow_the_level(client, level, attacks):
    cid = await _fighter(client, level)
    assert await _allowed(client, cid) == attacks
    wid = await _blade(client, cid)
    for _ in range(attacks):
        assert (await _attack(client, cid, wid)).status_code == 200
    assert (await _turn(client, cid))["action_attacks"] == attacks
    r = await _attack(client, cid, wid)
    assert r.status_code == 409 and r.json()["detail"] == {"code": "attack_limit", "made": attacks, "allowed": attacks}


async def test_the_player_can_confirm_one_more_attack_than_the_action_allows(client):
    cid = await _fighter(client, 5)
    wid = await _blade(client, cid)
    for _ in range(2):
        await _attack(client, cid, wid)
    assert (await _attack(client, cid, wid, confirm_extra_attack=True)).status_code == 200


async def test_extra_attack_does_not_stack_with_another_class_and_the_fighter_exceeds_two(client):
    cid = await _fighter(client, 5)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "barbarian", "level": 5, "hit_die": 12})
    assert r.status_code == 201, r.text
    assert await _allowed(client, cid) == 2  # Attacco Extra del guerriero e del barbaro: il massimo, non la somma
    klass = next(c for c in (await _full(client, cid))["classes"] if c["class_name"].lower() in ("fighter", "guerriero"))
    await client.patch(f"/characters/{cid}/classes/{klass['id']}", json={"level": 11})
    assert await _allowed(client, cid) == 3


# ---------------------------------------------------------------------------
# Indomito
# ---------------------------------------------------------------------------

async def _save(client, cid, die=3, **body):
    r = await client.post(f"/characters/{cid}/saving_throws/wisdom/roll", json={"die": die, **body})
    assert r.status_code == 200, r.text
    return r.json()


async def _after(client, cid, *keys, **extra):
    return await client.post(f"/characters/{cid}/last-roll/options", json={"options": list(keys), **extra})


async def test_indomitable_is_offered_after_a_saving_throw_only(client):
    cid = await _fighter(client, 9)
    assert IND in await _roll_keys(client, cid, "save", ability="wisdom")
    assert IND not in await _roll_keys(client, cid, "attack")
    assert IND not in await _roll_keys(client, cid, "skill", skill="athletics")
    assert IND not in await _roll_keys(client, await _fighter(client, 8), "save", ability="wisdom")


async def test_indomitable_rerolls_the_failed_save_and_the_new_result_stands(client):
    cid = await _fighter(client, 9)
    first = await _save(client, cid, die=2)
    r = await _after(client, cid, IND, dice=[4])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["die"] == 4 and body["total"] == first["total"] + 2  # il nuovo risultato, anche se peggiore, è obbligatorio
    assert (await _ability(client, cid, IND))["uses"] == 0
    assert (await _after(client, cid, IND, dice=[19])).status_code == 409  # un solo uso


async def test_indomitable_new_result_is_final_even_when_worse(client):
    cid = await _fighter(client, 9)
    first = await _save(client, cid, die=15)
    body = (await _after(client, cid, IND, dice=[1])).json()
    assert body["die"] == 1 and body["total"] == first["total"] - 14


async def test_indomitable_is_refused_without_uses_and_costs_nothing(client):
    cid = await _fighter(client, 9)
    await _save(client, cid, die=2)
    await _after(client, cid, IND, dice=[5])
    await _save(client, cid, die=2)
    r = await _after(client, cid, IND, dice=[5])
    assert r.status_code == 409 and r.json()["detail"]["code"] == "option_unavailable"


async def test_indomitable_returns_with_a_long_rest_and_not_with_a_short_one(client):
    cid = await _fighter(client, 13)
    for _ in range(2):
        await _save(client, cid, die=2)
        assert (await _after(client, cid, IND, dice=[5])).status_code == 200
    await _rest(client, cid, "short")
    assert (await _ability(client, cid, IND))["uses"] == 0
    await _rest(client, cid, "long")
    assert (await _ability(client, cid, IND))["uses"] == 2


async def test_indomitable_rerolls_a_concentration_save_too(client):
    cid = await _fighter(client, 9)
    spell = (await client.post(f"/characters/{cid}/spells", json={"name": "Benedizione", "level": 1, "is_concentration": True})).json()["id"]
    await client.patch(f"/characters/{cid}/concentration", json={"spell_id": spell})
    first = (await client.post(f"/characters/{cid}/concentration/save", json={"damage": 40, "dice": [2]})).json()
    assert first["success"] is False
    r = await _after(client, cid, IND, dice=[20])
    assert r.status_code == 200, r.text
    assert r.json()["concentration"]["success"] is True and r.json()["concentration"]["die"] == 20


# ---------------------------------------------------------------------------
# Campione
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,die,critical", [
    (3, 18, False), (3, 19, True), (3, 20, True), (14, 18, False), (15, 18, True), (15, 17, False), (20, 18, True)])
async def test_champion_critical_threshold(client, level, die, critical):
    cid = await _fighter(client, level, "champion")
    wid = await _blade(client, cid)
    assert (await _attack(client, cid, wid, die=die, confirm_extra_attack=True)).json()["is_critical"] is critical


@pytest.mark.parametrize("subclass", [None, "battle_master", "eldritch_knight"])
async def test_only_the_champion_has_the_larger_critical_range(client, subclass):
    cid = await _fighter(client, 15, subclass)
    wid = await _blade(client, cid)
    assert (await _attack(client, cid, wid, die=19, confirm_extra_attack=True)).json()["is_critical"] is False


async def test_champion_critical_range_applies_to_the_unarmed_strike_and_not_to_a_spell(client):
    cid = await _fighter(client, 5, "champion")
    r = await client.post(f"/characters/{cid}/attack/unarmed", json={"die": 19, "confirm_extra_attack": True})
    assert r.json()["is_critical"] is True
    spell = (await client.post(f"/characters/{cid}/spells", json={
        "name": "Raggio", "level": 0, "attack_save": "ATK", "damage_dice": "1d10", "damage_type": "fire"})).json()["id"]
    r = await client.post(f"/characters/{cid}/spells/{spell}/attack", json={"die": 19})
    assert r.status_code == 200, r.text
    assert r.json()["is_critical"] is False


async def test_champion_critical_doubles_the_weapon_dice(client):
    cid = await _fighter(client, 5, "champion")
    wid = await _blade(client, cid, damage_dice="1d8")
    assert len((await _attack(client, cid, wid, die=19, confirm_extra_attack=True)).json()["damage_rolls"]) == 2
    assert len((await _attack(client, cid, wid, die=18, confirm_extra_attack=True)).json()["damage_rolls"]) == 1


async def test_remarkable_athlete_adds_half_proficiency_rounded_up_to_unproficient_physical_checks(client):
    plain = await _fighter(client, 6, "battle_master")  # competenza +3
    athlete = await _fighter(client, 7, "champion")  # competenza +3: metà per eccesso = 2
    low = await _fighter(client, 6, "champion")
    bonus = {}
    for name, cid in (("plain", plain), ("athlete", athlete), ("low", low)):
        full = await _full(client, cid)
        bonus[name] = full["skill_bonuses"]
    assert bonus["athlete"]["athletics"] - bonus["plain"]["athletics"] == 2
    assert bonus["athlete"]["acrobatics"] - bonus["plain"]["acrobatics"] == 2
    assert bonus["athlete"]["perception"] == bonus["plain"]["perception"]  # Saggezza: no
    assert bonus["low"]["athletics"] == bonus["plain"]["athletics"]  # prima del 7°: no


@pytest.mark.parametrize("level,half", [(7, 2), (8, 2), (9, 2), (13, 3), (17, 3)])
async def test_remarkable_athlete_rounds_up_at_every_proficiency(client, level, half):
    base = (await _full(client, await _fighter(client, level, "battle_master")))["skill_bonuses"]["stealth"]
    assert (await _full(client, await _fighter(client, level, "champion")))["skill_bonuses"]["stealth"] - base == half


async def test_remarkable_athlete_does_not_stack_with_proficiency(client):
    plain, athlete = await _fighter(client, 7, "battle_master"), await _fighter(client, 7, "champion")
    for cid in (plain, athlete):
        await client.patch(f"/characters/{cid}/skills", json={"skills": {"athletics": True, "acrobatics": "expert"}})
    a, b = (await _full(client, plain))["skill_bonuses"], (await _full(client, athlete))["skill_bonuses"]
    assert a["athletics"] == b["athletics"] and a["acrobatics"] == b["acrobatics"]


async def test_remarkable_athlete_applies_to_plain_strength_checks_and_initiative_not_to_saves(client):
    plain, athlete = await _fighter(client, 7, "battle_master"), await _fighter(client, 7, "champion")
    totals = {}
    for name, cid in (("plain", plain), ("athlete", athlete)):
        r = await client.post(f"/characters/{cid}/ability_checks/strength/roll", json={"die": 10})
        assert r.status_code == 200, r.text
        totals[name] = r.json()["total"]
    assert totals["athlete"] - totals["plain"] == 2
    a = (await client.post(f"/characters/{plain}/saving_throws/dexterity/roll", json={"die": 10})).json()["total"]
    b = (await client.post(f"/characters/{athlete}/saving_throws/dexterity/roll", json={"die": 10})).json()["total"]
    assert a == b
    assert (await _full(client, athlete))["initiative_bonus"] - (await _full(client, plain))["initiative_bonus"] == 2


async def test_remarkable_athlete_and_jack_of_all_trades_give_the_larger_of_the_two(client):
    # guerriero 7 + bardo 6 = livello 13, competenza +5: Factotum dà 2, Atleta 3. Vale 3, non 5.
    both = {}
    for sub in ("champion", "battle_master"):
        cid = await _fighter(client, 7, sub)
        r = await client.post(f"/characters/{cid}/classes", json={"class_name": "bard", "level": 6, "hit_die": 8})
        assert r.status_code == 201, r.text
        both[sub] = (await _full(client, cid))["skill_bonuses"]["athletics"]
    assert both["champion"] - both["battle_master"] == 3 - 2


async def test_the_champion_chooses_a_second_style_at_level_10_and_others_do_not(client):
    champion, master = await _fighter(client, 10, "champion"), await _fighter(client, 10, "battle_master")
    styles = lambda full: [c for c in full["pending_choices"] if c.get("group") == "fighting_style"]  # noqa: E731
    assert [c["count"] for c in styles(await _full(client, champion))] == [2]
    assert [c["count"] for c in styles(await _full(client, master))] == [1]


# ---------------------------------------------------------------------------
# Sopravvissuto
# ---------------------------------------------------------------------------

async def _new_turn(client, cid):
    r = await client.post(f"/characters/{cid}/turn/new")
    assert r.status_code == 200, r.text


async def test_survivor_heals_five_plus_constitution_at_the_start_of_the_turn_up_to_half(client, test_session_factory):
    cid = await _fighter(client, 18, "champion", constitution=14)  # +2
    maximum = (await _full(client, cid))["hit_points"]
    await _hurt(test_session_factory, cid, maximum // 2)
    await _new_turn(client, cid)
    assert await _hp(client, cid) == maximum // 2 + 5 + 2
    await _new_turn(client, cid)  # ora ha più della metà: niente
    assert await _hp(client, cid) == maximum // 2 + 7


async def test_survivor_does_not_work_above_half_at_zero_or_without_the_subclass(client, test_session_factory):
    cid = await _fighter(client, 18, "champion")
    maximum = (await _full(client, cid))["hit_points"]
    await _hurt(test_session_factory, cid, maximum // 2 + 1)
    await _new_turn(client, cid)
    assert await _hp(client, cid) == maximum // 2 + 1
    await _hurt(test_session_factory, cid, 0)
    await _new_turn(client, cid)
    assert await _hp(client, cid) == 0
    other = await _fighter(client, 18, "battle_master")
    await _hurt(test_session_factory, other, 3)
    await _new_turn(client, other)
    assert await _hp(client, other) == 3


async def test_survivor_never_passes_the_maximum(client, test_session_factory):
    cid = await _fighter(client, 18, "champion", constitution=20)
    maximum = (await _full(client, cid))["hit_points"]
    await _hurt(test_session_factory, cid, maximum // 2)
    await _new_turn(client, cid)
    assert await _hp(client, cid) <= maximum


async def test_survivor_is_not_available_before_level_18(client, test_session_factory):
    cid = await _fighter(client, 17, "champion")
    await _hurt(test_session_factory, cid, 5)
    await _new_turn(client, cid)
    assert await _hp(client, cid) == 5


async def _champion_in_session(client, test_session_factory, level=18, subclass="Campione"):
    sid, cid = await seed_session(test_session_factory)
    as_user(PLAYER_ID)
    r = await client.post(f"/characters/{cid}/classes", json={
        "class_name": "fighter", "level": level, "hit_die": 10, "subclass": subclass})
    assert r.status_code == 201, r.text
    as_user(GM_ID)
    r = await client.post(f"/sessions/{sid}/encounter", json={"mode": "full"})
    assert r.status_code == 201, r.text
    enc = (await client.post(f"/sessions/{sid}/encounter/combatants",
                             json={"name": "Goblin", "count": 1, "initiative_mod": 0, "max_hp": 7, "ac": 15})).json()
    pc, goblin = (next(c for c in enc["combatants"] if c["kind"] == k)["id"] for k in ("pc", "monster"))
    as_user(PLAYER_ID)
    await client.post(f"/sessions/{sid}/encounter/combatants/{pc}/initiative", json={"die": 20})
    as_user(GM_ID)
    await client.post(f"/sessions/{sid}/encounter/combatants/{goblin}/initiative", json={"die": 1})
    return sid, cid


async def _start(client, sid):
    r = await client.post(f"/sessions/{sid}/encounter/start", json={})
    assert r.status_code == 200, r.text


async def _player_hp(client, cid) -> int:
    """I PF letti dal giocatore, poi si torna al GM che guida l'incontro."""
    as_user(PLAYER_ID)
    try:
        return await _hp(client, cid)
    finally:
        as_user(GM_ID)


async def test_survivor_heals_at_the_start_of_each_turn_of_an_encounter_and_the_undo_takes_it_back(client, test_session_factory):
    sid, cid = await _champion_in_session(client, test_session_factory)
    await _start(client, sid)
    await _hurt(test_session_factory, cid, 10)
    r = await client.post(f"/sessions/{sid}/encounter/next-turn")  # tocca al goblin
    assert r.status_code == 200, r.text
    assert await _player_hp(client, cid) == 10
    r = await client.post(f"/sessions/{sid}/encounter/next-turn")  # di nuovo il PG
    assert r.status_code == 200, r.text
    assert await _player_hp(client, cid) == 10 + 5
    as_user(PLAYER_ID)
    await _new_turn(client, cid)  # «Nuovo turno» in un incontro non cura una seconda volta
    as_user(GM_ID)
    assert await _player_hp(client, cid) == 15
    r = await client.post(f"/sessions/{sid}/encounter/prev-turn")
    assert r.status_code == 200, r.text
    assert await _player_hp(client, cid) == 10


async def test_survivor_heals_at_the_first_turn_of_the_encounter(client, test_session_factory):
    sid, cid = await _champion_in_session(client, test_session_factory)
    await _hurt(test_session_factory, cid, 10)
    await _start(client, sid)
    assert await _player_hp(client, cid) == 15


def _start_heal(turn: dict) -> list[dict]:
    return turn.get("start_heal") or []


async def test_survivor_says_how_much_it_healed_with_the_new_turn_button(client, test_session_factory):
    cid = await _fighter(client, 18, "champion", constitution=14)
    maximum = (await _full(client, cid))["hit_points"]
    await _hurt(test_session_factory, cid, maximum // 2)
    r = await client.post(f"/characters/{cid}/turn/new")
    assert r.status_code == 200, r.text
    (notice,) = _start_heal(r.json())
    assert (notice["feature_key"], notice["amount"]) == ("fighter.survivor", 7)
    assert notice["name"]["it"] == "Sopravvissuto" and notice["name"]["en"] == "Survivor"
    assert _start_heal(await _turn(client, cid)) == [notice]  # resta sul turno finché non ne comincia un altro
    r = await client.post(f"/characters/{cid}/turn/new")  # ora ha più della metà: niente da dire
    assert _start_heal(r.json()) == []


async def test_survivor_says_nothing_when_it_does_not_heal(client, test_session_factory):
    cid = await _fighter(client, 18, "champion")
    r = await client.post(f"/characters/{cid}/turn/new")
    assert _start_heal(r.json()) == []
    other = await _fighter(client, 18, "battle_master")
    await _hurt(test_session_factory, other, 3)
    assert _start_heal((await client.post(f"/characters/{other}/turn/new")).json()) == []


async def test_survivor_tells_the_player_at_each_turn_of_an_encounter(client, test_session_factory):
    sid, cid = await _champion_in_session(client, test_session_factory)
    await _hurt(test_session_factory, cid, 10)
    await _start(client, sid)  # primo turno: cura
    as_user(PLAYER_ID)
    assert [n["amount"] for n in _start_heal(await _turn(client, cid))] == [5]
    as_user(GM_ID)
    await client.post(f"/sessions/{sid}/encounter/next-turn")  # tocca al goblin: l'avviso è ancora quello del turno finito
    await client.post(f"/sessions/{sid}/encounter/next-turn")  # di nuovo il PG: 15 PF, cura ancora
    as_user(PLAYER_ID)
    assert [n["amount"] for n in _start_heal(await _turn(client, cid))] == [5]
    as_user(GM_ID)
    as_user(PLAYER_ID)
    maximum = (await _full(client, cid))["hit_points"]
    as_user(GM_ID)
    await _hurt(test_session_factory, cid, maximum)  # sopra la metà: il prossimo turno non cura e l'avviso sparisce
    await client.post(f"/sessions/{sid}/encounter/next-turn")
    await client.post(f"/sessions/{sid}/encounter/next-turn")
    as_user(PLAYER_ID)
    assert _start_heal(await _turn(client, cid)) == []


# ---------------------------------------------------------------------------
# Import da Beyond
# ---------------------------------------------------------------------------

async def test_beyond_option_names_find_the_styles_and_the_maneuvers(test_session_factory):
    from api.services.ddb_import import apply_class_options
    from api.services.ddb_import import ImportReport
    from core.rules.sample_characters import build_rules_character

    async with test_session_factory() as s:
        char = await build_rules_character(s, {"name": "x", "edition": "2014",
                                               "classes": [("Guerriero", 10, "Maestro di Battaglia", 10)]}, 1)
        report = ImportReport()
        names = ("Great Weapon Fighting", "Goading Attack", "Trip Attack", "Commander's Strike", "Riposte", "Rally",
                 "Sweeping Attack", "Evasive Footwork", "Dragon Slayer")
        apply_class_options(char, [{"class_index": 0, "name": n} for n in names], report, "it")
        options = char.classes[0].options
        assert options["fighting_style"] == ["great_weapon"]
        assert options["maneuvers"] == ["goading", "trip", "commanders_strike", "riposte", "rally", "sweeping", "evasive_footwork"]
        assert [e.name for e in report.approximated] == ["Dragon Slayer"]


# ---------------------------------------------------------------------------
# Passaggio al catalogo dei personaggi esistenti (R33, R17)
# ---------------------------------------------------------------------------

async def test_migration_keeps_spent_uses_and_does_not_duplicate_the_automatic_rows(client, test_session_factory):
    from sqlalchemy import select
    from api.services.catalog_migration import migrate_catalog
    from core.db.models import Ability

    master = await _fighter(client, 9, "battle_master")
    champion = await _fighter(client, 9, "champion")
    async with test_session_factory() as s:  # lo stato di prima del catalogo: nomi vecchi, usi spesi, i dadi anche a un Campione
        for a in (await s.execute(select(Ability).where(Ability.character_id == master))).scalars():
            if a.feature_key in (SW, IND, SD, AS):
                a.name, a.uses = {SW: "Secondo Vento", IND: "Indomabile", SD: "Dadi Superiorità", AS: "Azione Impetuosa"}[a.feature_key], 0
        champ = (await s.execute(select(Ability).where(Ability.character_id == champion, Ability.feature_key == SW))).scalar_one()
        s.add(Ability(character_id=champion, source_class_id=champ.source_class_id, is_class_feature=True, feature_key=SD,
                      name="Dadi Superiorità", max_uses=4, uses=4, is_active=True, is_passive=False))
        await s.commit()
    assert await migrate_catalog(test_session_factory) >= 1
    rows = (await _full(client, master))["abilities"]
    for key, name in ((SW, "Recuperare Energie"), (IND, "Indomito"), (SD, "Dadi di Superiorità"), (AS, "Azione Impetuosa")):
        mine = [a for a in rows if a["feature_key"] == key]
        assert len(mine) == 1 and mine[0]["name"] == name and mine[0]["uses"] == 0  # un solo uso speso resta speso
    assert SD not in await _keys_of(client, champion)  # non è un Maestro di Battaglia: la riga se ne va


async def test_two_simultaneous_uses_of_action_surge_spend_the_single_use_once(client):  # Task 28, I6: spesa comune
    import asyncio
    cid = await _fighter(client, 2)
    r = await asyncio.gather(*(client.post(f"/characters/{cid}/features/{AS}/use", json={}) for _ in range(2)))
    assert sorted(x.status_code for x in r) == [200, 409], [x.text for x in r]
