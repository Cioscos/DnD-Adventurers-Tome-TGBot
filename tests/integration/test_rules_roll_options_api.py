"""Conferma al tiro attraverso l'API: ogni flusso accetta `options`, il server riconvalida sempre."""
from __future__ import annotations

import random
from dataclasses import replace

import pytest
from sqlalchemy import select

from api.services.condition_effects import SaveSpec, upsert_effect
from core.db.models import AbilityScore, Character, PendingSave
from core.rules.types import Cost, FeatureSpec, RollOptionSpec, Uses
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, seed_session, setup_full_encounter
from tests.integration._telegram_stub import install_fake_telegram

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
    r = await client.post(f"/characters/{cid}/items/{item}/attack",
                          json={"die": die, "defer_damage": True, "confirm_extra_attack": True, **extra})
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

    async_ok = await client.post(f"/characters/{cid}/items/{item}/attack",
                                 json={"die": 10, "options": ["focus"], "confirm_extra_attack": True})
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
    rules_catalog(replace(_feature(bless_paid, uses=Uses(table={1: 1})), edition="2024"))
    cid = await _char(client, edition="2024")
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
        "needs": None, "group": None, "dice_cost": 0, "requires_input": None, "input_options": [],
        "auto_fail": False, "after": None, "pay_if_success": False, "saved_dice": [], "reroll_limit": None, "keep_rolled": False,
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
    rules_catalog(replace(_feature(BLESS), edition="2024"))
    cid = await _char(client, edition="2024")
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
    assert body["half_damage"] == body["total"] // 2
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


# --- Revisione: caratteristica e modalità sull'elenco (I2) -----------------------------------------------------------

def _keys(listed) -> list[str]:
    assert listed.status_code == 200, listed.text
    return [o["key"] for o in listed.json()]


async def _scores(factory, cid, **scores) -> None:
    async with factory() as s:
        rows = (await s.execute(select(AbilityScore).where(AbilityScore.character_id == cid))).scalars().all()
        for row in rows:
            row.value = scores.get(row.name, row.value)
        await s.commit()


async def _thrown_finesse(client, cid) -> int:
    return await _weapon(client, cid, properties=("finesse", "thrown"))


STR_ONLY = RollOptionSpec(key="reckless", phase="before", rolls=("attack",), label=_LABEL,
                          available=lambda ctx: ctx.ability == "strength")
MELEE_ONLY = RollOptionSpec(key="smite", phase="after_hit", rolls=("attack",), label=_LABEL,
                            available=lambda ctx: ctx.attack_mode == "melee", extra_dice=lambda _c, _i: "1d8")
TWO_HANDS = RollOptionSpec(key="gwf", phase="before", rolls=("attack",), label=_LABEL,
                           available=lambda ctx: ctx.grip == "two")


async def test_list_knows_the_ability_of_the_attack_like_the_roll(client, rules_catalog, test_session_factory):
    rules_catalog(_feature(STR_ONLY))
    cid = await _char(client)
    await _scores(test_session_factory, cid, strength=10, dexterity=18)
    finesse = await _weapon(client, cid)
    params = {"roll": "attack", "item_id": finesse}
    assert _keys(await client.get(f"/characters/{cid}/roll-options", params=params)) == []
    r = await client.post(f"/characters/{cid}/items/{finesse}/attack", json={"die": 10, "options": ["reckless"]})
    assert r.status_code == 409
    await _scores(test_session_factory, cid, strength=18, dexterity=10)
    assert _keys(await client.get(f"/characters/{cid}/roll-options", params=params)) == ["reckless"]
    r = await client.post(f"/characters/{cid}/items/{finesse}/attack", json={"die": 10, "options": ["reckless"]})
    assert r.status_code == 200, r.text


async def test_list_knows_the_ability_of_an_unarmed_strike(client, rules_catalog, test_session_factory):
    rules_catalog(_feature(STR_ONLY))
    cid = await _char(client)
    await _scores(test_session_factory, cid, strength=18, dexterity=10)
    assert _keys(await client.get(f"/characters/{cid}/roll-options", params={"roll": "attack"})) == ["reckless"]


