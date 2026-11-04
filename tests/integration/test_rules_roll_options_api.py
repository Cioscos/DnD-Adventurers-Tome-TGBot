"""Conferma al tiro attraverso l'API: ogni flusso accetta `options`, il server riconvalida sempre."""
from __future__ import annotations

import random

import pytest

from api.services.condition_effects import SaveSpec, upsert_effect
from core.db.models import Character, PendingSave
from core.rules.types import Cost, FeatureSpec, RollOptionSpec, Uses
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, seed_session

_LABEL = {"it": "Applica?", "en": "Apply?"}


def _is_finesse(ctx) -> bool:
    return ctx.item is not None and "finesse" in (ctx.item.item_metadata or "")


SNEAK = RollOptionSpec(key="sneak", phase="after_hit", rolls=("attack",), label=_LABEL, available=_is_finesse,
                       extra_dice=lambda _c, _i: "2d6", once_per_turn=True)
SMITE = RollOptionSpec(key="smite", phase="after_hit", rolls=("attack",), label=_LABEL, requires_input="slot",
                       cost=Cost(spell_slot_min=1), extra_dice=lambda _c, i: f"{i['slot_level'] + 1}d8")
BLESS = RollOptionSpec(key="bless", phase="before", rolls=("attack", "skill", "save", "initiative"), label=_LABEL,
                       bonus=lambda _c, _i: 2)
GUIDE = RollOptionSpec(key="guide", phase="before", rolls=("skill", "save", "initiative"), label=_LABEL,
                       extra_dice=lambda _c, _i: "1d4")
FOCUS = RollOptionSpec(key="focus", phase="before", rolls=("attack",), label=_LABEL, mode="advantage",
                       cost=Cost(feature_key="fighter.prova"))
ASSASSINATE = RollOptionSpec(key="assassinate", phase="before", rolls=("attack",), label=_LABEL, force_crit=True)
DEATH = RollOptionSpec(key="death", phase="after_hit", rolls=("attack",), label=_LABEL, multiplier=2)
EMPOWER = RollOptionSpec(key="empower", phase="before", rolls=("spell_damage",), label=_LABEL,
                         extra_dice=lambda _c, _i: "2d4", bonus=lambda _c, _i: 1)
UNCANNY = RollOptionSpec(key="uncanny", phase="damage_in", rolls=("damage_taken",), label=_LABEL, slot="reaction",
                         multiplier=0.5)
EVASION = RollOptionSpec(key="evasion", phase="damage_in", rolls=("damage_taken",), label=_LABEL, multiplier=0)
DEFLECT = RollOptionSpec(key="deflect", phase="damage_in", rolls=("damage_taken",), label=_LABEL,
                         extra_dice=lambda _c, _i: "1d4", bonus=lambda _c, _i: 100)


def _feature(*options, uses=None) -> FeatureSpec:
    return FeatureSpec(
        key="fighter.prova", class_key="fighter", edition="2014", level=1, source_title="Prova",
        name={"it": "Prova", "en": "Test"}, summary={"it": "x", "en": "x"}, action_type=None,
        uses=uses, restoration="long_rest" if uses else "none", roll_options=options,
    )


async def _char(client, edition="2014") -> int:
    r = await client.post("/characters", json={"name": "Prova"})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "fighter", "level": 5, "hit_die": 10})
    assert r.status_code == 201, r.text
    if edition != "2014":
        r = await client.patch(f"/characters/{cid}", json={"rules_edition": edition})
        assert r.status_code == 200, r.text
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": 50})
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 50})
    assert r.status_code == 200, r.text
    return cid


async def _weapon(client, cid, properties=("finesse",)) -> int:
    r = await client.post(f"/characters/{cid}/items", json={
        "name": "Stocco", "item_type": "weapon",
        "item_metadata": {"damage_dice": "1d8", "weapon_type": "melee", "properties": list(properties)}})
    assert r.status_code == 201, r.text
    return next(i["id"] for i in r.json()["items"] if i["name"] == "Stocco")


async def _cond(client, cid, **conditions) -> None:
    r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": conditions})
    assert r.status_code == 200, r.text


