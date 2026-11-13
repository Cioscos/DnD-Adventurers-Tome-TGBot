"""I sei talenti 2014 che agivano con regole homebrew ora agiscono dal motore (PR 1 talenti, Task 4)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from api.services.catalog_migration import migrate_catalog
from core.db.models import Ability, AppMeta, HomebrewRule, RestorationType
from tests.integration.rules.test_2014_bard import _full, _roll_keys
from tests.integration.test_level_choices import _take, _to_level_4


async def _l4(client) -> dict:
    """Guerriero 2014 di livello 4 con la scelta ASI/talento in sospeso, letto per intero."""
    body = await _to_level_4(client)
    return {**await _full(client, body["id"]), "pending_choices": body["pending_choices"]}


async def _rules(client, cid) -> list[dict]:
    return (await client.get(f"/characters/{cid}/homebrew/rules")).json()


async def test_alert_adds_five_to_initiative(client):
    body = await _l4(client)
    out = await _take(client, body, "alert")
    assert out["initiative_bonus"] == body["initiative_bonus"] + 5
    assert await _rules(client, body["id"]) == []


async def test_tough_adds_two_hp_per_level(client):
    body = await _l4(client)
    out = await _take(client, body, "tough")
    assert out["computed"]["hp_max_effective"] == body["computed"]["hp_max_effective"] + 8
    await client.patch(f"/characters/{body['id']}/xp", json={"set": 6500})
    up = await _full(client, body["id"])
    assert up["computed"]["hp_max_effective"] - up["hit_points"] - up["hp_max_homebrew_modifier"] == 10


async def test_mobile_speed(client):
    body = await _l4(client)
    out = await _take(client, body, "mobile")
    assert out["computed"]["speed"] == body["computed"]["speed"] + 10


async def test_observant_passives(client):
    body = await _l4(client)
    out = await _take(client, body, "observant", ability="wisdom")
    for skill in ("perception", "investigation"):
        assert out["passives"][skill] == body["passives"][skill] + 5  # Saggezza 10 -> 11: modificatore invariato
    assert out["passives"]["insight"] == body["passives"]["insight"]
    assert await _rules(client, body["id"]) == []


async def test_war_caster_concentration_advantage(client):
    body = await _l4(client)
    await _take(client, body, "war_caster")
    r = await client.post(f"/characters/{body['id']}/concentration/save", json={"damage": 10, "dice": [3, 18]})
    assert r.status_code == 200, r.text
    assert r.json()["mode_applied"] == "advantage" and r.json()["die"] == 18


async def test_lucky_three_points_reroll(client):
    body = await _l4(client)
    out = await _take(client, body, "lucky")
    lucky = next(a for a in out["abilities"] if a["feature_key"] == "feat.lucky")
    assert (lucky["max_uses"], lucky["uses"], lucky["restoration_type"]) == (3, 3, "long_rest")
    assert "feat.lucky" in await _roll_keys(client, body["id"], "save", ability="wisdom")
    assert "feat.lucky" in await _roll_keys(client, body["id"], "skill", skill="athletics")


async def test_migration_drops_feat_rules_once(client, test_session_factory):
    body = await _l4(client)
    cid = body["id"]
    now = datetime.now(timezone.utc).isoformat()
    dsl = {"version": 1, "subject": {"type": "character"}, "triggers": [], "passive_modifiers": [
        {"when": {"path": "$character.id", "op": "gt", "value": 0}, "target": "character.initiative", "value": 5}]}
    async with test_session_factory() as s:
        s.add(HomebrewRule(character_id=cid, name="Allerta", enabled=True, dsl=dsl, version=1, template_id="feat:alert",
                           created_at=now, updated_at=now))
        s.add(Ability(character_id=cid, name="Allerta", is_passive=True, feature_key="feat.alert"))
        s.add(Ability(character_id=cid, name="Punti fortuna", feature_key="feat.lucky", max_uses=3, uses=2,
                      restoration_type=RestorationType.LONG_REST))
        meta = await s.get(AppMeta, "catalog_version")
        if meta is None:
            s.add(AppMeta(key="catalog_version", value="0"))
        else:
            meta.value = "0"
        await s.commit()

    await migrate_catalog(test_session_factory)
    out = await _full(client, cid)
    assert out["initiative_bonus"] == body["initiative_bonus"] + 5
    assert next(a for a in out["abilities"] if a["feature_key"] == "feat.lucky")["uses"] == 2
    async with test_session_factory() as s:
        left = (await s.execute(select(HomebrewRule).where(HomebrewRule.character_id == cid))).scalars().all()
    assert left == []

    async with test_session_factory() as s:
        (await s.get(AppMeta, "catalog_version")).value = "0"
        await s.commit()
    await migrate_catalog(test_session_factory)
    again = await _full(client, cid)
    assert again["initiative_bonus"] == out["initiative_bonus"]
