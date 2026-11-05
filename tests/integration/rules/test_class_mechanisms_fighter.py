"""Meccanismi comuni aggiunti per il Guerriero 2014 (Task 23), provati con privilegi di prova e non con il Guerriero:
uso una volta per turno, rinuncia a un attacco, esiti e valori da dare, scelte di più sottoclassi nello stesso gruppo,
ritiro dei dadi bassi del danno, danno della seconda arma, cura a inizio turno e lancio con l'azione."""
from __future__ import annotations

from dataclasses import replace

import pytest
from sqlalchemy import select

from core.db.models import Character
from core.rules.types import ChoiceSpec, FeatureSpec, Modifier, OnUse, Uses
from tests.integration.rules.test_class_mechanisms import KEY, _fighter, _full, _spec, _use

TWICE = Uses(table={1: 2})


async def _turn(client, cid) -> dict:
    return (await client.get(f"/characters/{cid}/turn-state")).json()["turn"]


async def _uses(client, cid) -> int:
    return next(a for a in (await _full(client, cid))["abilities"] if a["feature_key"] == KEY)["uses"]


# ---------------------------------------------------------------------------
# OnUse: una volta per turno, rinuncia a un attacco, esiti, valore da dare
# ---------------------------------------------------------------------------

async def test_once_per_turn_refuses_the_second_use_before_spending(client, rules_catalog):
    rules_catalog(_spec(uses=TWICE, restoration="long_rest", on_use=OnUse(once_per_turn=True)))
    cid = await _fighter(client)
    assert (await _use(client, cid)).status_code == 200
    r = await _use(client, cid)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "once_per_turn"
    assert await _uses(client, cid) == 1  # il rifiuto non costa nulla
    await client.post(f"/characters/{cid}/turn/new")
    assert (await _use(client, cid)).status_code == 200 and await _uses(client, cid) == 0


async def test_once_per_turn_is_not_marked_when_the_use_is_refused(client, rules_catalog):
    rules_catalog(_spec(uses=TWICE, restoration="long_rest", on_use=OnUse(once_per_turn=True, slot="bonus")))
    cid = await _fighter(client)
    await client.post(f"/characters/{cid}/turn/use", json={"slot": "bonus"})
    assert (await _use(client, cid)).json()["detail"]["code"] == "turn_slot_used"
    assert KEY not in (await _turn(client, cid))["once_per_turn"]


async def test_forgoing_an_attack_uses_one_attack_of_the_action(client, rules_catalog):
    rules_catalog(_spec(uses=TWICE, restoration="long_rest", on_use=OnUse(forgoes_attack=True)))
    cid = await _fighter(client, 1)  # un solo attacco per azione
    assert (await _use(client, cid)).status_code == 200
    assert (await _turn(client, cid))["action_attacks"] == 1
    r = await _use(client, cid)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_attack_left"
    assert await _uses(client, cid) == 1  # il secondo non ha speso nulla
    assert (await _turn(client, cid))["attacks_made"] == 0  # non è un attacco fatto: l'Ira non lo conta


async def test_notes_come_back_as_keys_and_a_toggle_decides_them(client, rules_catalog):
    rules_catalog(_spec(on_use=OnUse(notes=lambda ctx, params: ["charge"] if params.get("x") else [])))
    cid = await _fighter(client)
    assert (await _use(client, cid, params={"x": True})).json()["notes"] == ["charge"]
    assert (await _use(client, cid)).json()["notes"] == []


async def test_gives_turns_the_roll_into_a_value_for_someone_else(client, rules_catalog):
    rules_catalog(_spec(on_use=OnUse(rolls="1d2", gives=lambda ctx, rolled: rolled + 3)))
    cid = await _fighter(client)
    body = (await _use(client, cid)).json()
    assert len(body["rolls"]) == 1 and body["given"] == body["rolls"][0] + 3 and body["healed"] == 0
    assert (await _full(client, cid))["temp_hp"] == 0  # nessun dato scritto sulla scheda


