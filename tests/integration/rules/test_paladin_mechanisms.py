"""Meccanismi comuni aggiunti dal Paladino 2014 (Task 25): opzioni automatiche, TS ripetuto degli effetti sugli altri, volo
fisso, immunità che vale da coscienti, scelte facoltative e filtri sull'uso di un privilegio."""
from __future__ import annotations

from core.rules.condition_removal import ConditionRemoval
from core.rules.types import (
    ChoiceSpec, FeatureSpec, Modifier, OnUse, RollOptionSpec, TargetEffect, UseChoice, Uses,
)
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, setup_full_encounter
from tests.integration._telegram_stub import install_fake_telegram

_LABEL = {"it": "Applica?", "en": "Apply?"}


def _melee(ctx) -> bool:
    return ctx.item is not None and ctx.attack_mode in ("melee", "offhand")


AUTO = RollOptionSpec(key="auto", phase="before", rolls=("attack",), label=_LABEL, automatic=True,
                      extra_dice=lambda _c, _i: "1d4", available=_melee,
                      effect=lambda _c, _i: {"it": "Radioso", "en": "Radiant"})
ASKED = RollOptionSpec(key="asked", phase="before", rolls=("attack",), label=_LABEL, bonus=lambda _c, _i: 1)


def _feature(*, key="fighter.prova", **kw) -> FeatureSpec:
    return FeatureSpec(key=key, class_key="fighter", edition="2014", level=1, source_title="Prova",
                       name={"it": "Prova", "en": "Test"}, summary={"it": "x", "en": "x"}, action_type=kw.pop("action_type", None), **kw)


async def _char(client, level=5, hp=50) -> int:
    cid = (await client.post("/characters", json={"name": "Prova"})).json()["id"]
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "fighter", "level": level, "hit_die": 10})
    assert r.status_code == 201, r.text
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": hp})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": hp})
    return cid


async def _weapon(client, cid, mode="melee") -> int:
    name = "Spada" if mode == "melee" else "Arco"
    r = await client.post(f"/characters/{cid}/items", json={"name": name, "item_type": "weapon", "item_metadata": {
        "damage_dice": "1d8", "weapon_type": mode, "properties": []}})
    return next(i["id"] for i in r.json()["items"] if i["name"] == name)


async def _full(client, cid) -> dict:
    return (await client.get(f"/characters/{cid}")).json()


# --- Opzione automatica ---------------------------------------------------------------------------------------------

async def test_an_automatic_option_is_applied_without_being_asked_and_never_listed(client, rules_catalog):
    rules_catalog(_feature(roll_options=(AUTO, ASKED)))
    cid = await _char(client)
    wid = await _weapon(client, cid)
    listed = (await client.get(f"/characters/{cid}/roll-options", params={"roll": "attack", "item_id": wid})).json()
    assert [o["key"] for o in listed] == ["asked"]
    body = (await client.post(f"/characters/{cid}/items/{wid}/attack", json={"die": 10})).json()
    block = body["option_result"]
    assert block["keys"] == ["auto"] and len(block["extra_rolls"]) == 1 and block["effects"] == [{"it": "Radioso", "en": "Radiant"}]
    assert body["damage_total"] == sum(body["damage_rolls"]) + body["damage_bonus"] + sum(block["extra_rolls"])


async def test_an_automatic_option_doubles_on_a_critical_and_follows_its_availability(client, rules_catalog):
    rules_catalog(_feature(roll_options=(AUTO,)))
    cid = await _char(client)
    sword, bow = await _weapon(client, cid), await _weapon(client, cid, "ranged")
    crit = await client.post(f"/characters/{cid}/items/{sword}/attack", json={"die": 20, "confirm_extra_attack": True})
    assert len(crit.json()["option_result"]["extra_rolls"]) == 2
    shot = await client.post(f"/characters/{cid}/items/{bow}/attack", json={"die": 10, "confirm_extra_attack": True})
    assert shot.status_code == 200 and shot.json().get("option_result") is None


