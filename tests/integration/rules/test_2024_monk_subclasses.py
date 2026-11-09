"""Monaco 2024 (Task 36, parte B): Guerriero della Misericordia, dell'Ombra, degli Elementi e della Mano Aperta.
Valori dalla scheda ``docs/superpowers/rules/2024/classes/monk.md``."""
from __future__ import annotations

import pytest

from core.rules.catalog import features_for
from tests.integration.rules.test_2014_bard import _ability, _full, _keys_of, _roll_keys, _spells, _use
from tests.integration.rules.test_2014_monk import _rest, _turn
from tests.integration.rules.test_2014_monk_ki import (
    _conditions, _damage, _fixed, _hit, _ki, _set_ki, _shortsword, _states, _strike,
)
from tests.integration.rules.test_2024_monk import FLURRY, STEP, STRIKE, _new_turn

SUBS = {"mercy": "Guerriero della Misericordia", "shadow": "Guerriero dell'Ombra", "elements": "Guerriero degli Elementi",
        "open_hand": "Guerriero della Mano Aperta"}
HARM, HARM_POISON = "monk.hand_of_harm", "monk.hand_of_harm_poisoned"
HARM_FREE, HARM_FREE_POISON = "monk.hand_of_harm_free", "monk.hand_of_harm_free_poisoned"
HEAL, HEAL_FLURRY, HEAL_FREE = "monk.hand_of_healing", "monk.hand_of_healing_flurry", "monk.flurry_of_healing_and_harm"
MERCY_POOL, ULTIMATE = "monk.flurry_of_healing_and_harm", "monk.hand_of_ultimate_mercy"
SHADOW_STEP, IMPROVED, CLOAK, SHADOW_FLURRY = ("monk.shadow_step", "monk.improved_shadow_step", "monk.cloak_of_shadows",
                                               "monk.shadow_flurry")
STEP_ADVANTAGE, STEP_STRIKE = "monk.shadow_step_advantage", "monk.shadow_step_strike"
ATTUNE, BURST, EPITOME = "monk.elemental_attunement", "monk.elemental_burst", "monk.elemental_epitome"
PUSH_EL = "monk.elemental_push"
ADDLE, PUSH, TOPPLE = "monk.open_hand_addle", "monk.open_hand_push", "monk.open_hand_topple"
WHOLENESS, FLEET, FLEET_FOCUS = "monk.wholeness_of_body", "monk.fleet_step", "monk.fleet_step_focus"
PALM, PALM_ATTACK, PALM_START = "monk.quivering_palm", "monk.quivering_palm_attack", "monk.quivering_palm_start"
LIGHT = {"light": "dim_or_dark"}


def _elemental(kind: str) -> str:
    return f"monk.elemental_strike_{kind}"


async def _sub(client, sub, level=3, **scores) -> int:
    body = {"name": "Monaco", "initial_class": {"class_name": "monk", "level": level, "subclass": SUBS[sub]}}
    r = await client.post("/characters", json=body)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    for ability, value in scores.items():
        assert (await client.patch(f"/characters/{cid}/ability_scores/{ability}", json={"value": value})).status_code == 200
    return cid


async def _hurt(client, cid, current, maximum=60):
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": maximum})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": current})


async def _flurry_hit(client, cid, **body):
    """Un colpo della Raffica di Colpi, a segno e con il danno ancora da tirare."""
    await _strike(client, cid)  # l'azione Attacco
    assert (await _use(client, cid, FLURRY)).status_code == 200
    return await _hit(client, cid, options=[STRIKE], **body)


async def _target(client, cid, key) -> dict:
    return (await client.get(f"/characters/{cid}/target-effects/{key}")).json()["result"]


# ---------------------------------------------------------------------------
# Catalogo e livelli
# ---------------------------------------------------------------------------

ROWS = {
    "mercy": {3: {"hand_of_harm", "hand_of_healing", "hand_of_healing_flurry", "implements_of_mercy"}, 6: {"physicians_touch"},
              11: {"flurry_of_healing_and_harm"}, 17: {"hand_of_ultimate_mercy"}},
    "shadow": {3: {"shadow_arts"}, 6: {"shadow_step"}, 11: {"improved_shadow_step"}, 17: {"cloak_of_shadows", "shadow_flurry"}},
    "elements": {3: {"elemental_attunement", "manipulate_elements"}, 6: {"elemental_burst"}, 11: {"stride_of_the_elements"},
                 17: {"elemental_epitome"}},
    "open_hand": {3: {"open_hand_technique", "addle", "push", "topple"}, 6: {"wholeness_of_body"}, 11: {"fleet_step", "fleet_step_focus"},
                  17: {"quivering_palm", "quivering_palm_attack"}},
}


@pytest.mark.parametrize("sub,level,present", [(s, lv, keys) for s, levels in ROWS.items() for lv, keys in levels.items()])
async def test_each_subclass_row_appears_at_its_level_and_only_for_its_own_subclass(client, sub, level, present):
    keys = await _keys_of(client, await _sub(client, sub, level))
    assert {f"monk.{k}" for k in present} <= keys
    low = await _keys_of(client, await _sub(client, sub, max(3, level - 1) if level > 3 else 3))
    if level > 3:
        assert not {f"monk.{k}" for k in present} & low
    for other in set(SUBS) - {sub}:
        assert not {f"monk.{k}" for k in present} & await _keys_of(client, await _sub(client, other, level))