async def _slot(client, cid, level, total=2) -> None:
    r = await client.post(f"/characters/{cid}/spell_slots", json={"level": level, "total": total})
    assert r.status_code == 201, r.text


async def _uses(client, cid) -> int:
    full = (await client.get(f"/characters/{cid}")).json()
    return next(a["uses"] for a in full["abilities"] if a["feature_key"] == "fighter.prova")


def _code(r) -> str | None:
    return r.json()["detail"]["code"] if r.status_code == 409 else None


async def _deferred(client, cid, item, die=10, **extra) -> dict:
    r = await client.post(f"/characters/{cid}/items/{item}/attack", json={"die": die, "defer_damage": True, **extra})
    assert r.status_code == 200, r.text
    return r.json()


# --- I sei casi del piano -------------------------------------------------------------------------------------------

async def test_option_adds_dice_and_doubles_on_crit(client, rules_catalog):
    rules_catalog(_feature(SNEAK))
    cid = await _char(client)
    item = await _weapon(client, cid)
    hit = await _deferred(client, cid, item, die=10)
    r = await client.post(f"/characters/{cid}/attack/{hit['attack_id']}/damage", json={"options": ["sneak"]})
    assert r.status_code == 200, r.text
    normal = r.json()
    extra = normal["option_result"]["extra_rolls"]
    assert len(extra) == 2 and normal["option_result"]["keys"] == ["sneak"]
    assert normal["damage_total"] == hit["damage_total"] + sum(extra)
    assert normal["notes"] == ["feature:fighter.prova"]

    await client.post(f"/characters/{cid}/turn/new")
    crit = await _deferred(client, cid, item, die=20)
    assert crit["is_critical"] is True
    r = await client.post(f"/characters/{cid}/attack/{crit['attack_id']}/damage", json={"options": ["sneak"]})
    assert len(r.json()["option_result"]["extra_rolls"]) == 4


async def test_once_per_turn_blocked_second_time(client, rules_catalog):
    rules_catalog(_feature(SNEAK))
    cid = await _char(client)
    item = await _weapon(client, cid)
    first = await _deferred(client, cid, item)
    assert (await client.post(f"/characters/{cid}/attack/{first['attack_id']}/damage",
                              json={"options": ["sneak"]})).status_code == 200
    listed = (await client.get(f"/characters/{cid}/roll-options", params={"roll": "attack", "item_id": item})).json()
    assert listed == []
    second = await _deferred(client, cid, item)
    r = await client.post(f"/characters/{cid}/attack/{second['attack_id']}/damage", json={"options": ["sneak"]})
    assert r.status_code == 409 and _code(r) == "option_unavailable" and r.json()["detail"]["key"] == "sneak"
    await client.post(f"/characters/{cid}/turn/new")
    listed = (await client.get(f"/characters/{cid}/roll-options", params={"roll": "attack", "item_id": item})).json()
    assert [o["key"] for o in listed] == ["sneak"]


async def test_option_cost_is_spent_only_when_used(client, rules_catalog):
    rules_catalog(_feature(FOCUS, uses=Uses(table={1: 1})))
    cid = await _char(client)
    item = await _weapon(client, cid)
    await client.post(f"/characters/{cid}/items/{item}/attack", json={"die": 10})
    assert await _uses(client, cid) == 1

    r = await client.post(f"/characters/{cid}/items/{item}/attack", json={"die": 10, "options": ["focus"]})
    assert r.status_code == 200, r.text
    assert r.json()["mode_applied"] == "advantage" and len(r.json()["dice"]) == 2
    assert await _uses(client, cid) == 0

    async_ok = await client.post(f"/characters/{cid}/items/{item}/attack", json={"die": 10, "options": ["focus"]})
    assert async_ok.status_code == 409 and _code(async_ok) == "option_unavailable"


async def test_failed_option_rolls_back_inspiration_and_ammo(client, rules_catalog, test_session_factory):
    rules_catalog(_feature(FOCUS, uses=Uses(table={1: 1})))
    cid = await _char(client)
    item = await _weapon(client, cid)
    async with test_session_factory() as s:
        (await s.get(Character, cid)).heroic_inspiration = True
        await s.commit()
    r = await client.post(f"/characters/{cid}/items/{item}/attack", json={"die": 10, "options": ["nope"]})
    assert r.status_code == 409
    async with test_session_factory() as s:
        char = await s.get(Character, cid)
        assert char.heroic_inspiration is True and (char.turn_state or {}).get("attacks_made", 0) == 0


