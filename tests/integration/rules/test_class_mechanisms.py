"""Meccanismi comuni aggiunti per il catalogo di classe (Task 19), provati con privilegi di prova e non con il Barbaro."""
from __future__ import annotations

from sqlalchemy import select

from core.db.models import Character
from core.rules.catalog import granted_spells
from core.rules.catalog.granted_spells import GrantedSpell
from core.rules.types import FeatureSpec, Modifier, OnUse, StateSpec, UseToggle, Uses, ZeroHpSave

KEY = "fighter.prova"


def _spec(level=1, **kw) -> FeatureSpec:
    return FeatureSpec(key=KEY, class_key="fighter", edition="2014", level=level, source_title="Prova",
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


async def _use(client, cid, **body):
    return await client.post(f"/characters/{cid}/features/{KEY}/use", json=body)


def _state(ctx, params) -> StateSpec:
    return StateSpec("prova", rounds=3, blocks_casting=True, data={"scelto": bool(params.get("x"))})


async def test_state_can_depend_on_a_toggle_and_blocks_casting(client, rules_catalog):
    rules_catalog(_spec(on_use=OnUse(state=_state, toggles=(
        UseToggle("x", {"it": "Scelta", "en": "Choice"}), UseToggle("y", {"it": "No", "en": "No"}, available=lambda c: False)))))
    cid = await _fighter(client)
    ability = next(a for a in (await _full(client, cid))["abilities"] if a["feature_key"] == KEY)
    assert ability["use_toggles"] == [{"key": "x", "label": {"it": "Scelta", "en": "Choice"}}]
    state = (await _use(client, cid, params={"x": True})).json()["state"]
    assert state["data"] == {"scelto": True} and state["blocks_casting"] is True
    spell = (await client.post(f"/characters/{cid}/spells", json={"name": "Trucco", "level": 0})).json()
    assert (await client.get(f"/characters/{cid}/spells/{spell['id']}/cast-check")).json() == ["state_blocks_casting"]
    assert (await _use(client, cid)).json()["state"]["data"] == {"scelto": False}  # senza scelta: spenta


async def test_available_predicate_refuses_the_use_before_spending(client, rules_catalog):
    rules_catalog(_spec(uses=Uses(table={1: 2}), restoration="long_rest",
                        on_use=OnUse(slot="bonus", available=lambda c: False)))
    cid = await _fighter(client)
    r = await _use(client, cid)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "feature_unavailable"
    full = await _full(client, cid)
    assert next(a for a in full["abilities"] if a["feature_key"] == KEY)["uses"] == 2


async def test_use_can_end_concentration(client, rules_catalog):
    rules_catalog(_spec(on_use=OnUse(ends_concentration=True)))
    cid = await _fighter(client)
    spell = (await client.post(f"/characters/{cid}/spells", json={"name": "Luce", "level": 0, "is_concentration": True})).json()
    await client.post(f"/characters/{cid}/spells/{spell['id']}/use", json={})
    assert (await _full(client, cid))["concentrating_spell_id"] == spell["id"]
    await _use(client, cid)
    assert (await _full(client, cid))["concentrating_spell_id"] is None


async def test_state_leaves_exhaustion_however_it_ends(client, rules_catalog):
    rules_catalog(_spec(on_use=OnUse(state=StateSpec("prova", rounds=1, ends_on=("rest_short",), exhaustion_on_end=1))))
    cid = await _fighter(client)
    await _use(client, cid)
    await client.delete(f"/characters/{cid}/active-states/prova")  # a mano
    assert (await _full(client, cid))["conditions"]["exhaustion"] == 1
    await _use(client, cid)
    await client.post(f"/characters/{cid}/rounds/tick")  # scaduto
    assert (await _full(client, cid))["conditions"]["exhaustion"] == 2
    await _use(client, cid)
    await client.post(f"/characters/{cid}/rest", json={"rest_type": "short", "confirm_early": True})  # riposo
    assert (await _full(client, cid))["conditions"]["exhaustion"] == 3


async def test_immune_conditions_cannot_be_added_and_suspend_the_existing_ones(client, rules_catalog):
    rules_catalog(_spec(on_use=OnUse(state=StateSpec("prova", immune_conditions=("frightened",)))))
    cid = await _fighter(client)
    sword = (await client.post(f"/characters/{cid}/items", json={"name": "Spada", "item_type": "weapon", "item_metadata": {
        "damage_dice": "1d8", "weapon_type": "melee", "properties": []}})).json()["items"][0]["id"]
    await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"frightened": True}})

    async def keys():
        r = await client.get(f"/characters/{cid}/roll-options", params={"roll": "attack", "item_id": sword})
        return [o["key"] for o in r.json()]
    assert "condition:frightened" in await keys()
    await _use(client, cid)
    assert "condition:frightened" not in await keys()
    r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"frightened": True, "poisoned": True}})
    assert r.json()["conditions"]["poisoned"] is True  # le altre passano
    await client.delete(f"/characters/{cid}/active-states/prova")
    assert "condition:frightened" in await keys()