async def test_an_automatic_option_cannot_be_forced_in_the_request(client, rules_catalog):
    rules_catalog(_feature(roll_options=(AUTO,)))
    cid = await _char(client)
    wid = await _weapon(client, cid)
    body = (await client.post(f"/characters/{cid}/items/{wid}/attack", json={"die": 10, "options": ["auto"]})).json()
    assert body["option_result"]["keys"] == ["auto"]  # una volta sola, anche se il client la nomina


# --- TS ripetuto -----------------------------------------------------------------------------------------------------

def _binding() -> FeatureSpec:
    return _feature(on_use=OnUse(target_effect=lambda _c, _i: TargetEffect(
        condition="restrained", save_ability="strength", save_dc=14, repeat_save="end")))


async def test_a_target_effect_can_repeat_its_save_at_the_end_of_the_targets_turn(client, test_session_factory, rules_catalog, monkeypatch):
    install_fake_telegram(monkeypatch)
    rules_catalog(_binding())
    sid, _ = await setup_full_encounter(client, test_session_factory)
    r = await client.post(f"/sessions/{sid}/encounter/start", json={})
    pc, goblin, _ = r.json()["combatants"]
    cid = pc["character_id"]
    as_user(PLAYER_ID)
    await client.post(f"/characters/{cid}/classes", json={"class_name": "fighter", "level": 3, "hit_die": 10})
    assert (await client.post(f"/characters/{cid}/features/fighter.prova/use", json={})).status_code == 200
    r = await client.post(f"/characters/{cid}/target-effects", json={"combatant_id": goblin["id"], "effect_key": "fighter.prova"})
    assert r.status_code == 200, r.text
    as_user(GM_ID)
    live = (await client.get(f"/sessions/{sid}/live")).json()
    mon = next(c for c in live["encounter"]["combatants"] if c["id"] == goblin["id"])
    [save] = mon["pending_saves"]
    r = await client.post(f"/sessions/{sid}/encounter/pending-saves/{save['id']}/resolve", json={"passed": False})
    assert r.status_code == 200, r.text
    live = (await client.get(f"/sessions/{sid}/live")).json()
    [eff] = next(c for c in live["encounter"]["combatants"] if c["id"] == goblin["id"])["condition_effects"]
    assert (eff["slug"], eff["save_ability"], eff["save_dc"], eff["save_edge"]) == ("restrained", "strength", 14, "end")


async def test_a_target_effect_without_repeat_leaves_no_repeated_save(client, test_session_factory, rules_catalog, monkeypatch):
    install_fake_telegram(monkeypatch)
    rules_catalog(_feature(on_use=OnUse(target_effect=lambda _c, _i: TargetEffect(
        condition="restrained", save_ability="strength", save_dc=14))))
    sid, _ = await setup_full_encounter(client, test_session_factory)
    pc, goblin, _ = (await client.post(f"/sessions/{sid}/encounter/start", json={})).json()["combatants"]
    cid = pc["character_id"]
    as_user(PLAYER_ID)
    await client.post(f"/characters/{cid}/classes", json={"class_name": "fighter", "level": 3, "hit_die": 10})
    await client.post(f"/characters/{cid}/features/fighter.prova/use", json={})
    await client.post(f"/characters/{cid}/target-effects", json={"combatant_id": goblin["id"], "effect_key": "fighter.prova"})
    as_user(GM_ID)
    live = (await client.get(f"/sessions/{sid}/live")).json()
    [save] = next(c for c in live["encounter"]["combatants"] if c["id"] == goblin["id"])["pending_saves"]
    await client.post(f"/sessions/{sid}/encounter/pending-saves/{save['id']}/resolve", json={"passed": False})
    live = (await client.get(f"/sessions/{sid}/live")).json()
    [eff] = next(c for c in live["encounter"]["combatants"] if c["id"] == goblin["id"])["condition_effects"]
    assert eff["save_ability"] is None and eff["save_edge"] is None


# --- Volo fisso ------------------------------------------------------------------------------------------------------

async def test_a_fixed_flying_speed_is_shown_and_never_lowers_the_walking_one(client, rules_catalog):
    rules_catalog(_feature(modifiers=(Modifier("fly_speed_value", 60, source="feature:fighter.prova"),)))
    cid = await _char(client)
    computed = (await _full(client, cid))["computed"]
    assert computed["fly_speed"] == 60