# ---------------------------------------------------------------------------
# Scelte: più ChoiceSpec dello stesso gruppo valgono il massimo (una per sottoclasse)
# ---------------------------------------------------------------------------

def _style(levels, subclass=None, key="stile") -> FeatureSpec:
    return replace(_spec(subclass=subclass), key=f"fighter.{key}", choices=(
        ChoiceSpec(group="stili", levels=levels, options=lambda ctx: ["a", "b", "c"]),))


async def _pending(client, cid, group="stili") -> list[dict]:
    return [c for c in (await _full(client, cid))["pending_choices"] if c.get("group") == group]


async def test_two_specs_of_one_group_ask_the_maximum_not_the_sum(client, rules_catalog):
    rules_catalog(_style({1: 1}), _style({3: 2}, key="extra"))
    cid = await _fighter(client, 5)
    assert [c["count"] for c in await _pending(client, cid)] == [2]


async def test_a_spec_of_another_subclass_does_not_apply_to_everyone(client, rules_catalog):
    rules_catalog(_style({1: 1}), _style({3: 2}, subclass="champion", key="extra"))
    cid = await _fighter(client, 5)
    assert [c["count"] for c in await _pending(client, cid)] == [1]


async def test_the_second_pick_asks_only_what_is_missing(client, rules_catalog):
    rules_catalog(_style({1: 1}), _style({3: 2}, key="extra"))
    cid = await _fighter(client, 2)
    choice = (await _pending(client, cid))[0]
    r = await client.post(f"/characters/{cid}/choices/{choice['id']}/resolve", json={"kind": "class_option", "options": ["a"]})
    assert r.status_code == 200, r.text
    assert await _pending(client, cid) == []
    klass = (await _full(client, cid))["classes"][0]
    await client.patch(f"/characters/{cid}/classes/{klass['id']}", json={"level": 3})
    again = await _pending(client, cid)
    assert [c["count"] for c in again] == [1] and {o["key"] for o in again[0]["options"]} == {"b", "c"}


# ---------------------------------------------------------------------------
# Dadi bassi del danno ritirati e danno della seconda arma
# ---------------------------------------------------------------------------

async def _sword(client, cid, equip=None, **meta) -> int:
    meta = {"damage_dice": "2d6", "weapon_type": "melee", "properties": [], **meta}
    r = await client.post(f"/characters/{cid}/items", json={"name": "Spada", "item_type": "weapon", "item_metadata": meta})
    assert r.status_code == 201, r.text
    wid = max(i["id"] for i in r.json()["items"])
    if equip:
        await client.patch(f"/characters/{cid}/items/{wid}", json={"is_equipped": True, "equipment_slot": equip})
    return wid


async def test_damage_reroll_reroll_low_dice_once_and_says_so(client, rules_catalog, monkeypatch):
    rules_catalog(_spec(modifiers=(Modifier("damage_reroll", 2, when=lambda c: c.roll == "damage"),)))
    cid = await _fighter(client, 1, strength=10)
    wid = await _sword(client, cid)
    values = iter([1, 5, 6, 3])  # due dadi: 1 e 5; il 1 si ritira e dà 6
    monkeypatch.setattr("api.routers.items.random.randint", lambda a, b: next(values))
    body = (await client.post(f"/characters/{cid}/items/{wid}/attack", json={"die": 10})).json()
    assert body["damage_rolls"] == [6, 5] and body["rerolled"] == [[1, 6]]


async def test_damage_reroll_does_not_loop_on_a_second_low_result(client, rules_catalog, monkeypatch):
    rules_catalog(_spec(modifiers=(Modifier("damage_reroll", 2, when=lambda c: c.roll == "damage"),)))
    cid = await _fighter(client, 1, strength=10)
    wid = await _sword(client, cid, damage_dice="1d6")
    values = iter([2, 1])  # il nuovo risultato vale anche se è ancora basso
    monkeypatch.setattr("api.routers.items.random.randint", lambda a, b: next(values))
    body = (await client.post(f"/characters/{cid}/items/{wid}/attack", json={"die": 10})).json()
    assert body["damage_rolls"] == [1] and body["rerolled"] == [[2, 1]]


