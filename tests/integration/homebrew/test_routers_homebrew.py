"""Integration tests on the homebrew router via httpx AsyncClient."""
import json

import pytest


@pytest.mark.asyncio
async def test_list_templates_returns_quality_wear(client):
    r = await client.get("/homebrew/templates")
    assert r.status_code == 200
    data = r.json()
    assert any(t["id"] == "quality_wear" for t in data)
    # Shape of TemplateRead — no dsl in the listing
    qu = next(t for t in data if t["id"] == "quality_wear")
    assert "name" in qu
    assert "description" in qu
    assert "icon" in qu
    assert "dsl" not in qu


@pytest.mark.asyncio
async def test_get_template_detail_includes_dsl(client):
    r = await client.get("/homebrew/templates/quality_wear")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == "quality_wear"
    assert body["dsl"]["version"] == 1


@pytest.mark.asyncio
async def test_get_template_detail_unknown_returns_404(client):
    r = await client.get("/homebrew/templates/does_not_exist")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_list_rules_empty_initially(client, char_id):
    r = await client.get(f"/characters/{char_id}/homebrew/rules")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_list_rules_unknown_char_returns_404(client):
    r = await client.get("/characters/99999/homebrew/rules")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_get_rule_unknown_returns_404(client, char_id):
    r = await client.get(f"/characters/{char_id}/homebrew/rules/99999")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_list_rules_other_user_char_returns_403(client, test_session_factory):
    """A character owned by a DIFFERENT user must return 403, not leak its data."""
    from core.db.models import Character
    async with test_session_factory() as s:
        other = Character(user_id=9999, name="Someone Else")
        s.add(other)
        await s.commit()
        await s.refresh(other)
        other_id = other.id
    r = await client.get(f"/characters/{other_id}/homebrew/rules")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_get_rule_other_user_char_returns_403(client, test_session_factory):
    from core.db.models import Character
    async with test_session_factory() as s:
        other = Character(user_id=9999, name="Someone Else")
        s.add(other)
        await s.commit()
        await s.refresh(other)
        other_id = other.id
    r = await client.get(f"/characters/{other_id}/homebrew/rules/1")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_install_template_creates_rule_and_returns_201(client, char_id):
    r = await client.post(f"/characters/{char_id}/homebrew/templates/quality_wear/install")
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Qualità & Usura"
    assert body["template_id"] == "quality_wear"
    assert body["enabled"] is True
    # The rule is now listed
    rules = (await client.get(f"/characters/{char_id}/homebrew/rules")).json()
    assert len(rules) == 1


@pytest.mark.asyncio
async def test_install_template_unknown_returns_404(client, char_id):
    r = await client.post(f"/characters/{char_id}/homebrew/templates/does_not_exist/install")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_install_template_materializes_defaults_on_matching_items(
    client, char_id, test_session_factory,
):
    from core.db.models import Item
    # Pre-create a weapon AND a non-matching item BEFORE install
    async with test_session_factory() as s:
        weapon = Item(character_id=char_id, name="Spada lunga", item_type="weapon", quantity=1)
        gear = Item(character_id=char_id, name="Zaino", item_type="gear", quantity=1)
        s.add_all([weapon, gear])
        await s.commit()
        await s.refresh(weapon)
        await s.refresh(gear)
        weapon_id = weapon.id
        gear_id = gear.id

    r = await client.post(f"/characters/{char_id}/homebrew/templates/quality_wear/install")
    assert r.status_code == 201

    # Check via a fresh session — weapon must have hb_quality + hb_damage_state, gear must NOT
    async with test_session_factory() as s:
        from sqlalchemy import select
        weapon = (await s.execute(select(Item).where(Item.id == weapon_id))).scalar_one()
        gear = (await s.execute(select(Item).where(Item.id == gear_id))).scalar_one()
        wmd = json.loads(weapon.item_metadata or "{}")
        gmd = json.loads(gear.item_metadata or "{}")
    assert wmd.get("hb_quality") == "ordinaria"
    assert wmd.get("hb_damage_state") == "integra"
    assert "hb_quality" not in gmd
    assert "hb_damage_state" not in gmd


@pytest.mark.asyncio
async def test_install_template_does_not_overwrite_existing_metadata(
    client, char_id, test_session_factory,
):
    from core.db.models import Item
    # Item has hb_quality already set
    async with test_session_factory() as s:
        weapon = Item(
            character_id=char_id, name="Spada", item_type="weapon", quantity=1,
            item_metadata=json.dumps({"hb_quality": "pessima"}),
        )
        s.add(weapon)
        await s.commit()
        await s.refresh(weapon)
        weapon_id = weapon.id

    await client.post(f"/characters/{char_id}/homebrew/templates/quality_wear/install")

    async with test_session_factory() as s:
        from sqlalchemy import select
        weapon = (await s.execute(select(Item).where(Item.id == weapon_id))).scalar_one()
        md = json.loads(weapon.item_metadata)
    assert md["hb_quality"] == "pessima"  # untouched
    assert md["hb_damage_state"] == "integra"  # added


@pytest.mark.asyncio
async def test_delete_rule_returns_204(client, char_id):
    r1 = await client.post(f"/characters/{char_id}/homebrew/templates/quality_wear/install")
    rule_id = r1.json()["id"]
    r2 = await client.delete(f"/characters/{char_id}/homebrew/rules/{rule_id}")
    assert r2.status_code == 204
    rules = (await client.get(f"/characters/{char_id}/homebrew/rules")).json()
    assert rules == []


