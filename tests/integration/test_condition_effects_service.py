"""Servizio effetti condizioni: coerenza con la mappa `conditions`."""
from __future__ import annotations

from api.services.condition_effects import ExpirySpec, SaveSpec, effects_for_character, upsert_effect
from api.services.homebrew.actions import execute_remove_condition
from core.db.models import Character


async def _char(client) -> int:
    r = await client.post("/characters", json={"name": "Eff"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_player_duration_creates_owner_start_effect(client):
    cid = await _char(client)
    await client.patch(f"/characters/{cid}/conditions",
                       json={"conditions": {"poisoned": True}, "durations": {"poisoned": 2}})
    eff = (await client.get(f"/characters/{cid}")).json()["condition_effects"][0]
    assert (eff["expiry_anchor"], eff["expiry_edge"], eff["expiry_count"]) == ("owner", "start", 2)


async def test_toggle_off_removes_effect(client):
    cid = await _char(client)
    await client.patch(f"/characters/{cid}/conditions",
                       json={"conditions": {"poisoned": True}, "durations": {"poisoned": 2}})
    await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"poisoned": False}})
    assert (await client.get(f"/characters/{cid}")).json()["condition_effects"] == []


async def test_homebrew_removal_removes_effect(client, test_session_factory):
    cid = await _char(client)
    async with test_session_factory() as s:
        char = await s.get(Character, cid)
        char.conditions = {"custom:bleeding": {"rule_id": 1, "params": {}}}
        await upsert_effect(s, ("character", cid), "custom:bleeding",
                            expiry=ExpirySpec("owner", "start", 3))
        await execute_remove_condition({"key": "custom:bleeding"}, None, None, s, char)
        assert await effects_for_character(s, cid) == []


async def test_player_duration_does_not_override_gm_effect(client, test_session_factory):
    cid = await _char(client)
    await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"poisoned": True}})
    async with test_session_factory() as s:
        await upsert_effect(s, ("character", cid), "poisoned",
                            expiry=ExpirySpec("source", "end", 3),
                            save=SaveSpec("constitution", 13, "end"), applied_by_gm=True)
        await s.commit()
    await client.patch(f"/characters/{cid}/conditions",
                       json={"conditions": {"poisoned": True}, "durations": {"poisoned": 5}})
    eff = (await client.get(f"/characters/{cid}")).json()["condition_effects"][0]
    assert (eff["expiry_anchor"], eff["expiry_count"], eff["save_ability"], eff["save_dc"]) == (
        "source", 3, "constitution", 13)