async def test_the_flying_speed_equal_to_walking_wins_when_higher(client, rules_catalog):
    rules_catalog(_feature(modifiers=(Modifier("fly_speed_value", 20), Modifier("fly_speed", 1))))
    cid = await _char(client)
    computed = (await _full(client, cid))["computed"]
    assert computed["fly_speed"] == max(20, computed["speed"])


# --- Immunità da coscienti -------------------------------------------------------------------------------------------

async def test_a_conscious_only_immunity_stops_at_zero_hp(client, rules_catalog, test_session_factory):
    from core.db.models import Character
    rules_catalog(_feature(condition_immunities=("charmed",), needs_conscious=True))
    cid = await _char(client)
    r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"charmed": True}})
    assert not r.json()["conditions"].get("charmed")
    async with test_session_factory() as s:
        (await s.get(Character, cid)).current_hit_points = 0
        await s.commit()
    r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"charmed": True}})
    assert r.json()["conditions"].get("charmed") is True


async def test_an_immunity_without_the_flag_holds_at_zero_hp_too(client, rules_catalog, test_session_factory):
    from core.db.models import Character
    rules_catalog(_feature(condition_immunities=("charmed",)))
    cid = await _char(client)
    async with test_session_factory() as s:
        (await s.get(Character, cid)).current_hit_points = 0
        await s.commit()
    r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"charmed": True}})
    assert not r.json()["conditions"].get("charmed")


# --- Scelte facoltative e filtri sull'uso -----------------------------------------------------------------------------

def _pool_feature() -> FeatureSpec:
    labels = lambda _ctx, key: {"it": f"Etichetta {key}", "en": f"Label {key}"}  # noqa: E731
    return _feature(
        uses=Uses(per_level=2), restoration="long_rest", action_type="action",
        on_use=OnUse(
            choose_amount=True, removal=ConditionRemoval(("charmed", "frightened"), ally=False),
            heal=lambda _c, _r: 1, heal_when=lambda _c, params: params.get("mode") == "self",
            amount_ok=lambda _c, amount, params: params.get("mode") != "cure" or amount % 5 == 0,
            choices=(UseChoice("mode", {"it": "Modo", "en": "Mode"}, lambda _c: ["self", "other", "cure"],
                               lambda k: {"it": k, "en": k}),
                     UseChoice("condition", {"it": "Condizione", "en": "Condition"},
                               lambda c: [k for k, v in (c.char.conditions or {}).items() if v],
                               lambda k: {"it": k, "en": k}, optional=True, option_label_ctx=labels))))


async def _use(client, cid, amount=1, **params):
    return await client.post(f"/characters/{cid}/features/fighter.prova/use", json={"amount": amount, "params": params})


async def test_heal_when_decides_whether_the_use_heals_the_user(client, rules_catalog):
    rules_catalog(_pool_feature())
    cid = await _char(client)
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 10})
    assert (await _use(client, cid, 3, mode="other")).json()["healed"] == 0
    assert (await _use(client, cid, 3, mode="self")).json()["healed"] == 3
    assert (await _full(client, cid))["current_hit_points"] == 13


async def test_amount_ok_refuses_before_spending_anything(client, rules_catalog):
    rules_catalog(_pool_feature())
    cid = await _char(client)
    r = await _use(client, cid, 4, mode="cure")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "amount_invalid"
    assert next(a for a in (await _full(client, cid))["abilities"] if a["feature_key"] == "fighter.prova")["uses"] == 10
    assert (await _use(client, cid, 5, mode="cure")).status_code == 200


async def test_an_optional_choice_may_be_left_out_and_when_given_it_must_be_valid(client, rules_catalog):
    rules_catalog(_pool_feature())
    cid = await _char(client)
    await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"charmed": True}})
    row = next(a for a in (await _full(client, cid))["abilities"] if a["feature_key"] == "fighter.prova")
    cond = next(c for c in row["use_choices"] if c["key"] == "condition")
    assert cond["options"] == [{"key": "charmed", "label": {"it": "Etichetta charmed", "en": "Label charmed"}}]
    assert (await _use(client, cid, mode="other")).status_code == 200
    assert (await _full(client, cid))["conditions"]["charmed"] is True  # senza la scelta la condizione resta
    assert (await _use(client, cid, mode="other", condition="frightened")).status_code == 422
    assert (await _use(client, cid, mode="other", condition="charmed")).status_code == 200
    assert not (await _full(client, cid))["conditions"].get("charmed")