async def test_damage_modifier_sees_the_grip_and_the_other_hand(client, rules_catalog):
    seen: list[tuple] = []

    def probe(ctx) -> int:
        if ctx.roll == "damage":
            seen.append((ctx.grip, ctx.offhand))
        return 0

    rules_catalog(_spec(modifiers=(Modifier("damage", probe),)))
    cid = await _fighter(client, 1)
    wid = await _sword(client, cid, properties=["versatile"], versatile_dice="1d10")
    await client.post(f"/characters/{cid}/items/{wid}/attack", json={"die": 10, "grip": "two"})
    assert ("two", False) in seen


async def test_the_other_hand_adds_its_modifier_when_a_privilege_says_so(client, rules_catalog):
    rules_catalog(_spec(modifiers=(Modifier("damage", lambda c: 3, when=lambda c: c.roll == "damage" and c.offhand),)))
    cid = await _fighter(client, 1, strength=10)
    main = await _sword(client, cid, equip="main_hand", properties=["light"], damage_dice="1d1")
    off = await _sword(client, cid, equip="off_hand", properties=["light"], damage_dice="1d1")
    plain = (await client.post(f"/characters/{cid}/items/{main}/attack", json={"die": 10})).json()["damage_bonus"]
    other = (await client.post(f"/characters/{cid}/items/{off}/attack", json={"die": 10, "attack_mode": "offhand"})).json()
    assert other["damage_bonus"] == plain + 3


# ---------------------------------------------------------------------------
# Cura a inizio turno
# ---------------------------------------------------------------------------

async def _hurt(factory, cid, hp) -> None:
    async with factory() as s:
        char = await s.get(Character, cid)
        char.current_hit_points = hp
        await s.commit()


async def test_turn_start_heal_runs_on_new_turn_outside_an_encounter(client, rules_catalog, test_session_factory):
    rules_catalog(_spec(turn_start_heal=lambda ctx: 4 if 0 < ctx.char.current_hit_points * 2 <= ctx.char.hit_points else 0))
    cid = await _fighter(client, 5)
    maximum = (await _full(client, cid))["hit_points"]
    await _hurt(test_session_factory, cid, maximum // 2)
    assert (await client.post(f"/characters/{cid}/turn/new")).status_code == 200
    assert (await _full(client, cid))["current_hit_points"] == maximum // 2 + 4
    await _hurt(test_session_factory, cid, 0)
    await client.post(f"/characters/{cid}/turn/new")
    assert (await _full(client, cid))["current_hit_points"] == 0  # a 0 PF la condizione del privilegio non c'è


async def test_turn_start_heal_never_passes_the_maximum(client, rules_catalog, test_session_factory):
    rules_catalog(_spec(turn_start_heal=lambda ctx: 50))
    cid = await _fighter(client, 5)
    maximum = (await _full(client, cid))["hit_points"]
    await _hurt(test_session_factory, cid, maximum - 2)
    await client.post(f"/characters/{cid}/turn/new")
    assert (await _full(client, cid))["current_hit_points"] == maximum


# ---------------------------------------------------------------------------
# Lancio con l'azione
# ---------------------------------------------------------------------------

async def test_the_cast_remembers_the_level_of_the_spell_cast_with_the_action(client):
    cid = await _fighter(client, 5)
    cantrip = (await client.post(f"/characters/{cid}/spells", json={"name": "Raggio", "level": 0, "casting_time": "1 azione"})).json()
    await client.post(f"/characters/{cid}/spells/{cantrip['id']}/use", json={})
    assert (await _turn(client, cid)).get("action_spell_level") == 0
    await client.post(f"/characters/{cid}/turn/new")
    assert (await _turn(client, cid))["action_spell_level"] is None