async def test_attack_mode_separates_melee_thrown_and_ranged(client, rules_catalog):
    rules_catalog(_feature(MELEE_ONLY))
    cid = await _char(client)
    dagger = await _thrown_finesse(client, cid)
    base = {"roll": "attack", "item_id": dagger}
    url = f"/characters/{cid}/roll-options"
    assert _keys(await client.get(url, params=base)) == ["smite"]
    assert _keys(await client.get(url, params={**base, "attack_mode": "thrown"})) == []
    # il server legge la stessa modalità nel secondo tempo
    hit = await _deferred(client, cid, dagger, attack_mode="thrown")
    r = await client.post(f"/characters/{cid}/attack/{hit['attack_id']}/damage", json={"options": ["smite"]})
    assert r.status_code == 409 and _code(r) == "option_unavailable"
    hit = await _deferred(client, cid, dagger)
    r = await client.post(f"/characters/{cid}/attack/{hit['attack_id']}/damage", json={"options": ["smite"]})
    assert r.status_code == 200, r.text
    r = await client.post(f"/characters/{cid}/items", json={
        "name": "Arco", "item_type": "weapon",
        "item_metadata": {"damage_dice": "1d8", "weapon_type": "ranged", "properties": []}})
    bow = next(i["id"] for i in r.json()["items"] if i["name"] == "Arco")
    assert _keys(await client.get(url, params={"roll": "attack", "item_id": bow})) == []


async def test_grip_reaches_the_context(client, rules_catalog):
    rules_catalog(_feature(TWO_HANDS))
    cid = await _char(client)
    item = await _weapon(client, cid)
    url = f"/characters/{cid}/roll-options"
    assert _keys(await client.get(url, params={"roll": "attack", "item_id": item})) == []
    assert _keys(await client.get(url, params={"roll": "attack", "item_id": item, "grip": "two"})) == ["gwf"]
    r = await client.post(f"/characters/{cid}/items/{item}/attack", json={"die": 10, "grip": "two", "options": ["gwf"]})
    assert r.status_code == 200, r.text


# --- Revisione: once_per_turn fuori dal proprio turno (I3) ------------------------------------------------------------

async def _once_used(factory, cid, reaction=True) -> None:
    async with factory() as s:
        (await s.get(Character, cid)).turn_state = {"once_per_turn": ["sneak"], "reaction_used": reaction}
        await s.commit()


async def _turn(factory, cid) -> dict:
    async with factory() as s:
        return dict((await s.get(Character, cid)).turn_state or {})


async def test_every_turn_start_clears_once_per_turn_of_all_pcs(client, test_session_factory, monkeypatch):
    install_fake_telegram(monkeypatch)
    sid, _ = await setup_full_encounter(client, test_session_factory)
    enc = (await client.post(f"/sessions/{sid}/encounter/start", json={})).json()
    cid = next(c["character_id"] for c in enc["combatants"] if c["kind"] == "pc")
    await _once_used(test_session_factory, cid)

    assert (await client.post(f"/sessions/{sid}/encounter/next-turn")).status_code == 200  # tocca a un mostro
    turn = await _turn(test_session_factory, cid)
    assert turn["once_per_turn"] == [] and turn["reaction_used"] is True

    # l'annullamento dell'avanzamento rimette la lista com'era
    assert (await client.post(f"/sessions/{sid}/encounter/prev-turn")).status_code == 200
    assert (await _turn(test_session_factory, cid))["once_per_turn"] == ["sneak"]


async def test_other_turn_command_clears_only_once_per_turn(client, rules_catalog, test_session_factory):
    rules_catalog(_feature(SNEAK))
    cid = await _char(client)
    item = await _weapon(client, cid)
    await _once_used(test_session_factory, cid)
    url = f"/characters/{cid}/roll-options"
    assert _keys(await client.get(url, params={"roll": "attack", "item_id": item})) == []
    r = await client.post(f"/characters/{cid}/turn/other")
    assert r.status_code == 200, r.text
    assert r.json()["once_per_turn"] == [] and r.json()["reaction_used"] is True
    assert _keys(await client.get(url, params={"roll": "attack", "item_id": item})) == ["sneak"]


# --- Revisione: /hp/undo rimborsa (I4) --------------------------------------------------------------------------------