async def test_a_mandatory_choice_still_has_to_be_given(client, rules_catalog):
    rules_catalog(_pool_feature())
    cid = await _char(client)
    assert (await _use(client, cid)).status_code == 422


# --- Riserva condivisa ------------------------------------------------------------------------------------------------

def _shared(key: str, class_key: str, table: dict, group: str = "pool") -> FeatureSpec:
    return FeatureSpec(
        key=key, class_key=class_key, edition="2014", level=1, source_title=key, name={"it": key, "en": key},
        summary={"it": "x", "en": "x"}, action_type="action", uses=Uses(table=table), restoration="short_rest", shared_pool=group)


def _spender(key: str, class_key: str, spends: str) -> FeatureSpec:
    return FeatureSpec(
        key=key, class_key=class_key, edition="2014", level=1, source_title=key, name={"it": key, "en": key},
        summary={"it": "x", "en": "x"}, action_type="action", on_use=OnUse(spends=spends))


async def _two_classes(client, fighter_level, wizard_level) -> int:
    cid = await _char(client, fighter_level)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "wizard", "level": wizard_level, "hit_die": 6})
    assert r.status_code == 201, r.text
    return cid


def _rows(full: dict, *keys: str) -> dict[str, int | None]:
    return {a["feature_key"]: a["max_uses"] for a in full["abilities"] if a["feature_key"] in keys}


async def test_a_shared_pool_is_held_by_one_class_only_with_the_larger_value(client, rules_catalog):
    rules_catalog(_shared("fighter.pool", "fighter", {1: 1, 6: 2}), _shared("wizard.pool", "wizard", {1: 1, 3: 3}))
    cid = await _two_classes(client, 5, 3)
    assert _rows(await _full(client, cid), "fighter.pool", "wizard.pool") == {"wizard.pool": 3}
    cid = await _two_classes(client, 6, 1)
    assert _rows(await _full(client, cid), "fighter.pool", "wizard.pool") == {"fighter.pool": 2}


async def test_equal_pools_give_one_row_held_by_the_first_class(client, rules_catalog):
    rules_catalog(_shared("fighter.pool", "fighter", {1: 1}), _shared("wizard.pool", "wizard", {1: 1}))
    cid = await _two_classes(client, 3, 3)
    assert _rows(await _full(client, cid), "fighter.pool", "wizard.pool") == {"fighter.pool": 1}


async def test_an_effect_of_either_class_spends_the_one_shared_row(client, rules_catalog):
    rules_catalog(_shared("fighter.pool", "fighter", {1: 2}), _shared("wizard.pool", "wizard", {1: 1}),
                  _spender("wizard.spender", "wizard", "wizard.pool"), _spender("fighter.spender", "fighter", "fighter.pool"))
    cid = await _two_classes(client, 3, 3)
    assert (await client.post(f"/characters/{cid}/features/wizard.spender/use", json={})).status_code == 200
    held = next(a for a in (await _full(client, cid))["abilities"] if a["feature_key"] == "fighter.pool")
    assert (held["max_uses"], held["uses"]) == (2, 1)
    assert (await client.post(f"/characters/{cid}/features/fighter.spender/use", json={})).status_code == 200
    assert (await client.post(f"/characters/{cid}/features/wizard.spender/use", json={})).status_code == 409


async def test_a_single_class_keeps_its_own_pool(client, rules_catalog):
    rules_catalog(_shared("fighter.pool", "fighter", {1: 2}), _shared("wizard.pool", "wizard", {1: 1}))
    cid = await _char(client, 3)
    assert _rows(await _full(client, cid), "fighter.pool", "wizard.pool") == {"fighter.pool": 2}