async def test_server_rejects_option_not_available(client, rules_catalog):
    rules_catalog(_feature(SNEAK, BLESS))
    cid = await _char(client)
    heavy = await _weapon(client, cid, properties=())
    hit = await _deferred(client, cid, heavy)
    url = f"/characters/{cid}/attack/{hit['attack_id']}/damage"
    # arma non accurata; chiave inventata; opzione di un'altra fase
    for keys in (["sneak"], ["nope"], ["bless"]):
        r = await client.post(url, json={"options": keys})
        assert r.status_code == 409 and _code(r) == "option_unavailable", keys
    # after_hit passata al tiro per colpire
    r = await client.post(f"/characters/{cid}/items/{heavy}/attack", json={"options": ["sneak"]})
    assert r.status_code == 409
    # opzione di un altro tiro
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Fuoco", "level": 0, "damage_dice": "1d10"})
    r = await client.post(f"/characters/{cid}/spells/{r.json()['id']}/roll_damage", json={"options": ["bless"]})
    assert r.status_code == 409


async def test_damage_in_multiplier_halves_down(client, rules_catalog):
    rules_catalog(_feature(UNCANNY))
    cid = await _char(client)
    body = {"op": "damage", "value": 15, "options": ["uncanny"]}
    r = await client.patch(f"/characters/{cid}/hp", json=body)
    assert r.status_code == 200, r.text
    full = r.json()
    assert full["current_hit_points"] == 50 - 7
    assert full["option_result"]["damage_before"] == 15 and full["option_result"]["damage_after"] == 7
    assert (await client.get(f"/characters/{cid}/turn-state")).json()["turn"]["reaction_used"] is True
    # la reazione è già spesa
    r = await client.patch(f"/characters/{cid}/hp", json=body)
    assert r.status_code == 409 and _code(r) == "option_unavailable"
    assert (await client.get(f"/characters/{cid}")).json()["current_hit_points"] == 43


async def test_no_options_keeps_old_response_shape(client, rules_catalog):
    cid = await _char(client)
    item = await _weapon(client, cid)
    attack = (await client.post(f"/characters/{cid}/items/{item}/attack", json={"die": 10})).json()
    assert set(attack) == {
        "weapon_name", "to_hit_die", "dice", "mode", "mode_applied", "notes", "to_hit_bonus", "to_hit_total",
        "is_critical", "is_fumble", "damage_dice", "damage_rolls", "damage_bonus", "damage_total",
        "homebrew_notifications", "ammo", "ammo_missing", "magic_bonus", "proficiency_warning",
    }
    skill = (await client.post(f"/characters/{cid}/skills/stealth/roll", json={"die": 10})).json()
    assert set(skill) == {"die", "dice", "mode", "mode_applied", "notes", "auto_fail", "bonus", "total",
                          "is_critical", "is_fumble", "description"}
    hp = (await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 1})).json()
    assert "option_result" not in hp
    # nessun attacco in sospeso senza defer_damage
    assert "attack_id" not in attack
    r = await client.post(f"/characters/{cid}/attack/abc/damage", json={})
    assert r.status_code == 404


# --- Attacco diviso (R8) --------------------------------------------------------------------------------------------

async def test_deferred_attack_is_single_replaced_and_cleared_by_a_new_turn(client, rules_catalog):
    rules_catalog(_feature(SNEAK))
    cid = await _char(client)
    item = await _weapon(client, cid)
    first = await _deferred(client, cid, item)
    second = await _deferred(client, cid, item)
    assert first["attack_id"] != second["attack_id"]
    assert (await client.post(f"/characters/{cid}/attack/{first['attack_id']}/damage", json={})).status_code == 404
    # senza opzioni il danno è quello base e il sospeso si chiude
    r = await client.post(f"/characters/{cid}/attack/{second['attack_id']}/damage", json={})
    assert r.status_code == 200 and r.json()["damage_total"] == second["damage_total"]
    assert (await client.post(f"/characters/{cid}/attack/{second['attack_id']}/damage", json={})).status_code == 404
    third = await _deferred(client, cid, item)
    await client.post(f"/characters/{cid}/turn/new")
    assert (await client.post(f"/characters/{cid}/attack/{third['attack_id']}/damage", json={})).status_code == 404