def test_every_subclass_row_names_a_subclass_known_to_the_subclass_table():
    rows = [s for s in features_for("2024", "monk") if s.subclass]
    assert {s.subclass for s in rows} == set(SUBS)
    assert len(rows) >= 22  # una riga per ogni privilegio di sottoclasse della mappatura


# ---------------------------------------------------------------------------
# Guerriero della Misericordia
# ---------------------------------------------------------------------------

async def test_hand_of_harm_is_for_unarmed_hits_spends_a_point_and_adds_a_necrotic_martial_die(client):
    cid = await _sub(client, "mercy", 3, wisdom=16, dexterity=16)
    assert HARM in await _roll_keys(client, cid, "attack")
    sword = await _shortsword(client, cid)
    assert HARM not in await _roll_keys(client, cid, "attack", item_id=sword)
    await client.patch(f"/characters/{cid}/items/{sword}", json={"is_equipped": False})
    hit = await _hit(client, cid)
    body = (await _damage(client, cid, hit, HARM)).json()
    assert await _ki(client, cid) == 2 and len(body["option_result"]["extra_rolls"]) == 1
    assert "necrotic" in body["option_result"]["effects"][0]["en"] and "necrotici" in body["option_result"]["effects"][0]["it"]
    assert "poisoned" not in (await _full(client, cid))["conditions"]


async def test_hand_of_harm_is_once_per_turn_and_needs_a_point(client):
    cid = await _sub(client, "mercy", 3, dexterity=16)
    assert (await _damage(client, cid, await _hit(client, cid), HARM)).status_code == 200
    r = await _damage(client, cid, await _hit(client, cid), HARM)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "option_unavailable" and await _ki(client, cid) == 2
    await _new_turn(client, cid)
    assert HARM in await _roll_keys(client, cid, "attack")
    await _set_ki(client, cid, 0)
    assert HARM not in await _roll_keys(client, cid, "attack")


async def test_hand_of_harm_is_not_offered_to_the_other_subclasses(client):
    assert HARM not in await _roll_keys(client, await _sub(client, "open_hand", 3), "attack")


async def test_physicians_touch_adds_the_poisoned_variant_from_level_6_until_the_end_of_the_next_turn(client):
    low = await _sub(client, "mercy", 5, wisdom=16, dexterity=16)
    assert HARM_POISON not in await _roll_keys(client, low, "attack")
    cid = await _sub(client, "mercy", 6, wisdom=16, dexterity=16)
    assert {HARM, HARM_POISON} <= set(await _roll_keys(client, cid, "attack"))
    hit = await _hit(client, cid)
    assert (await _damage(client, cid, hit, HARM_POISON)).status_code == 200
    assert await _ki(client, cid) == 5
    effect = await _target(client, cid, HARM_POISON)
    assert effect["condition"] == "poisoned" and not effect["save_ability"]
    assert effect["ends_at"] == {"anchor": "source", "edge": "end", "count": 1}
    again = await _hit(client, cid)
    assert (await _damage(client, cid, again, HARM, HARM_POISON)).status_code == 409  # un solo uso per turno


async def test_hand_of_healing_costs_a_point_and_the_action_and_heals_a_martial_die_plus_wisdom(client, monkeypatch):
    cid = await _sub(client, "mercy", 3, wisdom=16)
    await _hurt(client, cid, 10)
    _fixed(monkeypatch, 4)
    r = await _use(client, cid, HEAL, params={"mode": "self"})
    assert r.status_code == 200, r.text
    assert r.json()["healed"] == 4 + 3 and (await _full(client, cid))["current_hit_points"] == 17
    assert await _ki(client, cid) == 2 and (await _turn(client, cid))["action_used"] is True
    row = await _ability(client, cid, HEAL)
    assert row["ally_modes"] == ["other"]


async def test_hand_of_healing_on_another_creature_reports_the_amount_and_spends_the_point(client, monkeypatch):
    cid = await _sub(client, "mercy", 3, wisdom=16)
    _fixed(monkeypatch, 5)
    r = await _use(client, cid, HEAL, params={"mode": "other"})
    assert r.status_code == 200, r.text
    assert r.json()["given"] == 5 + 3 and r.json()["healed"] == 0 and await _ki(client, cid) == 2


async def test_hand_of_healing_is_refused_without_points_or_action_and_costs_nothing(client):
    cid = await _sub(client, "mercy", 3, wisdom=16)
    await client.post(f"/characters/{cid}/turn/use", json={"slot": "action"})
    r = await _use(client, cid, HEAL, params={"mode": "self"})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "turn_slot_used" and await _ki(client, cid) == 3
    await _new_turn(client, cid)
    await _set_ki(client, cid, 0)
    assert (await _use(client, cid, HEAL, params={"mode": "self"})).json()["detail"]["code"] == "no_uses"


async def test_hand_of_healing_ends_a_condition_on_yourself_only_from_level_6(client):
    low = await _sub(client, "mercy", 3)
    assert [c["key"] for c in (await _ability(client, low, HEAL))["use_choices"]] == ["mode"] and not (await _ability(client, low, HEAL))["removal"]
    cid = await _sub(client, "mercy", 6)
    await _conditions(client, cid, poisoned=True, stunned=True, charmed=True)
    row = await _ability(client, cid, HEAL)
    assert [o["key"] for o in row["removal"]["conditions"]] == ["blinded", "deafened", "paralyzed", "poisoned", "stunned"]
    assert row["removal"]["bound"] and row["removal"]["optional"]
    assert (await _use(client, cid, HEAL, params={"mode": "self", "removal": {"targets": ["self"], "conditions": ["poisoned"]}})).status_code == 200
    conditions = (await _full(client, cid))["conditions"]
    assert not conditions.get("poisoned") and conditions["stunned"] and conditions["charmed"]