@pytest.mark.asyncio
async def test_delete_rule_unknown_returns_404(client, char_id):
    r = await client.delete(f"/characters/{char_id}/homebrew/rules/99999")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_rule_clears_only_its_own_custom_conditions(
    client, char_id, test_session_factory,
):
    """#FN1: a rule's apply_condition writes custom:<slug> into char.conditions,
    a JSON blob OUTSIDE the relational graph — so deleting the rule cannot cascade
    it away. delete_rule must remove the custom:* entries this rule owns so they
    don't linger as orphans pointing at a deleted rule, while leaving standard
    conditions (poisoned/exhaustion) and OTHER rules' custom conditions intact."""
    from sqlalchemy import select as _select
    from sqlalchemy.orm.attributes import flag_modified

    from core.db.models import Character

    rsp = await client.post(
        f"/characters/{char_id}/homebrew/rules",
        json={
            "name": "Bleed", "description": "applies bleeding", "enabled": True,
            "dsl": {
                "version": 1, "subject": {"type": "character"},
                "triggers": [{
                    "event": "manual_trigger", "filters": [],
                    "effects": [{"action": "apply_condition", "key": "custom:bleeding"}],
                }],
            },
        },
    )
    assert rsp.status_code == 201, rsp.text
    rule_id = rsp.json()["id"]

    # Seed: a standard condition, this rule's custom condition, and an unrelated
    # custom condition owned by a different rule.
    async with test_session_factory() as s:
        ch = (await s.execute(_select(Character).where(Character.id == char_id))).scalar_one()
        ch.conditions = {
            "poisoned": True,
            "exhaustion": 2,
            "custom:bleeding": {"rule_id": rule_id, "params": {}},
            "custom:other": {"rule_id": 999999, "params": {}},
        }
        flag_modified(ch, "conditions")
        await s.commit()

    r = await client.delete(f"/characters/{char_id}/homebrew/rules/{rule_id}")
    assert r.status_code == 204

    async with test_session_factory() as s:
        ch = (await s.execute(_select(Character).where(Character.id == char_id))).scalar_one()
        conds = ch.conditions or {}
    assert "custom:bleeding" not in conds        # orphan removed
    assert conds.get("poisoned") is True         # standard condition intact
    assert conds.get("exhaustion") == 2          # standard condition intact
    assert "custom:other" in conds               # another rule's custom intact


@pytest.mark.asyncio
async def test_create_rule_from_scratch_returns_201(client, char_id):
    body = {
        "name": "My custom",
        "description": "Test",
        "dsl": {
            "version": 1,
            "subject": {"type": "character"},
            "triggers": [{
                "event": "manual_trigger", "filters": [],
                "effects": [{"action": "notify", "severity": "info", "message": "hi"}],
            }],
        },
        "enabled": True,
    }
    r = await client.post(f"/characters/{char_id}/homebrew/rules", json=body)
    assert r.status_code == 201
    payload = r.json()
    assert payload["name"] == "My custom"
    assert payload["version"] == 1
    assert payload["template_id"] is None


@pytest.mark.asyncio
async def test_create_rule_invalid_dsl_returns_422(client, char_id):
    body = {"name": "Bad", "dsl": {"version": 1}, "enabled": True}  # missing subject + triggers
    r = await client.post(f"/characters/{char_id}/homebrew/rules", json=body)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_create_rule_empty_name_returns_422(client, char_id):
    body = {
        "name": "",
        "dsl": {
            "version": 1,
            "subject": {"type": "character"},
            "triggers": [{"event": "manual_trigger", "filters": [], "effects": []}],
        },
        "enabled": True,
    }
    r = await client.post(f"/characters/{char_id}/homebrew/rules", json=body)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_update_rule_changes_name_and_description(client, char_id):
    r1 = await client.post(f"/characters/{char_id}/homebrew/templates/quality_wear/install")
    rule_id = r1.json()["id"]
    r2 = await client.patch(
        f"/characters/{char_id}/homebrew/rules/{rule_id}",
        json={"name": "Renamed", "description": "new"},
    )
    assert r2.status_code == 200
    body = r2.json()
    assert body["name"] == "Renamed"
    assert body["description"] == "new"
    # version should NOT bump when dsl is unchanged
    assert body["version"] == 1


@pytest.mark.asyncio
async def test_update_rule_bumps_version_when_dsl_changes(client, char_id):
    r1 = await client.post(f"/characters/{char_id}/homebrew/templates/quality_wear/install")
    rule_id = r1.json()["id"]
    new_dsl = {
        "version": 1,
        "subject": {"type": "character"},
        "triggers": [{"event": "manual_trigger", "filters": [], "effects": []}],
    }
    r2 = await client.patch(
        f"/characters/{char_id}/homebrew/rules/{rule_id}",
        json={"dsl": new_dsl},
    )
    assert r2.status_code == 200
    assert r2.json()["version"] == 2


@pytest.mark.asyncio
async def test_update_rule_invalid_dsl_returns_422(client, char_id):
    r1 = await client.post(f"/characters/{char_id}/homebrew/templates/quality_wear/install")
    rule_id = r1.json()["id"]
    r2 = await client.patch(
        f"/characters/{char_id}/homebrew/rules/{rule_id}",
        json={"dsl": {"version": 99}},
    )
    assert r2.status_code == 422


