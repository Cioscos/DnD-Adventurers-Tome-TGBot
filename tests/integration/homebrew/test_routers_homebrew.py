"""Integration tests on the homebrew router via httpx AsyncClient."""
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
