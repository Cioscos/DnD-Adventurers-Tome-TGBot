"""Meccanismi comuni aggiunti per il Barbaro 2024 (Task 31), provati con privilegi di prova e non con il Barbaro."""
from __future__ import annotations

import pytest

from core.rules.types import ENDS_ON, FeatureSpec, Modifier, OnUse, RollOptionSpec, StateSpec, Uses

KEY = "fighter.prova"


def _spec(key=KEY, level=1, **kw) -> FeatureSpec:
    return FeatureSpec(key=key, class_key="fighter", edition="2014", level=level, source_title="Prova",
                       name={"it": "Prova", "en": "Test"}, summary={"it": "x", "en": "x"}, action_type=None, **kw)


async def _fighter(client, level=5, **scores) -> int:
    cid = (await client.post("/characters", json={"name": "Prova"})).json()["id"]
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "fighter", "level": level, "hit_die": 10})
    assert r.status_code == 201, r.text
    for ability, value in scores.items():
        await client.patch(f"/characters/{cid}/ability_scores/{ability}", json={"value": value})
    return cid


async def _full(client, cid) -> dict:
    return (await client.get(f"/characters/{cid}")).json()


async def _use(client, cid, key=KEY, **body):
    return await client.post(f"/characters/{cid}/features/{key}/use", json=body)


def _option(key, **kw) -> RollOptionSpec:
    return RollOptionSpec(key=key, phase="before", rolls=("skill",), label={"it": key, "en": key}, **kw)


# --- group_max: più opzioni dello stesso gruppo (Colpo Brutale Migliorato) ------------------------------------------

async def test_group_max_allows_that_many_options_of_a_group_and_no_more(client, rules_catalog):
    rules_catalog(_spec(roll_options=tuple(_option(f"p.{n}", group="g", group_max=lambda _c: 2) for n in "abc")))
    cid = await _fighter(client)
    ok = await client.post(f"/characters/{cid}/skills/athletics/roll", json={"die": 10, "options": ["p.a", "p.b"]})
    assert ok.status_code == 200, ok.text
    three = await client.post(f"/characters/{cid}/skills/athletics/roll", json={"die": 10, "options": ["p.a", "p.b", "p.c"]})
    assert three.status_code == 409 and three.json()["detail"]["code"] == "option_unavailable"


async def test_a_group_without_group_max_still_allows_one_option(client, rules_catalog):
    rules_catalog(_spec(roll_options=tuple(_option(f"p.{n}", group="g") for n in "ab")))
    cid = await _fighter(client)
    two = await client.post(f"/characters/{cid}/skills/athletics/roll", json={"die": 10, "options": ["p.a", "p.b"]})
    assert two.status_code == 409


async def test_the_roll_option_read_exposes_group_max(client, rules_catalog):
    rules_catalog(_spec(roll_options=(_option("p.a", group="g", group_max=lambda _c: 2),)))
    cid = await _fighter(client)
    read = (await client.get(f"/characters/{cid}/roll-options", params={"roll": "skill", "skill": "athletics"})).json()
    assert [(o["key"], o["group_max"]) for o in read if o["key"] == "p.a"] == [("p.a", 2)]


# --- ability_override: la prova fatta con un'altra caratteristica (Conoscenza Primordiale) ----------------------------

async def test_ability_override_rolls_the_skill_with_the_other_ability(client, rules_catalog):
    rules_catalog(_spec(roll_options=(_option("p.str", ability_override="strength"),)))
    cid = await _fighter(client, level=1, strength=18, dexterity=8)
    plain = (await client.post(f"/characters/{cid}/skills/acrobatics/roll", json={"die": 10})).json()
    forced = (await client.post(f"/characters/{cid}/skills/acrobatics/roll", json={"die": 10, "options": ["p.str"]})).json()
    assert forced["bonus"] - plain["bonus"] == 4 - (-1)  # Forza +4 al posto di Destrezza -1


async def test_ability_override_brings_the_modifiers_of_the_new_ability(client, rules_catalog):
    rules_catalog(_spec(modifiers=(Modifier("advantage", 1, when=lambda c: c.roll == "skill" and c.ability == "strength", source="feature:t"),),
                        roll_options=(_option("p.str", ability_override="strength"),)))
    cid = await _fighter(client)
    plain = (await client.post(f"/characters/{cid}/skills/acrobatics/roll", json={"die": 10})).json()
    forced = (await client.post(f"/characters/{cid}/skills/acrobatics/roll", json={"die": 10, "options": ["p.str"]})).json()
    assert plain["mode_applied"] == "normal" and forced["mode_applied"] == "advantage"


# --- OnUse: stato facoltativo, slot e costo dalla scelta -----------------------------------------------------------------

async def test_use_state_may_be_none_and_cost_and_slot_follow_the_params(client, rules_catalog):
    state = lambda c, p: None if p.get("again") else StateSpec("prova", rounds=5)
    rules_catalog(_spec(uses=Uses(table={1: 2}), restoration="long_rest", on_use=OnUse(
        slot="bonus", state=state, cost_by=lambda c, p: 0 if p.get("again") else 1,
        slot_by=lambda c, p: None if p.get("free") else "bonus")))
    cid = await _fighter(client)
    first = await _use(client, cid)
    assert first.json()["state"]["rounds_left"] == 5
    again = await _use(client, cid, params={"again": True, "free": True})  # senza costo né slot: il bonus è già speso
    assert again.status_code == 200 and again.json()["state"] is None
    ability = next(a for a in (await _full(client, cid))["abilities"] if a["feature_key"] == KEY)
    assert ability["uses"] == 1
    assert (await _use(client, cid, params={"again": True})).status_code == 409  # senza «free» il bonus è già speso


# --- alt_spends: ripristinare un uso spendendo un uso di Ira (Presenza Intimidatoria, Presenza Zelante) -----------------

async def test_alt_spends_pays_from_the_other_pool_when_the_toggle_is_on(client, rules_catalog):
    pool = _spec("fighter.pool", uses=Uses(table={1: 1}), restoration="long_rest")
    rules_catalog(pool, _spec(uses=Uses(table={1: 1}), restoration="long_rest",
                              on_use=OnUse(alt_spends="fighter.pool", alt_param="restore")))
    cid = await _fighter(client)
    assert (await _use(client, cid)).status_code == 200  # il proprio uso
    assert (await _use(client, cid)).status_code == 409  # finito
    assert (await _use(client, cid, params={"restore": True})).status_code == 200  # dal pozzo
    abilities = {a["feature_key"]: a["uses"] for a in (await _full(client, cid))["abilities"]}
    assert abilities == {KEY: 0, "fighter.pool": 0}
    assert (await _use(client, cid, params={"restore": True})).status_code == 409  # nemmeno il pozzo


# --- ENDS_ON: turn_end_unextended e heavy_armor ---------------------------------------------------------------------------

def test_new_end_tokens_are_part_of_the_closed_set():
    assert {"turn_end_unextended", "heavy_armor"} <= ENDS_ON


# --- velocità di scalare e nuotare date da un privilegio (Pantera, Salmone) --------------------------------------------------

async def test_climb_and_swim_speed_equal_to_walking_speed(client, rules_catalog):
    rules_catalog(_spec(modifiers=(Modifier("climb_speed", 1), Modifier("swim_speed", 1, when=lambda c: False))))
    cid = await _fighter(client)
    computed = (await _full(client, cid))["computed"]
    assert computed["climb_speed"] == computed["speed"] and computed["swim_speed"] is None