@pytest.mark.asyncio
async def test_toggle_enabled_off_then_on(client, char_id):
    r1 = await client.post(f"/characters/{char_id}/homebrew/templates/quality_wear/install")
    rule_id = r1.json()["id"]
    r2 = await client.post(
        f"/characters/{char_id}/homebrew/rules/{rule_id}/enable",
        json={"enabled": False},
    )
    assert r2.status_code == 200
    assert r2.json()["enabled"] is False
    r3 = await client.post(
        f"/characters/{char_id}/homebrew/rules/{rule_id}/enable",
        json={"enabled": True},
    )
    assert r3.json()["enabled"] is True


# ─── Homebrew resources: materialization on rule install/create ──────────────


def _resource_rule_body(
    *, name: str = "Luck Pool", key: str = "luck_points",
    res_name: str = "Luck Points", max_value: int = 3,
    restoration: str = "long_rest",
    event: str = "resource_changed", message: str = "Luck changed",
) -> dict:
    """Build a create_rule body with one ResourceDef + a trigger on `event`."""
    return {
        "name": name,
        "description": "Custom resource",
        "enabled": True,
        "dsl": {
            "version": 1,
            "subject": {"type": "character"},
            "resources": [{
                "key": key, "name": res_name, "max": max_value,
                "restoration_type": restoration,
            }],
            "triggers": [{
                "event": event, "filters": [],
                "effects": [{"action": "notify", "severity": "info", "message": message}],
            }],
        },
    }


@pytest.mark.asyncio
async def test_create_rule_materializes_resource(client, char_id):
    r = await client.post(
        f"/characters/{char_id}/homebrew/rules",
        json=_resource_rule_body(),
    )
    assert r.status_code == 201
    resources = (await client.get(f"/characters/{char_id}/homebrew/resources")).json()
    assert len(resources) == 1
    res = resources[0]
    assert res["key"] == "luck_points"
    assert res["name"] == "Luck Points"
    assert res["current"] == 3
    assert res["max"] == 3
    assert res["restoration_type"] == "long_rest"


@pytest.mark.asyncio
async def test_create_rule_duplicate_resource_key_returns_409(client, char_id):
    r1 = await client.post(
        f"/characters/{char_id}/homebrew/rules",
        json=_resource_rule_body(name="First"),
    )
    assert r1.status_code == 201
    r2 = await client.post(
        f"/characters/{char_id}/homebrew/rules",
        json=_resource_rule_body(name="Second"),
    )
    assert r2.status_code == 409
    assert "luck_points" in r2.json()["detail"]


@pytest.mark.asyncio
async def test_create_rule_with_multiple_resources_in_same_dsl(client, char_id):
    body = _resource_rule_body()
    body["dsl"]["resources"].append(
        {"key": "fate_points", "name": "Fate", "max": 2, "restoration_type": "short_rest"},
    )
    r = await client.post(f"/characters/{char_id}/homebrew/rules", json=body)
    assert r.status_code == 201
    resources = (await client.get(f"/characters/{char_id}/homebrew/resources")).json()
    assert {r["key"] for r in resources} == {"luck_points", "fate_points"}


@pytest.mark.asyncio
async def test_install_template_without_resources_does_not_create_any(client, char_id):
    # quality_wear has no resources — install should not create any HomebrewResource.
    r = await client.post(f"/characters/{char_id}/homebrew/templates/quality_wear/install")
    assert r.status_code == 201
    resources = (await client.get(f"/characters/{char_id}/homebrew/resources")).json()
    assert resources == []


@pytest.mark.asyncio
async def test_materialized_resource_persists_restoration_type_as_enum_name(
    client, char_id, test_session_factory,
):
    """#15 (verified false positive — regression guard): the raw column stores the
    enum NAME ('LONG_REST'), consistent with Ability and the engine.py heal-migration.

    The audit claimed _materialize_resources persisted the lowercase VALUE, but on
    SQLAlchemy 2.0.48 (the pinned version) a *valid* value-string is coerced to its
    member on write, so the NAME is already stored for all four members — including
    'manual' -> 'MANUAL', whose old pass-through bug only existed before MANUAL was an
    enum member. The API/ORM still surface the lowercase value, hence the raw-SQL read.
    This locks by-NAME storage so a future SQLAlchemy change (or an Enum values_callable)
    cannot silently regress it to value-storage.
    """
    from sqlalchemy import text

    body = _resource_rule_body()
    body["dsl"]["resources"] = [
        {"key": "rt_long", "name": "L", "max": 3, "restoration_type": "long_rest"},
        {"key": "rt_short", "name": "S", "max": 3, "restoration_type": "short_rest"},
        {"key": "rt_none", "name": "N", "max": 3, "restoration_type": "none"},
        {"key": "rt_manual", "name": "M", "max": 3, "restoration_type": "manual"},
    ]
    r = await client.post(f"/characters/{char_id}/homebrew/rules", json=body)
    assert r.status_code == 201, r.text

    async with test_session_factory() as session:
        rows = (await session.execute(text(
            "SELECT key, restoration_type FROM homebrew_resources "
            "WHERE character_id = :cid"
        ), {"cid": char_id})).all()
    stored = {key: rt for key, rt in rows}
    assert stored == {
        "rt_long": "LONG_REST",
        "rt_short": "SHORT_REST",
        "rt_none": "NONE",
        "rt_manual": "MANUAL",
    }


# ─── Homebrew resources: list + PATCH endpoints ──────────────────────────────