async def test_one_flurry_strike_can_become_a_free_hand_of_healing(client, monkeypatch):
    cid = await _sub(client, "mercy", 3, wisdom=16)
    await _hurt(client, cid, 10)
    assert (await _use(client, cid, HEAL_FLURRY, params={"mode": "self"})).json()["detail"]["code"] == "feature_unavailable"
    await _strike(client, cid)
    assert (await _use(client, cid, FLURRY)).status_code == 200
    _fixed(monkeypatch, 2)
    r = await _use(client, cid, HEAL_FLURRY, params={"mode": "self"})
    assert r.status_code == 200, r.text
    assert r.json()["healed"] == 2 + 3 and await _ki(client, cid) == 2  # solo il punto della Raffica
    assert (await _states(client, cid))["flurry_of_blows"]["data"]["charges"] == 1
    again = await _use(client, cid, HEAL_FLURRY, params={"mode": "self"})
    assert again.status_code == 409 and again.json()["detail"]["code"] == "once_per_turn"


async def test_flurry_of_healing_and_harm_has_wisdom_modifier_uses_with_a_minimum_of_one(client):
    row = await _ability(client, await _sub(client, "mercy", 11, wisdom=16), MERCY_POOL)
    assert (row["uses"], row["max_uses"], row["restoration_type"]) == (3, 3, "long_rest")
    assert (await _ability(client, await _sub(client, "mercy", 11, wisdom=8), MERCY_POOL))["max_uses"] == 1


async def test_from_level_11_every_strike_of_the_flurry_can_be_healing_for_a_use_of_the_pool(client, monkeypatch):
    cid = await _sub(client, "mercy", 11, wisdom=16)
    await _hurt(client, cid, 10)
    await _strike(client, cid)
    await _use(client, cid, FLURRY)
    _fixed(monkeypatch, 3)
    for left in (2, 1):
        r = await _use(client, cid, HEAL_FREE, params={"mode": "self"})
        assert r.status_code == 200, r.text
        assert (await _ability(client, cid, MERCY_POOL))["uses"] == left
    assert (await _states(client, cid))["flurry_of_blows"]["data"]["charges"] == 1
    assert await _ki(client, cid) == 10  # nessun punto oltre quello della Raffica
    await _rest(client, cid, "short")
    assert (await _ability(client, cid, MERCY_POOL))["uses"] == 1
    await _rest(client, cid, "long")
    assert (await _ability(client, cid, MERCY_POOL))["uses"] == 3


async def test_free_hand_of_harm_on_a_flurry_hit_spends_a_use_of_the_pool_and_no_point(client):
    cid = await _sub(client, "mercy", 11, wisdom=16, dexterity=16)
    plain = await _hit(client, cid)
    assert (await _damage(client, cid, plain, HARM_FREE)).status_code == 409  # solo sui colpi della Raffica
    await _new_turn(client, cid)
    hit = await _flurry_hit(client, cid)
    ki = await _ki(client, cid)
    body = (await _damage(client, cid, hit, HARM_FREE)).json()
    assert await _ki(client, cid) == ki and (await _ability(client, cid, MERCY_POOL))["uses"] == 2
    assert len(body["option_result"]["extra_rolls"]) == 1
    second = await _hit(client, cid, options=[STRIKE])
    assert (await _damage(client, cid, second, HARM_FREE_POISON)).status_code == 409  # Mano del Danno è una volta per turno


async def test_hand_of_ultimate_mercy_costs_five_points_once_per_long_rest_and_gives_4d10_plus_wisdom(client, monkeypatch):
    cid = await _sub(client, "mercy", 17, wisdom=16)
    _fixed(monkeypatch, 5)
    r = await _use(client, cid, ULTIMATE)
    assert r.status_code == 200, r.text
    assert len(r.json()["rolls"]) == 4 and r.json()["given"] == 4 * 5 + 3
    assert await _ki(client, cid) == 12 and (await _turn(client, cid))["action_used"] is True
    await _new_turn(client, cid)
    assert (await _use(client, cid, ULTIMATE)).json()["detail"]["code"] == "feature_unavailable"
    await _rest(client, cid, "short")
    assert (await _use(client, cid, ULTIMATE)).status_code == 409
    await _rest(client, cid, "long")
    assert (await _use(client, cid, ULTIMATE)).status_code == 200


async def test_hand_of_ultimate_mercy_is_refused_with_fewer_than_five_points_and_costs_nothing(client):
    cid = await _sub(client, "mercy", 17)
    await _set_ki(client, cid, 4)
    r = await _use(client, cid, ULTIMATE)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_uses"
    assert await _ki(client, cid) == 4 and not (await _turn(client, cid))["action_used"]
    await _set_ki(client, cid, 5)
    assert (await _use(client, cid, ULTIMATE)).status_code == 200


async def test_implements_of_mercy_grants_insight_medicine_and_the_herbalism_kit(client):
    cid = await _sub(client, "mercy", 3)
    sheet = await _full(client, cid)
    assert sheet["skills"]["insight"] and sheet["skills"]["medicine"]
    assert any("erborista" in t.lower() for t in sheet["general_proficiencies"]["tools"])
    other = await _full(client, await _sub(client, "shadow", 3))
    assert not other["skills"].get("medicine")