async def test_plain_attack_drops_the_pending_one(client, rules_catalog):
    cid = await _char(client)
    item = await _weapon(client, cid)
    pending = await _deferred(client, cid, item)
    await client.post(f"/characters/{cid}/items/{item}/attack", json={"die": 10})
    assert (await client.post(f"/characters/{cid}/attack/{pending['attack_id']}/damage", json={})).status_code == 404


async def test_fumble_leaves_nothing_pending(client, rules_catalog):
    cid = await _char(client)
    item = await _weapon(client, cid)
    assert "attack_id" not in await _deferred(client, cid, item, die=1)


async def test_unarmed_attack_defers_too(client, rules_catalog):
    rules_catalog(_feature(DEATH))
    cid = await _char(client)
    r = await client.post(f"/characters/{cid}/attack/unarmed", json={"die": 10, "defer_damage": True})
    assert r.status_code == 200, r.text
    hit = r.json()
    listed = (await client.get(f"/characters/{cid}/roll-options", params={"roll": "attack"})).json()
    assert [o["key"] for o in listed] == ["death"]
    r = await client.post(f"/characters/{cid}/attack/{hit['attack_id']}/damage", json={"options": ["death"]})
    assert r.status_code == 200, r.text
    assert r.json()["damage_total"] == hit["damage_total"] * 2


async def test_inspiration_reroll_keeps_the_paid_bonus_without_spending_again(client, rules_catalog, test_session_factory):
    bless_paid = RollOptionSpec(key="bless", phase="before", rolls=("attack",), label=_LABEL, bonus=lambda _c, _i: 2,
                                cost=Cost(feature_key="fighter.prova"))
    rules_catalog(_feature(bless_paid, uses=Uses(table={1: 1})))
    cid = await _char(client)
    item = await _weapon(client, cid)
    async with test_session_factory() as s:
        (await s.get(Character, cid)).heroic_inspiration = True
        await s.commit()
    first = (await client.post(f"/characters/{cid}/items/{item}/attack", json={"die": 10, "options": ["bless"]})).json()
    r = await client.post(f"/characters/{cid}/items/{item}/attack", json={"die": 11, "with_inspiration": True})
    assert r.status_code == 200, r.text
    assert r.json()["to_hit_bonus"] == first["to_hit_bonus"] and r.json()["option_result"]["keys"] == ["bless"]
    assert await _uses(client, cid) == 0
    # un attacco nuovo senza opzioni non eredita il bonus
    third = (await client.post(f"/characters/{cid}/items/{item}/attack", json={"die": 10})).json()
    assert third["to_hit_bonus"] == first["to_hit_bonus"] - 2


async def test_assassinate_doubles_the_base_dice_unless_it_is_a_natural_one(client, rules_catalog):
    rules_catalog(_feature(ASSASSINATE))
    cid = await _char(client)
    item = await _weapon(client, cid)
    r = (await client.post(f"/characters/{cid}/items/{item}/attack", json={"die": 5, "options": ["assassinate"]})).json()
    assert r["is_critical"] is True and len(r["damage_rolls"]) == 2
    r = (await client.post(f"/characters/{cid}/items/{item}/attack", json={"die": 1, "options": ["assassinate"]})).json()
    assert r["is_critical"] is False and r["is_fumble"] is True


# --- Slot scelto ---------------------------------------------------------------------------------------------------