async def test_hp_undo_gives_back_what_the_option_paid(client, rules_catalog):
    paid = RollOptionSpec(key="dodge", phase="damage_in", rolls=("damage_taken",), label=_LABEL, slot="reaction",
                          once_per_turn=True, multiplier=0.5, cost=Cost(feature_key="fighter.prova"))
    rules_catalog(_feature(paid, uses=Uses(table={1: 1})))
    cid = await _char(client)
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 15, "options": ["dodge"]})
    assert r.status_code == 200, r.text
    assert await _uses(client, cid) == 0
    r = await client.post(f"/characters/{cid}/hp/undo", json={"op_id": r.json()["hp_undo_id"]})
    assert r.status_code == 200, r.text
    assert r.json()["current_hit_points"] == 50 and await _uses(client, cid) == 1
    assert (await client.get(f"/characters/{cid}/turn-state")).json()["turn"]["reaction_used"] is False
    # si ribatte il danno: l'opzione c'è ancora
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 9, "options": ["dodge"]})
    assert r.status_code == 200 and r.json()["current_hit_points"] == 50 - 4


async def test_hp_undo_gives_back_the_spell_slot(client, rules_catalog):
    slot_option = RollOptionSpec(key="shield", phase="damage_in", rolls=("damage_taken",), label=_LABEL,
                                 requires_input="slot", cost=Cost(spell_slot_min=1), multiplier=0)
    rules_catalog(_feature(slot_option))
    cid = await _char(client)
    await _slot(client, cid, 1)
    r = await client.patch(f"/characters/{cid}/hp", json={
        "op": "damage", "value": 5, "options": ["shield"], "option_inputs": {"shield": {"slot_level": 1}}})
    assert r.status_code == 200, r.text
    assert r.json()["spell_slots"][0]["used"] == 1
    r = await client.post(f"/characters/{cid}/hp/undo", json={"op_id": r.json()["hp_undo_id"]})
    assert r.json()["spell_slots"][0]["used"] == 0


async def test_hp_undo_without_options_touches_nothing_else(client, rules_catalog, test_session_factory):
    cid = await _char(client)
    await _once_used(test_session_factory, cid)
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 5})
    await client.post(f"/characters/{cid}/hp/undo", json={"op_id": r.json()["hp_undo_id"]})
    turn = await _turn(test_session_factory, cid)
    assert turn["reaction_used"] is True and turn["once_per_turn"] == ["sneak"]


# --- Revisione: forme del catalogo ------------------------------------------------------------------------------------

async def test_group_is_one_option_per_request_through_the_api(client, rules_catalog):
    rules_catalog(_feature(
        RollOptionSpec(key="m1", phase="before", rolls=("attack",), label=_LABEL, group="maneuver"),
        RollOptionSpec(key="m2", phase="before", rolls=("attack",), label=_LABEL, group="maneuver"),
    ))
    cid = await _char(client)
    item = await _weapon(client, cid)
    listed = (await client.get(f"/characters/{cid}/roll-options", params={"roll": "attack", "item_id": item})).json()
    assert [o["group"] for o in listed] == ["maneuver", "maneuver"]
    r = await client.post(f"/characters/{cid}/items/{item}/attack", json={"options": ["m1", "m2"]})
    assert r.status_code == 409


async def test_needs_across_phases_reads_the_pending_attack(client, rules_catalog):
    rules_catalog(_feature(
        RollOptionSpec(key="reckless", phase="before", rolls=("attack",), label=_LABEL),
        RollOptionSpec(key="brutal", phase="after_hit", rolls=("attack",), label=_LABEL, needs="reckless",
                       extra_dice=lambda _c, _i: "1d10"),
    ))
    cid = await _char(client)
    item = await _weapon(client, cid)
    url = f"/characters/{cid}/roll-options"
    plain = await _deferred(client, cid, item)
    r = await client.post(f"/characters/{cid}/attack/{plain['attack_id']}/damage", json={"options": ["brutal"]})
    assert r.status_code == 409

    hit = await _deferred(client, cid, item, options=["reckless"])
    # confermata al primo tempo: il prompt del secondo non la chiede più come dipendenza
    listed = (await client.get(url, params={"roll": "attack", "item_id": item})).json()
    assert next(o for o in listed if o["key"] == "brutal")["needs"] is None
    r = await client.post(f"/characters/{cid}/attack/{hit['attack_id']}/damage", json={"options": ["brutal"]})
    assert r.status_code == 200, r.text
    assert len(r.json()["option_result"]["extra_rolls"]) == 1