# ---------------------------------------------------------------------------
# Guerriero dell'Ombra
# ---------------------------------------------------------------------------

async def test_shadow_arts_gives_darkness_for_a_point_minor_illusion_and_darkvision(client):
    cid = await _sub(client, "shadow", 3, wisdom=16)
    spells = await _spells(client, cid)
    assert {"Oscurità", "Illusione minore"} <= set(spells)
    assert spells["Oscurità"]["ki_cast"]["cost"] == 1 and spells["Illusione minore"]["level"] == 0
    assert (await _full(client, cid))["computed"]["senses"] == [{"type": "darkvision", "range_ft": 60}]


async def test_shadow_arts_darkvision_adds_sixty_feet_to_the_one_already_owned(client):
    cid = await _sub(client, "shadow", 3)
    await client.patch(f"/characters/{cid}", json={"settings": {"senses": [{"type": "darkvision", "range_ft": 60}]}})
    assert (await _full(client, cid))["computed"]["senses"] == [{"type": "darkvision", "range_ft": 120}]


async def test_a_darkness_cast_for_a_point_spends_the_point_and_the_other_subclasses_do_not_have_it(client):
    cid = await _sub(client, "shadow", 3)
    spell = (await _spells(client, cid))["Oscurità"]
    r = await client.post(f"/characters/{cid}/spells/{spell['id']}/use", json={"ki": True})
    assert r.status_code == 200, r.text
    assert await _ki(client, cid) == 2
    assert "Oscurità" not in await _spells(client, await _sub(client, "open_hand", 3))


async def test_shadow_step_needs_the_light_confirmed_costs_nothing_and_gives_advantage_once(client):
    cid = await _sub(client, "shadow", 6, dexterity=16)
    r = await _use(client, cid, SHADOW_STEP, params={})
    assert r.status_code == 422 and not (await _turn(client, cid))["bonus_used"]
    assert (await _use(client, cid, SHADOW_STEP, params=LIGHT)).status_code == 200
    assert (await _turn(client, cid))["bonus_used"] is True and await _ki(client, cid) == 6
    r = await _strike(client, cid, STEP_ADVANTAGE)
    assert r.status_code == 200 and r.json()["mode"] == "advantage"
    assert (await _strike(client, cid, STEP_ADVANTAGE)).status_code == 409


async def test_improved_shadow_step_costs_a_point_ignores_the_light_and_allows_an_unarmed_strike_right_after(client):
    cid = await _sub(client, "shadow", 11, dexterity=16)
    assert STEP_STRIKE not in await _roll_keys(client, cid, "attack")
    row = await _ability(client, cid, IMPROVED)
    assert row["action_type"] == "bonus_action" and not row["use_choices"]
    assert (await _use(client, cid, IMPROVED)).status_code == 200
    assert await _ki(client, cid) == 10 and (await _turn(client, cid))["bonus_used"] is True
    assert STEP_STRIKE in await _roll_keys(client, cid, "attack")
    r = await _strike(client, cid, STEP_STRIKE)
    assert r.status_code == 200, r.text
    assert (await _turn(client, cid))["action_attacks"] == 0  # parte della stessa azione bonus
    assert STEP_STRIKE not in await _roll_keys(client, cid, "attack")


async def test_improved_shadow_step_is_refused_without_a_point_or_the_bonus_action(client):
    cid = await _sub(client, "shadow", 11)
    await _set_ki(client, cid, 0)
    assert (await _use(client, cid, IMPROVED)).json()["detail"]["code"] == "no_uses"
    await _set_ki(client, cid, 3)
    await client.post(f"/characters/{cid}/turn/use", json={"slot": "bonus"})
    assert (await _use(client, cid, IMPROVED)).json()["detail"]["code"] == "turn_slot_used" and await _ki(client, cid) == 3


async def test_cloak_of_shadows_costs_three_points_and_makes_the_monk_invisible_for_a_minute(client):
    cid = await _sub(client, "shadow", 17, dexterity=16)
    r = await _use(client, cid, CLOAK, params={})
    assert r.status_code == 422 and await _ki(client, cid) == 17
    assert (await _use(client, cid, CLOAK, params=LIGHT)).status_code == 200
    assert await _ki(client, cid) == 14 and (await _turn(client, cid))["action_used"] is True
    assert (await _full(client, cid))["conditions"]["invisible"] is True
    state = (await _states(client, cid))["cloak_of_shadows"]
    assert state["rounds_left"] == 10 and "incapacitated" in state["ends_on"] and "attack" not in state["ends_on"]
    assert (await _strike(client, cid)).status_code == 200  # attaccare non la interrompe
    assert "cloak_of_shadows" in await _states(client, cid)


async def test_cloak_of_shadows_is_refused_without_three_points_and_ends_when_incapacitated(client):
    cid = await _sub(client, "shadow", 17)
    await _set_ki(client, cid, 2)
    assert (await _use(client, cid, CLOAK, params=LIGHT)).json()["detail"]["code"] == "no_uses"
    await _set_ki(client, cid, 10)
    await _use(client, cid, CLOAK, params=LIGHT)
    await _conditions(client, cid, incapacitated=True)
    assert "cloak_of_shadows" not in await _states(client, cid)


