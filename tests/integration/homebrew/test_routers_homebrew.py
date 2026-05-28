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