async def test_smite_lists_slots_and_spends_the_chosen_one(client, rules_catalog):
    rules_catalog(_feature(SMITE))
    cid = await _char(client)
    item = await _weapon(client, cid)
    assert (await client.get(f"/characters/{cid}/roll-options", params={"roll": "attack", "item_id": item})).json() == []
    await _slot(client, cid, 1)
    await _slot(client, cid, 2)
    listed = (await client.get(f"/characters/{cid}/roll-options", params={"roll": "attack", "item_id": item})).json()
    assert listed[0]["requires_input"] == "slot"
    assert listed[0]["input_options"] == [{"level": 1, "available": 2, "dice": "2d8"},
                                          {"level": 2, "available": 2, "dice": "3d8"}]
    hit = await _deferred(client, cid, item)
    url = f"/characters/{cid}/attack/{hit['attack_id']}/damage"
    r = await client.post(url, json={"options": ["smite"], "option_inputs": {"smite": {"slot_level": 5}}})
    assert r.status_code == 409 and _code(r) == "option_unavailable"
    r = await client.post(url, json={"options": ["smite"], "option_inputs": {"smite": {"slot_level": 2}}})
    assert r.status_code == 200, r.text
    assert len(r.json()["option_result"]["extra_rolls"]) == 3
    slots = (await client.get(f"/characters/{cid}")).json()["spell_slots"]
    assert {s["level"]: s["used"] for s in slots} == {1: 0, 2: 1}


# --- Elenco ---------------------------------------------------------------------------------------------------------

async def test_list_is_localized_and_describes_the_option(client, rules_catalog):
    rules_catalog(_feature(FOCUS, GUIDE, uses=Uses(table={1: 2})))
    cid = await _char(client)
    item = await _weapon(client, cid)
    r = await client.get(f"/characters/{cid}/roll-options", params={"roll": "attack", "item_id": item})
    assert r.status_code == 200, r.text
    assert r.json() == [{
        "key": "focus", "phase": "before", "label": "Applica?", "source": "feature:fighter.prova",
        "dice": None, "bonus": None, "mode": "advantage", "multiplier": None, "once_per_turn": False, "slot": None,
        "needs": None, "requires_input": None, "input_options": [], "auto_fail": False,
        "cost": {"feature_key": "fighter.prova", "amount": 1, "spell_slot_min": None},
    }]
    guide = await client.get(f"/characters/{cid}/roll-options", params={"roll": "skill", "skill": "stealth"})
    assert guide.json()[0]["dice"] == "1d4"


async def test_list_validates_roll_and_ownership(client, rules_catalog):
    cid = await _char(client)
    assert (await client.get(f"/characters/{cid}/roll-options", params={"roll": "nope"})).status_code == 422
    assert (await client.get(f"/characters/{cid}/roll-options",
                             params={"roll": "attack", "item_id": 999})).status_code == 404


# --- Ogni tiro ------------------------------------------------------------------------------------------------------

async def test_skill_and_save_add_bonus_and_dice_to_the_total(client, rules_catalog):
    rules_catalog(_feature(BLESS, GUIDE))
    cid = await _char(client)
    clean = (await client.post(f"/characters/{cid}/skills/arcana/roll", json={"die": 10})).json()
    r = await client.post(f"/characters/{cid}/skills/arcana/roll", json={"die": 10, "options": ["bless", "guide"]})
    assert r.status_code == 200, r.text
    body = r.json()
    extra = body["option_result"]["extra_rolls"]
    assert len(extra) == 1 and body["bonus"] == clean["bonus"] + 2
    assert body["total"] == 10 + clean["bonus"] + 2 + extra[0]

    clean = (await client.post(f"/characters/{cid}/saving_throws/wisdom/roll", json={"die": 10})).json()
    r = await client.post(f"/characters/{cid}/saving_throws/wisdom/roll", json={"die": 10, "options": ["bless"]})
    assert r.json()["total"] == clean["total"] + 2


async def test_skill_reroll_keeps_option_bonus(client, rules_catalog, test_session_factory):
    rules_catalog(_feature(BLESS))
    cid = await _char(client)
    async with test_session_factory() as s:
        (await s.get(Character, cid)).heroic_inspiration = True
        await s.commit()
    first = (await client.post(f"/characters/{cid}/skills/arcana/roll", json={"die": 10, "options": ["bless"]})).json()
    again = (await client.post(f"/characters/{cid}/skills/arcana/roll", json={"die": 10, "with_inspiration": True})).json()
    assert again["bonus"] == first["bonus"]