async def test_shadow_flurry_is_a_free_flurry_only_while_the_cloak_is_on(client):
    cid = await _sub(client, "shadow", 17, dexterity=16)
    assert (await _use(client, cid, SHADOW_FLURRY)).json()["detail"]["code"] == "feature_unavailable"
    await _use(client, cid, CLOAK, params=LIGHT)
    await _new_turn(client, cid)
    ki = await _ki(client, cid)
    assert (await _use(client, cid, SHADOW_FLURRY)).status_code == 200
    assert await _ki(client, cid) == ki and (await _turn(client, cid))["bonus_used"] is True
    assert (await _states(client, cid))["flurry_of_blows"]["data"]["charges"] == 3


# ---------------------------------------------------------------------------
# Guerriero degli Elementi
# ---------------------------------------------------------------------------

async def test_elemental_attunement_costs_a_point_and_lasts_ten_minutes_with_three_metres_more_reach(client):
    cid = await _sub(client, "elements", 3, dexterity=16)
    assert _elemental("fire") not in await _roll_keys(client, cid, "attack")
    assert (await _use(client, cid, ATTUNE)).status_code == 200
    assert await _ki(client, cid) == 2
    state = (await _states(client, cid))["elemental_attunement"]
    assert state["rounds_left"] == 100 and "incapacitated" in state["ends_on"] and state["data"]["reach_bonus_ft"] == 10
    await _set_ki(client, cid, 0)
    await client.delete(f"/characters/{cid}/active-states/elemental_attunement")
    assert (await _use(client, cid, ATTUNE)).json()["detail"]["code"] == "no_uses"


async def test_attunement_ends_when_incapacitated_and_a_short_rest_ends_it_after_ten_minutes(client):
    cid = await _sub(client, "elements", 3)
    await _use(client, cid, ATTUNE)
    await _rest(client, cid, "short")
    assert "elemental_attunement" not in await _states(client, cid)
    await _use(client, cid, ATTUNE)
    await _conditions(client, cid, incapacitated=True)
    assert "elemental_attunement" not in await _states(client, cid)


@pytest.mark.parametrize("kind", ["acid", "cold", "fire", "lightning", "thunder"])
async def test_the_unarmed_strike_deals_the_chosen_element_while_attuned(client, kind):
    cid = await _sub(client, "elements", 3, dexterity=16)
    await _use(client, cid, ATTUNE)
    keys = await _roll_keys(client, cid, "attack")
    assert {_elemental(k) for k in ("acid", "cold", "fire", "lightning", "thunder")} <= set(keys)
    assert (await _strike(client, cid, _elemental(kind))).json()["damage_type"] == kind
    await _new_turn(client, cid)
    assert (await _strike(client, cid)).json()["damage_type"] == "bludgeoning"


async def test_the_elements_are_one_per_strike_and_not_for_monk_weapons(client):
    cid = await _sub(client, "elements", 3, dexterity=16)
    await _use(client, cid, ATTUNE)
    assert (await _strike(client, cid, _elemental("fire"), _elemental("cold"))).status_code == 409
    sword = await _shortsword(client, cid)
    assert _elemental("fire") not in await _roll_keys(client, cid, "attack", item_id=sword)


async def test_the_elemental_push_needs_an_element_and_shows_the_strength_save_with_the_focus_dc(client):
    cid = await _sub(client, "elements", 3, dexterity=16, wisdom=16)
    await _use(client, cid, ATTUNE)
    plain = await _hit(client, cid)
    assert (await _damage(client, cid, plain, PUSH_EL)).status_code == 409
    await _new_turn(client, cid)
    hit = await _hit(client, cid, options=[_elemental("cold")])
    body = (await _damage(client, cid, hit, PUSH_EL)).json()
    assert "CD 13" in body["option_result"]["effects"][0]["it"] and "3 m" in body["option_result"]["effects"][0]["it"]
    effect = await _target(client, cid, PUSH_EL)
    assert (effect["save_ability"], effect["save_dc"]) == ("strength", 13) and not effect["condition"]
    assert await _ki(client, cid) == 2  # la spinta non costa nulla


async def test_manipulate_elements_teaches_elementalism_with_wisdom(client):
    assert "Elementalismo" in await _spells(client, await _sub(client, "elements", 3))
    assert "Elementalismo" not in await _spells(client, await _sub(client, "mercy", 3))


async def test_elemental_burst_costs_two_points_the_action_and_rolls_three_martial_dice(client):
    cid = await _sub(client, "elements", 6, dexterity=16, wisdom=16)  # d8, competenza +3, Saggezza +3
    row = await _ability(client, cid, BURST)
    assert row["action_type"] == "action"
    assert (await _use(client, cid, BURST, params={})).status_code == 422 and await _ki(client, cid) == 6
    r = await _use(client, cid, BURST, params={"element": "fire"})
    assert r.status_code == 200, r.text
    assert len(r.json()["rolls"]) == 3 and await _ki(client, cid) == 4 and (await _turn(client, cid))["action_used"] is True
    effect = await _target(client, cid, BURST)
    assert (effect["save_ability"], effect["save_dc"], effect["damage_dice"], effect["on_failure_only"]) == ("dexterity", 14, "3d8", False)


async def test_elemental_burst_dice_follow_the_martial_arts_die_and_need_two_points(client):
    cid = await _sub(client, "elements", 11, dexterity=16)
    assert (await _use(client, cid, BURST, params={"element": "cold"})).status_code == 200
    assert (await _target(client, cid, BURST))["damage_dice"] == "3d10"
    await _new_turn(client, cid)
    await _set_ki(client, cid, 1)
    assert (await _use(client, cid, BURST, params={"element": "cold"})).json()["detail"]["code"] == "no_uses"