async def test_extra_crit_dice_and_minimum_total_modifiers(client, rules_catalog):
    rules_catalog(_spec(modifiers=(
        Modifier("crit_dice", 2, when=lambda c: c.roll == "damage"),
        Modifier("min_total", 15, when=lambda c: c.roll == "skill" and c.ability == "strength"))))
    cid = await _fighter(client)
    sword = (await client.post(f"/characters/{cid}/items", json={"name": "Spada", "item_type": "weapon", "item_metadata": {
        "damage_dice": "1d8", "weapon_type": "melee", "properties": []}})).json()["items"][0]["id"]
    crit = await client.post(f"/characters/{cid}/items/{sword}/attack", json={"die": 20, "confirm_extra_attack": True})
    assert len(crit.json()["damage_rolls"]) == 4  # 1d8 raddoppiato + 2 dadi in più
    plain = await client.post(f"/characters/{cid}/items/{sword}/attack", json={"die": 9, "confirm_extra_attack": True})
    assert len(plain.json()["damage_rolls"]) == 1
    assert (await client.post(f"/characters/{cid}/skills/athletics/roll", json={"die": 1})).json()["total"] >= 15
    assert (await client.post(f"/characters/{cid}/skills/acrobatics/roll", json={"die": 1})).json()["total"] < 15


async def test_acts_when_surprised_needs_its_state(client, rules_catalog, test_session_factory):
    rules_catalog(_spec(acts_when_surprised="prova", on_use=OnUse(state=StateSpec("prova"))))
    cid = await _fighter(client)
    async with test_session_factory() as s:
        char = (await s.execute(select(Character).where(Character.id == cid))).scalar_one()
        char.turn_state = {"surprised": True}
        await s.commit()
    assert (await _full(client, cid))["computed"]["surprised"] is True
    await _use(client, cid)
    assert (await _full(client, cid))["computed"]["surprised"] is False


def _zero(**kw) -> FeatureSpec:
    return _spec(zero_hp_save=ZeroHpSave(state="prova", **kw), on_use=OnUse(state=StateSpec("prova")))


async def _hp(client, cid, current=30, maximum=30):
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": maximum})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": current})


async def test_zero_hp_save_uses_its_own_dc_step_and_hp(client, rules_catalog, monkeypatch):
    monkeypatch.setattr("api.services.d20.random.randint", lambda a, b: 20)
    rules_catalog(_zero(base_dc=12, step=3, hp=lambda ctx: 4))
    cid = await _fighter(client)
    await _hp(client, cid)
    await _use(client, cid)
    first = (await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 35})).json()
    assert (first["zero_hp_save"]["dc"], first["current_hit_points"]) == (12, 4)
    await _hp(client, cid)
    second = (await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 35})).json()
    assert second["zero_hp_save"]["dc"] == 15
    await client.post(f"/characters/{cid}/rest", json={"rest_type": "long", "confirm_early": True})
    await _use(client, cid)
    third = (await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 35})).json()
    assert third["zero_hp_save"]["dc"] == 12