async def test_pending_save_accepts_options(client, rules_catalog, test_session_factory):
    rules_catalog(_feature(BLESS))
    cid = await _char(client)
    async with test_session_factory() as s:
        ch = await s.get(Character, cid)
        ch.conditions = {"poisoned": True}
        eff = await upsert_effect(s, ("character", cid), "poisoned", save=SaveSpec("constitution", 13, "end"))
        ps = PendingSave(effect_id=eff.id, character_id=cid, ability="constitution", dc=13, status="pending",
                         created_at="2026-11-04T10:00:00")
        s.add(ps)
        await s.commit()
        psid = ps.id
    r = await client.post(f"/characters/{cid}/pending-saves/{psid}/roll", json={"die": 11, "options": ["bless"]})
    assert r.status_code == 200, r.text
    assert r.json()["roll"]["total"] == 11 + r.json()["roll"]["bonus"] and r.json()["roll"]["bonus"] >= 2
    assert r.json()["passed"] is True


async def test_character_initiative_with_options(client, rules_catalog):
    rules_catalog(_feature(BLESS))
    cid = await _char(client)
    clean = (await client.post(f"/characters/{cid}/dice/initiative", json={"die": 10})).json()
    r = await client.post(f"/characters/{cid}/dice/initiative", json={"die": 10, "options": ["bless"]})
    assert r.status_code == 200, r.text
    assert r.json()["total"] == clean["total"] + 2 and r.json()["bonus"] == clean["bonus"] + 2


async def test_spell_damage_with_options_doubles_dice_only(client, rules_catalog):
    rules_catalog(_feature(EMPOWER))
    cid = await _char(client)
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Fuoco", "level": 1, "damage_dice": "1d10"})
    sid = r.json()["id"]
    url = f"/characters/{cid}/spells/{sid}/roll_damage"
    r = await client.post(url, json={"options": ["empower"], "main_rolls": [5]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["option_result"]["extra_rolls"]) == 2
    assert body["total"] == 5 + sum(body["option_result"]["extra_rolls"]) + 1
    assert body["half_damage"] == (body["total"] + 1) // 2
    r = await client.post(url, json={"options": ["empower"], "is_critical": True, "main_rolls": [5, 5]})
    assert len(r.json()["option_result"]["extra_rolls"]) == 4
    assert "option_result" not in (await client.post(url, json={})).json()


async def test_spell_attack_with_frightened_confirmed(client, rules_catalog):
    cid = await _char(client)
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Dardo", "level": 0, "attack_save": "ATK"})
    sid = r.json()["id"]
    await _cond(client, cid, frightened=True)
    url = f"/characters/{cid}/spells/{sid}/attack"
    assert (await client.post(url, json={"slot_level": None})).json()["mode_applied"] == "normal"
    r = await client.post(url, json={"slot_level": None, "options": ["condition:frightened"]})
    assert r.status_code == 200, r.text
    assert r.json()["mode_applied"] == "disadvantage" and r.json()["notes"] == ["condition:frightened"]


# --- Danno subito ---------------------------------------------------------------------------------------------------

async def test_damage_in_comes_before_resistance(client, rules_catalog):
    rules_catalog(_feature(UNCANNY))
    cid = await _char(client)
    r = await client.patch(f"/characters/{cid}", json={"damage_modifiers": {"resistances": ["fire"]}})
    assert r.status_code == 200, r.text
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 15, "damage_type": "fire",
                                                          "options": ["uncanny"]})
    assert r.json()["current_hit_points"] == 50 - 3  # 15 -> 7 -> 3


async def test_damage_in_with_client_annotation_recomputes_from_the_raw_value(client, rules_catalog):
    rules_catalog(_feature(UNCANNY))
    cid = await _char(client)
    r = await client.patch(f"/characters/{cid}/hp", json={
        "op": "damage", "value": 7, "raw_value": 15, "damage_modifier": "half", "options": ["uncanny"]})
    assert r.status_code == 200, r.text
    assert r.json()["current_hit_points"] == 50 - 3


async def test_evasion_and_reduction_never_go_below_zero(client, rules_catalog):
    rules_catalog(_feature(EVASION, DEFLECT))
    cid = await _char(client)
    for keys in (["evasion"], ["deflect"]):
        r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 15, "options": keys})
        assert r.status_code == 200, r.text
        assert r.json()["current_hit_points"] == 50
        assert r.json()["option_result"]["damage_after"] == 0