async def test_stride_of_the_elements_gives_fly_and_swim_equal_to_the_speed_only_while_attuned(client):
    cid = await _sub(client, "elements", 11)
    computed = (await _full(client, cid))["computed"]
    assert not computed.get("fly_speed") and not computed.get("swim_speed")
    await _use(client, cid, ATTUNE)
    computed = (await _full(client, cid))["computed"]
    assert computed["fly_speed"] == computed["swim_speed"] and computed["fly_speed"] > 0
    low = await _sub(client, "elements", 10)
    await _use(client, low, ATTUNE)
    assert not (await _full(client, low))["computed"].get("fly_speed")


async def test_elemental_epitome_gives_one_chosen_resistance_while_attuned_and_changes_with_a_choice(client):
    cid = await _sub(client, "elements", 17)
    await _use(client, cid, ATTUNE)
    assert (await _use(client, cid, EPITOME, params={})).status_code == 422
    assert (await _use(client, cid, EPITOME, params={"element": "fire"})).status_code == 200
    resistances = set((await _full(client, cid))["computed"]["resistances"])
    assert "fire" in resistances and "cold" not in resistances
    assert (await _use(client, cid, EPITOME, params={"element": "cold"})).status_code == 200
    resistances = set((await _full(client, cid))["computed"]["resistances"])
    assert "cold" in resistances and "fire" not in resistances


async def test_elemental_epitome_does_nothing_without_the_attunement(client):
    cid = await _sub(client, "elements", 17)
    assert (await _use(client, cid, EPITOME, params={"element": "fire"})).json()["detail"]["code"] == "feature_unavailable"


async def test_destructive_stride_adds_twenty_feet_to_step_of_the_wind_only_while_attuned(client):
    cid = await _sub(client, "elements", 17)
    await _use(client, cid, STEP)
    plain = (await _full(client, cid))["computed"]["speed"]
    await _new_turn(client, cid)
    await _use(client, cid, ATTUNE)
    await _use(client, cid, STEP)
    assert (await _full(client, cid))["computed"]["speed"] == plain + 20


async def test_the_epitome_adds_a_martial_die_of_damage_once_per_turn_on_unarmed_hits_while_attuned(client):
    cid = await _sub(client, "elements", 17, dexterity=16)
    key = "monk.elemental_epitome_strike"
    assert key not in await _roll_keys(client, cid, "attack")
    await _use(client, cid, ATTUNE)
    assert key in await _roll_keys(client, cid, "attack")
    body = (await _damage(client, cid, await _hit(client, cid), key)).json()
    assert len(body["option_result"]["extra_rolls"]) == 1
    assert (await _damage(client, cid, await _hit(client, cid), key)).status_code == 409


# ---------------------------------------------------------------------------
# Guerriero della Mano Aperta
# ---------------------------------------------------------------------------

async def test_the_technique_is_offered_only_on_the_hits_of_the_flurry(client):
    cid = await _sub(client, "open_hand", 3, wisdom=16, dexterity=16)
    plain = await _hit(client, cid)
    assert not {ADDLE, PUSH, TOPPLE} & set(await _roll_keys(client, cid, "attack"))
    assert (await _damage(client, cid, plain, TOPPLE)).status_code == 409
    await _new_turn(client, cid)
    await _flurry_hit(client, cid)
    assert {ADDLE, PUSH, TOPPLE} <= set(await _roll_keys(client, cid, "attack"))
    assert not {ADDLE, PUSH, TOPPLE} & set(await _roll_keys(client, await _sub(client, "mercy", 3), "attack"))


async def test_push_and_topple_show_their_save_with_the_focus_dc_and_cost_nothing(client):
    cid = await _sub(client, "open_hand", 3, wisdom=16, dexterity=16)  # competenza +2, Saggezza +3
    hit = await _flurry_hit(client, cid)
    body = (await _damage(client, cid, hit, PUSH)).json()
    assert "CD 13" in body["option_result"]["effects"][0]["it"] and "4,5 m" in body["option_result"]["effects"][0]["it"]
    effect = await _target(client, cid, PUSH)
    assert (effect["save_ability"], effect["save_dc"]) == ("strength", 13) and not effect["condition"]
    second = await _hit(client, cid, options=[STRIKE])
    topple = (await _damage(client, cid, second, TOPPLE)).json()
    assert "CD 13" in topple["option_result"]["effects"][0]["it"]
    effect = await _target(client, cid, TOPPLE)
    assert (effect["condition"], effect["save_ability"], effect["save_dc"]) == ("prone", "dexterity", 13)
    assert await _ki(client, cid) == 2


async def test_addle_has_no_save_and_lasts_until_the_start_of_the_targets_next_turn(client):
    cid = await _sub(client, "open_hand", 3, wisdom=16, dexterity=16)
    hit = await _flurry_hit(client, cid)
    body = (await _damage(client, cid, hit, ADDLE)).json()
    text = body["option_result"]["effects"][0]
    assert "attacchi di opportunità" in text["it"] and "opportunity" in text["en"] and "TS" not in text["it"]


async def test_the_technique_allows_one_choice_for_each_hit(client):
    cid = await _sub(client, "open_hand", 3, dexterity=16)
    hit = await _flurry_hit(client, cid)
    r = await _damage(client, cid, hit, PUSH, TOPPLE)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "option_unavailable"