async def test_dice_cost_through_the_second_step(client, rules_catalog):
    rules_catalog(_feature(
        RollOptionSpec(key="sneak", phase="after_hit", rolls=("attack",), label=_LABEL, extra_dice=lambda _c, _i: "3d6"),
        RollOptionSpec(key="poison", phase="after_hit", rolls=("attack",), label=_LABEL, needs="sneak", dice_cost=1),
    ))
    cid = await _char(client)
    item = await _weapon(client, cid)
    hit = await _deferred(client, cid, item)
    r = await client.post(f"/characters/{cid}/attack/{hit['attack_id']}/damage", json={"options": ["sneak", "poison"]})
    assert r.status_code == 200, r.text
    assert len(r.json()["option_result"]["extra_rolls"]) == 2


async def test_dice_outside_crit_and_outside_the_total(client, rules_catalog):
    rules_catalog(_feature(
        RollOptionSpec(key="hellish", phase="after_hit", rolls=("attack",), label=_LABEL, crit_doubles=False,
                       extra_dice=lambda _c, _i: "2d6"),
        RollOptionSpec(key="sweep", phase="after_hit", rolls=("attack",), label=_LABEL, crit_doubles=False,
                       separate_damage=True, extra_dice=lambda _c, _i: "1d8"),
    ))
    cid = await _char(client)
    item = await _weapon(client, cid)
    crit = await _deferred(client, cid, item, die=20)
    r = await client.post(f"/characters/{cid}/attack/{crit['attack_id']}/damage", json={"options": ["hellish", "sweep"]})
    assert r.status_code == 200, r.text
    body = r.json()
    result = body["option_result"]
    assert len(result["extra_rolls"]) == 2  # niente raddoppio
    assert len(result["separate_rolls"]) == 1 and result["separate_total"] == result["separate_rolls"][0]
    assert body["damage_total"] == crit["damage_total"] + sum(result["extra_rolls"])


async def test_on_confirm_runs_in_the_same_transaction(client, rules_catalog):
    def set_temp(_session, ctx, _inputs) -> None:
        ctx.char.temp_hp = ctx.class_level

    rules_catalog(_feature(RollOptionSpec(key="blessing", phase="before", rolls=("skill",), label=_LABEL,
                                          on_confirm=set_temp)))
    cid = await _char(client)
    r = await client.post(f"/characters/{cid}/skills/arcana/roll", json={"die": 10, "options": ["blessing"]})
    assert r.status_code == 200, r.text
    assert (await client.get(f"/characters/{cid}")).json()["temp_hp"] == 5


async def test_death_save_accepts_options(client, rules_catalog):
    rules_catalog(_feature(RollOptionSpec(key="vengeance", phase="before", rolls=("death_save",), label=_LABEL,
                                          bonus=lambda _c, _i: 5)))
    cid = await _char(client)
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 0})
    assert _keys(await client.get(f"/characters/{cid}/roll-options", params={"roll": "death_save"})) == ["vengeance"]
    r = await client.post(f"/characters/{cid}/death_saves/roll", json={"die": 6})
    assert r.json()["outcome"] == "failure" and "option_result" not in r.json()
    r = await client.post(f"/characters/{cid}/death_saves/roll", json={"die": 6, "options": ["vengeance"]})
    assert r.status_code == 200, r.text
    assert r.json()["outcome"] == "success" and r.json()["option_result"]["keys"] == ["vengeance"]


async def test_gm_cannot_spend_the_options_of_a_player(client, test_session_factory):
    sid, cid = await seed_session(test_session_factory)
    async with test_session_factory() as s:
        (await s.get(Character, cid)).conditions = {"frightened": True}
        await s.commit()
    as_user(GM_ID)
    pc = next(c for c in (await client.post(f"/sessions/{sid}/encounter", json={"mode": "full"})).json()["combatants"]
              if c["kind"] == "pc")
    r = await client.post(f"/sessions/{sid}/encounter/combatants/{pc['id']}/initiative",
                          json={"die": 12, "options": ["condition:frightened"]})
    assert r.status_code == 403
    r = await client.post(f"/sessions/{sid}/encounter/combatants/{pc['id']}/initiative", json={"die": 12})
    assert r.status_code == 200, r.text