async def test_options_only_on_damage(client, rules_catalog):
    rules_catalog(_feature(UNCANNY))
    cid = await _char(client)
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "heal", "value": 1, "options": ["uncanny"]})
    assert r.status_code == 422


# --- Condizioni: R25 e R25 bis ----------------------------------------------------------------------------------

async def test_frightened_attack_asks_and_applies_only_when_confirmed(client, rules_catalog):
    cid = await _char(client)
    item = await _weapon(client, cid)
    await _cond(client, cid, frightened=True)
    listed = (await client.get(f"/characters/{cid}/roll-options", params={"roll": "attack", "item_id": item})).json()
    assert [o["key"] for o in listed] == ["condition:frightened"] and listed[0]["mode"] == "disadvantage"
    assert (await client.post(f"/characters/{cid}/items/{item}/attack", json={"die": 10})).json()["mode_applied"] == "normal"
    r = await client.post(f"/characters/{cid}/items/{item}/attack", json={"die": 10, "options": ["condition:frightened"]})
    assert r.json()["mode_applied"] == "disadvantage" and r.json()["notes"] == ["condition:frightened"]


async def test_frightened_skill_and_initiative(client, rules_catalog):
    cid = await _char(client)
    await _cond(client, cid, frightened=True)
    r = await client.post(f"/characters/{cid}/skills/stealth/roll", json={"die": 10, "options": ["condition:frightened"]})
    assert r.json()["mode_applied"] == "disadvantage"
    r = await client.post(f"/characters/{cid}/dice/initiative", json={"die": 10, "options": ["condition:frightened"]})
    assert r.status_code == 200, r.text
    assert r.json()["mode_applied"] == "disadvantage"
    assert (await client.post(f"/characters/{cid}/dice/initiative", json={"die": 10})).json()["mode_applied"] == "normal"


async def test_grappled_2024_asks_on_attack(client, rules_catalog):
    cid = await _char(client, edition="2024")
    item = await _weapon(client, cid)
    await _cond(client, cid, grappled=True)
    assert (await client.post(f"/characters/{cid}/items/{item}/attack", json={"die": 10})).json()["mode_applied"] == "normal"
    r = await client.post(f"/characters/{cid}/items/{item}/attack", json={"die": 10, "options": ["condition:grappled"]})
    assert r.json()["mode_applied"] == "disadvantage"


@pytest.mark.parametrize("condition", ["blinded", "deafened"])
async def test_senses_auto_fail_only_when_confirmed(client, rules_catalog, condition):
    cid = await _char(client)
    await _cond(client, cid, **{condition: True})
    assert (await client.post(f"/characters/{cid}/skills/perception/roll", json={"die": 20})).json()["auto_fail"] is False
    r = await client.post(f"/characters/{cid}/skills/perception/roll",
                          json={"die": 20, "options": [f"condition:{condition}"]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["auto_fail"] is True and body["is_critical"] is False and body["notes"] == [f"condition:{condition}"]


async def test_encounter_initiative_with_confirmed_frightened(client, test_session_factory, monkeypatch):
    sid, cid = await seed_session(test_session_factory)
    async with test_session_factory() as s:
        (await s.get(Character, cid)).conditions = {"frightened": True}
        await s.commit()
    as_user(GM_ID)
    r = await client.post(f"/sessions/{sid}/encounter", json={"mode": "full"})
    assert r.status_code in (200, 201), r.text
    pc = next(c for c in r.json()["combatants"] if c["kind"] == "pc")
    monkeypatch.setattr(random, "randint", lambda a, b: 3)
    as_user(PLAYER_ID)
    r = await client.post(f"/sessions/{sid}/encounter/combatants/{pc['id']}/initiative",
                          json={"die": 12, "options": ["condition:frightened"]})
    assert r.status_code == 200, r.text
    enc = r.json()
    assert enc["initiative_roll"]["mode_applied"] == "disadvantage"
    assert enc["initiative_roll"]["notes"] == ["condition:frightened"]
    assert next(c for c in enc["combatants"] if c["id"] == pc["id"])["initiative_die"] == 3