@pytest.mark.asyncio
async def test_list_resources_empty_initially(client, char_id):
    r = await client.get(f"/characters/{char_id}/homebrew/resources")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_list_resources_other_user_char_returns_403(client, test_session_factory):
    from core.db.models import Character
    async with test_session_factory() as s:
        other = Character(user_id=9999, name="Someone Else")
        s.add(other)
        await s.commit()
        await s.refresh(other)
        other_id = other.id
    r = await client.get(f"/characters/{other_id}/homebrew/resources")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_patch_resource_decrement_emits_resource_changed_notification(client, char_id):
    await client.post(
        f"/characters/{char_id}/homebrew/rules",
        json=_resource_rule_body(message="Luck spent"),
    )
    resources = (await client.get(f"/characters/{char_id}/homebrew/resources")).json()
    res_id = resources[0]["id"]

    r = await client.patch(
        f"/characters/{char_id}/homebrew/resources/{res_id}",
        json={"current": 2},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["current"] == 2
    notes = body.get("homebrew_notifications") or []
    assert any(n["message"] == "Luck spent" for n in notes)


@pytest.mark.asyncio
async def test_patch_resource_to_zero_fires_changed_and_depleted(client, char_id):
    # Two rules: one listens to resource_changed, one to resource_depleted.
    await client.post(
        f"/characters/{char_id}/homebrew/rules",
        json=_resource_rule_body(name="Listener A", message="changed-msg"),
    )
    body_b = {
        "name": "Listener B",
        "description": "Depleted listener",
        "enabled": True,
        "dsl": {
            "version": 1,
            "subject": {"type": "character"},
            "triggers": [{
                "event": "resource_depleted", "filters": [],
                "effects": [{"action": "notify", "severity": "warning", "message": "depleted-msg"}],
            }],
        },
    }
    await client.post(f"/characters/{char_id}/homebrew/rules", json=body_b)
    res_id = (await client.get(f"/characters/{char_id}/homebrew/resources")).json()[0]["id"]

    r = await client.patch(
        f"/characters/{char_id}/homebrew/resources/{res_id}",
        json={"current": 0},
    )
    assert r.status_code == 200
    messages = {n["message"] for n in (r.json().get("homebrew_notifications") or [])}
    assert "changed-msg" in messages
    assert "depleted-msg" in messages


@pytest.mark.asyncio
async def test_change_resource_action_reemits_changed_and_depleted(
    client, char_id, test_session_factory,
):
    """#1 regression: a rule-driven change_resource that drains a resource to 0
    must re-emit resource_changed AND resource_depleted — exactly like the manual
    PATCH — so cascade rules bound to those events fire for engine-driven
    mutations too (previously only the manual UI edit emitted them).

    Verified via CharacterHistory: notifications produced inside a *nested*
    re-emit are not threaded back into the top-level firing result (this mirrors
    execute_damage_character), but add_history entries are persisted by every
    dispatch invocation, so they are the reliable cascade signal here.
    """
    from sqlalchemy import select as _select

    from core.db.models import CharacterHistory

    # Spender owns luck_points (max=3) and drains it on manual_trigger.
    spender = {
        "name": "Spender", "description": "Drains luck", "enabled": True,
        "dsl": {
            "version": 1,
            "subject": {"type": "character"},
            "resources": [{"key": "luck_points", "name": "Luck", "max": 3,
                           "restoration_type": "long_rest"}],
            "triggers": [{
                "event": "manual_trigger", "filters": [],
                "effects": [{"action": "change_resource",
                             "key": "luck_points", "delta": -3}],
            }],
        },
    }
    rsp = await client.post(f"/characters/{char_id}/homebrew/rules", json=spender)
    assert rsp.status_code == 201, rsp.text
    spender_id = rsp.json()["id"]

    # Two cascade listeners, each writing a recognizable history entry.
    for nm, ev, desc in [
        ("Listener A", "resource_changed", "HB-CHANGED"),
        ("Listener B", "resource_depleted", "HB-DEPLETED"),
    ]:
        body = {
            "name": nm, "description": "listener", "enabled": True,
            "dsl": {
                "version": 1,
                "subject": {"type": "character"},
                "triggers": [{
                    "event": ev, "filters": [],
                    "effects": [{"action": "add_history", "description": desc}],
                }],
            },
        }
        assert (
            await client.post(f"/characters/{char_id}/homebrew/rules", json=body)
        ).status_code == 201

    # Fire the spender → luck 3 → 0 → cascade changed + depleted.
    r = await client.post(
        f"/characters/{char_id}/homebrew/manual-trigger/{spender_id}"
    )
    assert r.status_code == 200, r.text

    res = (await client.get(f"/characters/{char_id}/homebrew/resources")).json()
    assert res[0]["current"] == 0  # drained

    async with test_session_factory() as s:
        descriptions = (await s.execute(
            _select(CharacterHistory.description).where(
                CharacterHistory.character_id == char_id,
            )
        )).scalars().all()
    joined = "\n".join(d or "" for d in descriptions)
    assert "HB-CHANGED" in joined    # resource_changed cascade fired
    assert "HB-DEPLETED" in joined   # resource_depleted cascade fired


@pytest.mark.asyncio
async def test_damage_character_propagates_was_critical(
    client, char_id, test_session_factory,
):
    """#6: the `was_critical` toggle on damage_character must propagate into the
    re-emitted damage_taken (`was_critical_hit`) so cascade rules can filter on it.
    Before the fix the flag was hardcoded False and the listener never fired.
    """
    from sqlalchemy import select as _select

    from core.db.models import CharacterHistory

    dealer = {
        "name": "Critico", "description": "danno critico", "enabled": True,
        "dsl": {
            "version": 1, "subject": {"type": "character"},
            "triggers": [{
                "event": "manual_trigger", "filters": [],
                "effects": [{"action": "damage_character", "amount": 1,
                             "was_critical": True}],
            }],
        },
    }
    rsp = await client.post(f"/characters/{char_id}/homebrew/rules", json=dealer)
    assert rsp.status_code == 201, rsp.text
    dealer_id = rsp.json()["id"]

    listener = {
        "name": "Reazione al critico", "description": "listener", "enabled": True,
        "dsl": {
            "version": 1, "subject": {"type": "character"},
            "triggers": [{
                "event": "damage_taken",
                "filters": [{"path": "$event.was_critical_hit", "op": "eq", "value": True}],
                "effects": [{"action": "add_history", "description": "CRIT-REACTION"}],
            }],
        },
    }
    assert (
        await client.post(f"/characters/{char_id}/homebrew/rules", json=listener)
    ).status_code == 201

    r = await client.post(
        f"/characters/{char_id}/homebrew/manual-trigger/{dealer_id}"
    )
    assert r.status_code == 200, r.text

    async with test_session_factory() as s:
        descs = (await s.execute(
            _select(CharacterHistory.description).where(
                CharacterHistory.character_id == char_id,
            )
        )).scalars().all()
    # The cascade listener fired → was_critical_hit propagated as True.
    assert any("CRIT-REACTION" in (d or "") for d in descs)


@pytest.mark.asyncio
async def test_damage_character_reemits_gross_amount_not_net_of_temp_hp(
    client, char_id, test_session_factory,
):
    """#29: the re-emitted damage_taken.amount must be the GROSS damage dealt,
    consistent with hp.py (which passes body.value), NOT the residual left after
    temp-HP absorption. The actual HP lost stays derivable from
    current_hp_before/after, so no separate key is needed.
    """
    from sqlalchemy import select as _select

    from core.db.models import Character, CharacterHistory

    # 5 temp HP, 30/30 real HP.
    async with test_session_factory() as s:
        ch = (await s.execute(
            _select(Character).where(Character.id == char_id)
        )).scalar_one()
        ch.temp_hp = 5
        ch.current_hit_points = 30
        ch.hit_points = 30
        await s.commit()

    # Dealer: deal 8 on manual_trigger → 5 absorbed by temp HP, 3 to real HP.
    dealer = {
        "name": "Dealer", "description": "deals 8", "enabled": True,
        "dsl": {"version": 1, "subject": {"type": "character"},
                "triggers": [{"event": "manual_trigger", "filters": [],
                              "effects": [{"action": "damage_character", "amount": 8}]}]},
    }
    rsp = await client.post(f"/characters/{char_id}/homebrew/rules", json=dealer)
    assert rsp.status_code == 201, rsp.text
    dealer_id = rsp.json()["id"]

    # Listener records the amount it observed on the re-emitted damage_taken.
    listener = {
        "name": "Listener", "description": "records amount", "enabled": True,
        "dsl": {"version": 1, "subject": {"type": "character"},
                "triggers": [{"event": "damage_taken", "filters": [],
                              "effects": [{"action": "add_history",
                                           "description": "DT-AMOUNT=$event.amount"}]}]},
    }
    assert (
        await client.post(f"/characters/{char_id}/homebrew/rules", json=listener)
    ).status_code == 201

    r = await client.post(f"/characters/{char_id}/homebrew/manual-trigger/{dealer_id}")
    assert r.status_code == 200, r.text

    async with test_session_factory() as s:
        descs = (await s.execute(_select(CharacterHistory.description).where(
            CharacterHistory.character_id == char_id))).scalars().all()
    joined = "\n".join(d or "" for d in descs)
    # Gross damage (8), NOT the residual 3 left after the 5 temp HP were absorbed.
    assert "DT-AMOUNT=8" in joined


@pytest.mark.asyncio
async def test_patch_resource_already_at_zero_does_not_fire_events(client, char_id):
    # Create rule with max=0 → current=0; PATCH to 0 is a no-op (no events).
    await client.post(
        f"/characters/{char_id}/homebrew/rules",
        json=_resource_rule_body(max_value=0, message="should-not-fire"),
    )
    res_id = (await client.get(f"/characters/{char_id}/homebrew/resources")).json()[0]["id"]
    r = await client.patch(
        f"/characters/{char_id}/homebrew/resources/{res_id}",
        json={"current": 0},
    )
    assert r.status_code == 200
    # No events fired → field stays None (Optional).
    assert r.json().get("homebrew_notifications") in (None, [])


@pytest.mark.asyncio
async def test_patch_resource_clamps_above_max(client, char_id):
    await client.post(
        f"/characters/{char_id}/homebrew/rules",
        json=_resource_rule_body(),
    )
    res_id = (await client.get(f"/characters/{char_id}/homebrew/resources")).json()[0]["id"]
    r = await client.patch(
        f"/characters/{char_id}/homebrew/resources/{res_id}",
        json={"current": 999},
    )
    assert r.status_code == 200
    # Max is 3, current starts at 3 → clamp to 3 → no change → no events.
    assert r.json()["current"] == 3


@pytest.mark.asyncio
async def test_patch_resource_clamps_negative_to_zero(client, char_id):
    await client.post(
        f"/characters/{char_id}/homebrew/rules",
        json=_resource_rule_body(message="m"),
    )
    res_id = (await client.get(f"/characters/{char_id}/homebrew/resources")).json()[0]["id"]
    r = await client.patch(
        f"/characters/{char_id}/homebrew/resources/{res_id}",
        json={"current": -50},
    )
    assert r.status_code == 200
    assert r.json()["current"] == 0


@pytest.mark.asyncio
async def test_patch_resource_unknown_id_returns_404(client, char_id):
    r = await client.patch(
        f"/characters/{char_id}/homebrew/resources/99999",
        json={"current": 1},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_patch_resource_other_user_resource_returns_404(client, test_session_factory, char_id):
    """Even if a resource id exists, it must be unreachable from another character's URL."""
    from core.db.models import Character, HomebrewResource, HomebrewRule
    # Create another user with their own resource.
    async with test_session_factory() as s:
        other = Character(user_id=9999, name="Other")
        s.add(other)
        await s.commit()
        await s.refresh(other)
        # Other user's own rule + resource
        rule = HomebrewRule(
            character_id=other.id, name="x", description=None, enabled=True,
            dsl={"version": 1, "subject": {"type": "character"},
                 "triggers": [{"event": "manual_trigger", "filters": [], "effects": []}]},
            version=1, template_id=None,
            created_at="2026-01-01T00:00:00", updated_at="2026-01-01T00:00:00",
        )
        s.add(rule)
        await s.commit()
        await s.refresh(rule)
        res = HomebrewResource(
            rule_id=rule.id, character_id=other.id, key="luck_points",
            name="Luck", current=3, max=3, restoration_type="long_rest",
        )
        s.add(res)
        await s.commit()
        await s.refresh(res)
        other_resource_id = res.id

    # Using our own char_id URL but pointing at the other char's resource → 404.
    r = await client.patch(
        f"/characters/{char_id}/homebrew/resources/{other_resource_id}",
        json={"current": 1},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_patch_resource_wrong_owner_via_url_returns_403(client, test_session_factory):
    """PATCH where the URL's char_id is owned by another user must 403 at the char gate."""
    from core.db.models import Character
    async with test_session_factory() as s:
        other = Character(user_id=9999, name="Other")
        s.add(other)
        await s.commit()
        await s.refresh(other)
        other_id = other.id
    r = await client.patch(
        f"/characters/{other_id}/homebrew/resources/1",
        json={"current": 1},
    )
    assert r.status_code == 403


# ─── Homebrew resources: DELETE (orphan cleanup, #31) ────────────────────────


@pytest.mark.asyncio
async def test_delete_resource_returns_204_and_removes_it(client, char_id):
    """#31: DELETE removes a resource so the player can clean up orphans left by a
    DSL edit (materialization is additive and never removes rows)."""
    await client.post(f"/characters/{char_id}/homebrew/rules", json=_resource_rule_body())
    res_id = (await client.get(f"/characters/{char_id}/homebrew/resources")).json()[0]["id"]
    r = await client.delete(f"/characters/{char_id}/homebrew/resources/{res_id}")
    assert r.status_code == 204
    assert (await client.get(f"/characters/{char_id}/homebrew/resources")).json() == []


@pytest.mark.asyncio
async def test_delete_resource_frees_unique_key_for_another_rule(client, char_id):
    """#31: deleting an orphan resource frees the UNIQUE(character_id, key) slot so a
    different rule can (re)use that key without the 409 collision."""
    a = await client.post(f"/characters/{char_id}/homebrew/rules", json=_resource_rule_body(name="A"))
    assert a.status_code == 201
    res_id = (await client.get(f"/characters/{char_id}/homebrew/resources")).json()[0]["id"]
    d = await client.delete(f"/characters/{char_id}/homebrew/resources/{res_id}")
    assert d.status_code == 204
    # Same key, different rule — no longer collides now that the orphan is gone.
    b = await client.post(f"/characters/{char_id}/homebrew/rules", json=_resource_rule_body(name="B"))
    assert b.status_code == 201


@pytest.mark.asyncio
async def test_delete_resource_unknown_id_returns_404(client, char_id):
    r = await client.delete(f"/characters/{char_id}/homebrew/resources/99999")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_resource_other_user_resource_returns_404(client, test_session_factory, char_id):
    """A resource id that exists but belongs to another character must be unreachable
    from our character's URL → 404 (mirrors the PATCH ownership guard)."""
    from core.db.models import Character, HomebrewResource, HomebrewRule
    async with test_session_factory() as s:
        other = Character(user_id=9999, name="Other")
        s.add(other)
        await s.commit()
        await s.refresh(other)
        rule = HomebrewRule(
            character_id=other.id, name="x", description=None, enabled=True,
            dsl={"version": 1, "subject": {"type": "character"},
                 "triggers": [{"event": "manual_trigger", "filters": [], "effects": []}]},
            version=1, template_id=None,
            created_at="2026-01-01T00:00:00", updated_at="2026-01-01T00:00:00",
        )
        s.add(rule)
        await s.commit()
        await s.refresh(rule)
        res = HomebrewResource(
            rule_id=rule.id, character_id=other.id, key="luck_points",
            name="Luck", current=3, max=3, restoration_type="long_rest",
        )
        s.add(res)
        await s.commit()
        await s.refresh(res)
        other_resource_id = res.id
    r = await client.delete(f"/characters/{char_id}/homebrew/resources/{other_resource_id}")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_resource_wrong_owner_via_url_returns_403(client, test_session_factory):
    """DELETE where the URL's char_id is owned by another user must 403 at the char gate."""
    from core.db.models import Character
    async with test_session_factory() as s:
        other = Character(user_id=9999, name="Other")
        s.add(other)
        await s.commit()
        await s.refresh(other)
        other_id = other.id
    r = await client.delete(f"/characters/{other_id}/homebrew/resources/1")
    assert r.status_code == 403


# ─── Manual endpoints: turn-start + manual-trigger ───────────────────────────


@pytest.mark.asyncio
async def test_turn_start_fires_turn_started_event(client, char_id):
    """A rule with a `turn_started` trigger fires on POST /turn-start."""
    body = {
        "name": "Turn announcer",
        "description": "Notifies on turn start",
        "enabled": True,
        "dsl": {
            "version": 1,
            "subject": {"type": "character"},
            "triggers": [{
                "event": "turn_started", "filters": [],
                "effects": [{"action": "notify", "severity": "info", "message": "Your turn!"}],
            }],
        },
    }
    r1 = await client.post(f"/characters/{char_id}/homebrew/rules", json=body)
    assert r1.status_code == 201

    r2 = await client.post(f"/characters/{char_id}/homebrew/turn-start")
    assert r2.status_code == 200
    notes = r2.json()["notifications"]
    assert any(n["message"] == "Your turn!" for n in notes)


@pytest.mark.asyncio
async def test_turn_start_no_rule_no_notifications(client, char_id):
    """POST /turn-start with no rules returns empty notifications list."""
    r = await client.post(f"/characters/{char_id}/homebrew/turn-start")
    assert r.status_code == 200
    assert r.json() == {"notifications": []}


@pytest.mark.asyncio
async def test_turn_start_wrong_owner_returns_403(client, test_session_factory):
    """POST /turn-start for another user's character must return 403."""
    from core.db.models import Character
    async with test_session_factory() as s:
        other = Character(user_id=9999, name="Other")
        s.add(other)
        await s.commit()
        await s.refresh(other)
        other_id = other.id
    r = await client.post(f"/characters/{other_id}/homebrew/turn-start")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_manual_trigger_fires_event(client, char_id):
    """POST /manual-trigger/{rule_id} fires rules listening to manual_trigger."""
    body = {
        "name": "Manual rule",
        "description": "Fires on manual_trigger",
        "enabled": True,
        "dsl": {
            "version": 1,
            "subject": {"type": "character"},
            "triggers": [{
                "event": "manual_trigger", "filters": [],
                "effects": [{"action": "notify", "severity": "info", "message": "Manual fired"}],
            }],
        },
    }
    r1 = await client.post(f"/characters/{char_id}/homebrew/rules", json=body)
    assert r1.status_code == 201
    rule_id = r1.json()["id"]

    r2 = await client.post(f"/characters/{char_id}/homebrew/manual-trigger/{rule_id}")
    assert r2.status_code == 200
    notes = r2.json()["notifications"]
    assert any(n["message"] == "Manual fired" for n in notes)


@pytest.mark.asyncio
async def test_manual_trigger_only_fires_targeted_rule(client, char_id):
    """#19: POST /manual-trigger/{rule_id} must fire ONLY the targeted rule, not
    every enabled rule with a manual_trigger. A luck-style rule that drains a
    resource and has no $event.rule_id self-filter must NOT be spent when the user
    taps a *different* manual rule (the luck_points template omits that filter).
    """
    # Vulnerable rule: drains `luck` on manual_trigger, NO self-filter.
    luck = {
        "name": "Luck", "description": "drains luck", "enabled": True,
        "dsl": {
            "version": 1,
            "subject": {"type": "character"},
            "resources": [{"key": "luck", "name": "Luck", "max": 3,
                           "restoration_type": "long_rest"}],
            "triggers": [{
                "event": "manual_trigger", "filters": [],
                "effects": [{"action": "change_resource", "key": "luck", "delta": -1}],
            }],
        },
    }
    assert (
        await client.post(f"/characters/{char_id}/homebrew/rules", json=luck)
    ).status_code == 201

    # A different manual rule — the one the user actually taps.
    other = {
        "name": "Other", "description": "unrelated manual rule", "enabled": True,
        "dsl": {
            "version": 1,
            "subject": {"type": "character"},
            "triggers": [{
                "event": "manual_trigger", "filters": [],
                "effects": [{"action": "notify", "severity": "info", "message": "Other fired"}],
            }],
        },
    }
    r_other = await client.post(f"/characters/{char_id}/homebrew/rules", json=other)
    assert r_other.status_code == 201
    other_id = r_other.json()["id"]

    # Tap the OTHER rule's manual trigger.
    r = await client.post(f"/characters/{char_id}/homebrew/manual-trigger/{other_id}")
    assert r.status_code == 200, r.text

    # The targeted rule fired …
    assert any(n["rule_id"] == other_id for n in r.json()["notifications"])
    # … but the luck resource was NOT drained (only the targeted rule should fire).
    resources = (await client.get(f"/characters/{char_id}/homebrew/resources")).json()
    luck_res = next(x for x in resources if x["key"] == "luck")
    assert luck_res["current"] == 3


@pytest.mark.asyncio
async def test_manual_trigger_disabled_rule_returns_409(client, char_id):
    """POST /manual-trigger/{rule_id} on a disabled rule returns 409."""
    body = {
        "name": "Manual rule",
        "description": "Fires on manual_trigger",
        "enabled": True,
        "dsl": {
            "version": 1,
            "subject": {"type": "character"},
            "triggers": [{
                "event": "manual_trigger", "filters": [],
                "effects": [{"action": "notify", "severity": "info", "message": "should-not-fire"}],
            }],
        },
    }
    r1 = await client.post(f"/characters/{char_id}/homebrew/rules", json=body)
    rule_id = r1.json()["id"]
    # Toggle off
    r2 = await client.post(
        f"/characters/{char_id}/homebrew/rules/{rule_id}/enable",
        json={"enabled": False},
    )
    assert r2.status_code == 200
    r3 = await client.post(f"/characters/{char_id}/homebrew/manual-trigger/{rule_id}")
    assert r3.status_code == 409


@pytest.mark.asyncio
async def test_manual_trigger_missing_rule_returns_404(client, char_id):
    r = await client.post(f"/characters/{char_id}/homebrew/manual-trigger/99999")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_manual_trigger_wrong_owner_returns_403(client, test_session_factory):
    """POST /manual-trigger/{rule_id} on another user's character returns 403."""
    from core.db.models import Character, HomebrewRule
    async with test_session_factory() as s:
        other = Character(user_id=9999, name="Other")
        s.add(other)
        await s.commit()
        await s.refresh(other)
        rule = HomebrewRule(
            character_id=other.id, name="x", description=None, enabled=True,
            dsl={
                "version": 1,
                "subject": {"type": "character"},
                "triggers": [{"event": "manual_trigger", "filters": [], "effects": []}],
            },
            version=1, template_id=None,
            created_at="2026-01-01T00:00:00", updated_at="2026-01-01T00:00:00",
        )
        s.add(rule)
        await s.commit()
        await s.refresh(rule)
        other_id = other.id
        other_rule_id = rule.id

    r = await client.post(
        f"/characters/{other_id}/homebrew/manual-trigger/{other_rule_id}"
    )
    assert r.status_code == 403


# ─── Fase 3: resource lifecycle (auto-restore, undeclared rejection) ─────────


@pytest.mark.asyncio
async def test_rest_auto_restores_homebrew_resources_by_restoration_type(client, char_id):
    """#13/D3: a long rest restores long_rest AND short_rest homebrew resources;
    a short rest restores only short_rest ones; 'none' never auto-restores."""
    body = {
        "name": "Pools", "description": "rest pools", "enabled": True,
        "dsl": {
            "version": 1, "subject": {"type": "character"},
            "resources": [
                {"key": "luck", "name": "Luck", "max": 3, "restoration_type": "long_rest"},
                {"key": "ki", "name": "Ki", "max": 2, "restoration_type": "short_rest"},
                {"key": "fate", "name": "Fate", "max": 4, "restoration_type": "none"},
            ],
            "triggers": [{"event": "manual_trigger", "filters": [],
                          "effects": [{"action": "notify", "severity": "info", "message": "x"}]}],
        },
    }
    assert (await client.post(f"/characters/{char_id}/homebrew/rules", json=body)).status_code == 201

    resources = (await client.get(f"/characters/{char_id}/homebrew/resources")).json()
    ids = {r["key"]: r["id"] for r in resources}
    for key in ("luck", "ki", "fate"):
        await client.patch(
            f"/characters/{char_id}/homebrew/resources/{ids[key]}", json={"current": 0}
        )

    # Short rest → only 'ki' (short_rest) restored.
    assert (await client.post(
        f"/characters/{char_id}/rest", json={"rest_type": "short"}
    )).status_code == 200
    by_key = {r["key"]: r for r in (await client.get(f"/characters/{char_id}/homebrew/resources")).json()}
    assert by_key["ki"]["current"] == 2
    assert by_key["luck"]["current"] == 0
    assert by_key["fate"]["current"] == 0

    # Long rest → 'luck' (long_rest) and 'ki' (short_rest) restored; 'fate' (none) not.
    assert (await client.post(
        f"/characters/{char_id}/rest", json={"rest_type": "long"}
    )).status_code == 200
    by_key = {r["key"]: r for r in (await client.get(f"/characters/{char_id}/homebrew/resources")).json()}
    assert by_key["luck"]["current"] == 3
    assert by_key["ki"]["current"] == 2
    assert by_key["fate"]["current"] == 0


@pytest.mark.asyncio
async def test_create_rule_undeclared_resource_key_returns_422(client, char_id):
    """#14: a change_resource referencing a key that is neither declared in
    dsl['resources'] nor already owned is rejected with 422 (no silent placeholder)."""
    body = {
        "name": "Bad", "description": "uses undeclared key", "enabled": True,
        "dsl": {
            "version": 1, "subject": {"type": "character"},
            "triggers": [{
                "event": "manual_trigger", "filters": [],
                "effects": [{"action": "change_resource", "key": "ghost_points", "delta": -1}],
            }],
        },
    }
    r = await client.post(f"/characters/{char_id}/homebrew/rules", json=body)
    assert r.status_code == 422
    assert "ghost_points" in r.json()["detail"]


@pytest.mark.asyncio
async def test_item_created_after_install_gets_property_defaults(
    client, char_id, test_session_factory,
):
    """#32: an item acquired AFTER an item-scoped rule is installed still receives
    the rule's hb_<key> defaults (materialized on create)."""
    import json as _json

    from sqlalchemy import select as _select

    from core.db.models import Item

    assert (await client.post(
        f"/characters/{char_id}/homebrew/templates/quality_wear/install"
    )).status_code == 201

    # Weapon created AFTER the install.
    r = await client.post(
        f"/characters/{char_id}/items",
        json={"name": "Ascia", "item_type": "weapon", "quantity": 1},
    )
    assert r.status_code == 201, r.text

    async with test_session_factory() as s:
        item = (await s.execute(
            _select(Item).where(Item.character_id == char_id, Item.name == "Ascia")
        )).scalar_one()
        md = _json.loads(item.item_metadata or "{}")
    assert md.get("hb_quality") == "ordinaria"
    assert md.get("hb_damage_state") == "integra"