async def test_zero_hp_save_is_not_asked_without_its_state_or_when_already_at_zero(client, rules_catalog, monkeypatch):
    monkeypatch.setattr("api.services.d20.random.randint", lambda a, b: 20)
    rules_catalog(_zero())
    cid = await _fighter(client)
    await _hp(client, cid)
    assert (await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 35})).json().get("zero_hp_save") is None
    await _hp(client, cid)
    await _use(client, cid)
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 0})
    assert (await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 3})).json().get("zero_hp_save") is None


async def test_ritual_only_granted_spell_casts_as_ritual_and_warns_otherwise(client, rules_catalog, monkeypatch):
    monkeypatch.setitem(granted_spells.GRANTED_SPELLS, "prova-rituale", GrantedSpell(
        "prova-rituale", {"it": "Rituale di prova", "en": "Test ritual"}, 1, is_ritual=True, ritual_only=True))
    rules_catalog(_spec(granted_spells=("prova-rituale",)))
    cid = await _fighter(client)  # il Guerriero non ha il Lancio Rituale
    spell = next(s for s in (await client.get(f"/characters/{cid}/spells")).json() if s["name"] == "Rituale di prova")
    assert (await client.get(f"/characters/{cid}/spells/{spell['id']}/cast-check")).json() == ["ritual_only"]
    assert (await client.get(f"/characters/{cid}/spells/{spell['id']}/cast-check", params={"ritual": True})).json() == []
    assert (await client.post(f"/characters/{cid}/spells/{spell['id']}/use", json={"as_ritual": True})).status_code == 200
    plain = await client.post(f"/characters/{cid}/spells", json={"name": "Altro", "level": 1, "is_ritual": True})
    r = await client.post(f"/characters/{cid}/spells/{plain.json()['id']}/use", json={"as_ritual": True})
    assert r.status_code == 400  # il privilegio apre solo il suo incantesimo


async def test_ability_bonus_is_written_once_capped_and_taken_back(client, rules_catalog):
    rules_catalog(_spec(level=5, ability_bonus={"strength": 4, "constitution": 4}, ability_cap=24))
    cid = await _fighter(client, 4, strength=18, constitution=22)
    cls = (await _full(client, cid))["classes"][0]["id"]

    async def scores():
        return {a["name"]: a["value"] for a in (await _full(client, cid))["ability_scores"]}
    assert (await scores())["strength"] == 18
    await client.patch(f"/characters/{cid}/classes/{cls}", json={"level": 5})
    assert [(await scores())["strength"], (await scores())["constitution"]] == [22, 24]  # CON 22 + 4 si ferma a 24
    await client.patch(f"/characters/{cid}", json={"name": "Altro nome"})  # altri sync non lo ripetono
    assert (await scores())["strength"] == 22
    await client.patch(f"/characters/{cid}/classes/{cls}", json={"level": 4})
    assert [(await scores())["strength"], (await scores())["constitution"]] == [18, 22]


async def test_carry_double_and_granted_fly_speed(client, rules_catalog):
    rules_catalog(_spec(modifiers=(Modifier("carry_double", 1), Modifier("fly_speed", 1))))
    cid = await _fighter(client, strength=10)
    full = await _full(client, cid)
    assert full["carry_capacity"] == 300 and full["computed"]["fly_speed"] == full["computed"]["speed"] == 30


async def test_rules_only_spec_has_no_sheet_row(client, rules_catalog):
    rules_catalog(_spec(no_row=True))
    cid = await _fighter(client)
    assert KEY not in {a["feature_key"] for a in (await _full(client, cid))["abilities"]}