async def test_wholeness_of_body_is_a_bonus_action_with_wisdom_modifier_uses_and_heals_die_plus_wisdom(client, monkeypatch):
    cid = await _sub(client, "open_hand", 6, wisdom=16)
    await _hurt(client, cid, 10)
    _fixed(monkeypatch, 5)
    r = await _use(client, cid, WHOLENESS)
    assert r.status_code == 200, r.text
    assert r.json()["healed"] == 5 + 3 and (await _full(client, cid))["current_hit_points"] == 18
    row = await _ability(client, cid, WHOLENESS)
    assert (row["uses"], row["max_uses"], row["restoration_type"], row["action_type"]) == (2, 3, "long_rest", "bonus_action")
    assert (await _turn(client, cid))["bonus_used"] is True and not (await _turn(client, cid))["action_used"]


async def test_wholeness_of_body_heals_at_least_one_and_has_at_least_one_use(client, monkeypatch):
    cid = await _sub(client, "open_hand", 6, wisdom=1)  # modificatore -5
    await _hurt(client, cid, 10)
    _fixed(monkeypatch, 2)
    assert (await _use(client, cid, WHOLENESS)).json()["healed"] == 1
    row = await _ability(client, cid, WHOLENESS)
    assert row["max_uses"] == 1 and row["uses"] == 0


async def test_wholeness_of_body_is_refused_without_the_bonus_action_and_comes_back_with_a_long_rest_only(client):
    cid = await _sub(client, "open_hand", 6, wisdom=10)
    await client.post(f"/characters/{cid}/turn/use", json={"slot": "bonus"})
    r = await _use(client, cid, WHOLENESS)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "turn_slot_used"
    await _new_turn(client, cid)
    assert (await _use(client, cid, WHOLENESS)).status_code == 200
    await _new_turn(client, cid)
    assert (await _use(client, cid, WHOLENESS)).json()["detail"]["code"] == "no_uses"
    await _rest(client, cid, "short")
    assert (await _ability(client, cid, WHOLENESS))["uses"] == 0
    await _rest(client, cid, "long")
    assert (await _ability(client, cid, WHOLENESS))["uses"] == 1


async def test_fleet_step_is_offered_only_after_another_bonus_action_and_costs_no_bonus_action(client):
    cid = await _sub(client, "open_hand", 11)
    assert (await _use(client, cid, FLEET)).json()["detail"]["code"] == "feature_unavailable"
    await _strike(client, cid)
    await _use(client, cid, FLURRY)  # un'azione bonus diversa da Passo del Vento
    r = await _use(client, cid, FLEET)
    assert r.status_code == 200, r.text
    assert (await _states(client, cid))["step_of_the_wind"]["data"]["mode"] == "dash"
    assert await _ki(client, cid) == 10  # solo la Raffica
    assert (await _use(client, cid, FLEET)).status_code == 409  # non si concatena a se stesso


async def test_fleet_step_with_a_point_gives_the_disengage_dash_and_double_jump_variant(client):
    cid = await _sub(client, "open_hand", 11)
    await client.post(f"/characters/{cid}/turn/use", json={"slot": "bonus"})
    assert (await _use(client, cid, FLEET_FOCUS)).status_code == 200
    state = (await _states(client, cid))["step_of_the_wind"]
    assert state["data"]["mode"] == "disengage_dash" and state["data"]["jump_doubled"] is True
    assert await _ki(client, cid) == 10


async def test_fleet_step_is_not_offered_after_step_of_the_wind_itself_or_without_a_point(client):
    cid = await _sub(client, "open_hand", 11)
    await _use(client, cid, STEP)
    assert (await _use(client, cid, FLEET)).json()["detail"]["code"] == "feature_unavailable"
    other = await _sub(client, "open_hand", 11)
    await client.post(f"/characters/{other}/turn/use", json={"slot": "bonus"})
    await _set_ki(client, other, 0)
    assert (await _use(client, other, FLEET_FOCUS)).json()["detail"]["code"] == "no_uses"
    assert (await _use(client, other, FLEET)).status_code == 200


async def test_quivering_palm_spends_four_points_and_keeps_the_vibrations_for_as_many_days_as_the_level(client):
    low = await _sub(client, "open_hand", 16)
    assert PALM_START not in await _roll_keys(client, low, "attack")
    cid = await _sub(client, "open_hand", 17, dexterity=16)
    assert PALM_START in await _roll_keys(client, cid, "attack")
    sword = await _shortsword(client, cid)
    assert PALM_START not in await _roll_keys(client, cid, "attack", item_id=sword)
    await client.patch(f"/characters/{cid}/items/{sword}", json={"is_equipped": False})
    assert (await _damage(client, cid, await _hit(client, cid), PALM_START)).status_code == 200
    assert await _ki(client, cid) == 13
    state = (await _states(client, cid))["quivering_palm"]
    assert state["rounds_left"] == 17 * 14400 and "manual" in state["ends_on"]
    assert PALM_START not in await _roll_keys(client, cid, "attack")  # una sola creatura alla volta
    await _set_ki(client, cid, 3)
    await client.delete(f"/characters/{cid}/active-states/quivering_palm")
    assert PALM_START not in await _roll_keys(client, cid, "attack")


async def test_ending_the_vibrations_with_the_action_rolls_ten_d12_with_a_constitution_save(client):
    cid = await _sub(client, "open_hand", 17, dexterity=16, wisdom=16)  # competenza +6, Saggezza +3
    assert (await _use(client, cid, PALM)).json()["detail"]["code"] == "feature_unavailable"
    await _damage(client, cid, await _hit(client, cid), PALM_START)
    await _new_turn(client, cid)
    r = await _use(client, cid, PALM)
    assert r.status_code == 200, r.text
    assert len(r.json()["rolls"]) == 10
    effect = await _target(client, cid, PALM)
    assert (effect["save_ability"], effect["save_dc"], effect["damage_dice"], effect["on_failure_only"]) == (
        "constitution", 8 + 6 + 3, "10d12", False)
    assert "quivering_palm" not in await _states(client, cid) and (await _turn(client, cid))["action_used"] is True
    assert await _ki(client, cid) == 13  # la fine non costa punti


async def test_the_vibrations_can_also_end_by_giving_up_one_attack_of_the_attack_action(client):
    cid = await _sub(client, "open_hand", 17, dexterity=16)
    await _damage(client, cid, await _hit(client, cid), PALM_START)
    await _new_turn(client, cid)
    await _strike(client, cid)
    await _strike(client, cid, confirm_extra_attack=True)  # i due attacchi dell'azione sono finiti
    r = await _use(client, cid, PALM_ATTACK)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_attack_left" and "quivering_palm" in await _states(client, cid)
    await _new_turn(client, cid)
    await _strike(client, cid)
    r = await _use(client, cid, PALM_ATTACK)
    assert r.status_code == 200, r.text
    assert (await _turn(client, cid))["action_attacks"] == 2 and "quivering_palm" not in await _states(client, cid)
    assert (await _target(client, cid, PALM_ATTACK))["damage_dice"] == "10d12"


async def test_the_vibrations_can_end_harmlessly_without_an_action(client):
    cid = await _sub(client, "open_hand", 17, dexterity=16)
    await _damage(client, cid, await _hit(client, cid), PALM_START)
    assert (await client.delete(f"/characters/{cid}/active-states/quivering_palm")).status_code == 200
    assert "quivering_palm" not in await _states(client, cid) and not (await _turn(client, cid))["action_used"]


# ---------------------------------------------------------------------------
# Giro di correzione 1 (I2, I3, I5, I6, M12)
# ---------------------------------------------------------------------------

async def _deferring(client, cid) -> set[str]:
    r = await client.get(f"/characters/{cid}/roll-options", params={"roll": "attack"})
    return {o["key"] for o in r.json() if o.get("defers_damage")}


async def test_the_flurry_strike_and_the_elemental_strikes_make_the_damage_wait_for_the_after_hit_choice(client):
    """Il client rinvia il danno solo se una scelta prima del tiro lo dichiara: senza, Tecnica e spinta andrebbero perse."""
    cid = await _sub(client, "open_hand", 5, wisdom=16, dexterity=16)
    await _strike(client, cid)
    assert (await _use(client, cid, FLURRY)).status_code == 200
    assert STRIKE in await _deferring(client, cid)
    el = await _sub(client, "elements", 3, wisdom=16)
    await _use(client, el, ATTUNE)
    assert {_elemental(k) for k in ("acid", "cold", "fire", "lightning", "thunder")} <= await _deferring(client, el)


async def test_the_destructive_stride_rolls_a_martial_die_of_a_chosen_type_once_per_creature_and_costs_nothing(client):
    cid = await _sub(client, "elements", 17, dexterity=16)
    key = "monk.destructive_stride"
    assert (await _use(client, cid, key, params={"element": "fire"})).status_code == 409  # senza Sintonia e Passo del Vento
    await _use(client, cid, ATTUNE)
    await _use(client, cid, STEP)
    ki = await _ki(client, cid)
    r = await _use(client, cid, key, params={"element": "fire"})
    assert r.status_code == 200, r.text
    assert len(r.json()["rolls"]) == 1 and await _ki(client, cid) == ki
    text = r.json()["message"]
    assert "una volta per turno" in text["it"] and "fuoco" in text["it"].lower() and "once per turn" in text["en"]


async def test_hand_of_harm_and_the_epitome_do_not_double_their_die_on_a_critical_hit(client):
    cid = await _sub(client, "mercy", 3, wisdom=16, dexterity=16)
    body = (await _damage(client, cid, await _hit(client, cid, die=20), HARM)).json()
    assert len(body["option_result"]["extra_rolls"]) == 1
    cid = await _sub(client, "elements", 17, dexterity=16)
    await _use(client, cid, ATTUNE)
    body = (await _damage(client, cid, await _hit(client, cid, die=20), "monk.elemental_epitome_strike")).json()
    assert len(body["option_result"]["extra_rolls"]) == 1


async def test_hand_of_harm_total_adds_the_die_and_wisdom_to_the_strike(client, monkeypatch):
    cid = await _sub(client, "mercy", 3, wisdom=16, dexterity=16)  # Saggezza +3, Destrezza +3, d6
    _fixed(monkeypatch, 4)
    hit = await _hit(client, cid)
    body = (await _damage(client, cid, hit, HARM)).json()
    assert body["option_result"]["extra_rolls"] == [4] and body["damage_total"] == (4 + 3) + (4 + 3)


async def test_addle_is_an_effect_on_the_target_until_the_start_of_its_next_turn(client):
    from core.data.labels import CUSTOM_CONDITION_LABELS
    cid = await _sub(client, "open_hand", 3, wisdom=16, dexterity=16)
    await _damage(client, cid, await _flurry_hit(client, cid), ADDLE)
    effect = await _target(client, cid, ADDLE)
    assert effect["condition"] == "custom:no_opportunity_attacks"
    assert effect["ends_at"] == {"anchor": "owner", "edge": "start", "count": 1}
    assert "no_opportunity_attacks" in CUSTOM_CONDITION_LABELS
