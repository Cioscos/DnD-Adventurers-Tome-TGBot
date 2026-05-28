"""Integration tests for lifecycle events fired by character routers.

Currently covers:
  - long_rest_taken / short_rest_taken (hp.py rest endpoint)
  - spell_cast (spell_slots.py PATCH endpoint)
  - ability_used (abilities.py PATCH endpoint)
"""
from __future__ import annotations

import pytest


def _notify_rule(event: str, message: str, name: str = "Test Lifecycle Rule") -> dict:
    """Build a HomebrewRule create body with a single notify trigger on `event`."""
    return {
        "name": name,
        "description": "Integration test rule",
        "enabled": True,
        "dsl": {
            "version": 1,
            "subject": {"type": "character"},
            "triggers": [
                {
                    "event": event,
                    "filters": [],
                    "effects": [
                        {"action": "notify", "severity": "info", "message": message}
                    ],
                }
            ],
        },
    }


@pytest.mark.asyncio
async def test_long_rest_fires_event(client, char_id):
    """Installing a rule on `long_rest_taken` → POST /rest long surfaces the notification."""
    r = await client.post(
        f"/characters/{char_id}/homebrew/rules",
        json=_notify_rule("long_rest_taken", "Rested long!", name="Long Rest Notice"),
    )
    assert r.status_code == 201

    r = await client.post(f"/characters/{char_id}/rest", json={"rest_type": "long"})
    assert r.status_code == 200
    body = r.json()
    notifs = body.get("homebrew_notifications")
    assert notifs is not None
    assert any("Rested long!" in n["message"] for n in notifs)
    n = next(n for n in notifs if "Rested long!" in n["message"])
    assert n["severity"] == "info"
    assert n["rule_id"] is not None
    assert n["rule_name"] == "Long Rest Notice"


@pytest.mark.asyncio
async def test_short_rest_fires_event(client, char_id):
    """Installing a rule on `short_rest_taken` → POST /rest short surfaces the notification."""
    r = await client.post(
        f"/characters/{char_id}/homebrew/rules",
        json=_notify_rule("short_rest_taken", "Rested short!", name="Short Rest Notice"),
    )
    assert r.status_code == 201

    r = await client.post(f"/characters/{char_id}/rest", json={"rest_type": "short"})
    assert r.status_code == 200
    body = r.json()
    notifs = body.get("homebrew_notifications")
    assert notifs is not None
    assert any("Rested short!" in n["message"] for n in notifs)
    n = next(n for n in notifs if "Rested short!" in n["message"])
    assert n["severity"] == "info"
    assert n["rule_id"] is not None
    assert n["rule_name"] == "Short Rest Notice"


@pytest.mark.asyncio
async def test_rest_no_rule_returns_no_notifications_field(client, char_id):
    """No rules installed → homebrew_notifications absent/None on response."""
    r = await client.post(f"/characters/{char_id}/rest", json={"rest_type": "long"})
    assert r.status_code == 200
    body = r.json()
    # The field is Optional[list]; either omitted or null when no rule fires.
    assert body.get("homebrew_notifications") is None


@pytest.mark.asyncio
async def test_long_rest_does_not_fire_short_rest_rule(client, char_id):
    """Cross-event isolation: long rest should not surface a short_rest_taken rule."""
    r = await client.post(
        f"/characters/{char_id}/homebrew/rules",
        json=_notify_rule("short_rest_taken", "Only on short!", name="Short Only"),
    )
    assert r.status_code == 201

    r = await client.post(f"/characters/{char_id}/rest", json={"rest_type": "long"})
    assert r.status_code == 200
    body = r.json()
    assert body.get("homebrew_notifications") is None


# ---------------------------------------------------------------------------
# spell_cast (spell_slots.update_spell_slot)
# ---------------------------------------------------------------------------

async def _create_spell_slot(client, char_id: int, level: int = 1, total: int = 3, used: int = 0) -> int:
    r = await client.post(
        f"/characters/{char_id}/spell_slots",
        json={"level": level, "total": total, "used": used},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


@pytest.mark.asyncio
async def test_spell_cast_fires_event(client, char_id):
    """PATCH spell_slot with incremented `used` → spell_cast rule fires and notifies."""
    r = await client.post(
        f"/characters/{char_id}/homebrew/rules",
        json=_notify_rule("spell_cast", "Spell consumed!", name="Spell Cast Notice"),
    )
    assert r.status_code == 201

    slot_id = await _create_spell_slot(client, char_id, level=1, total=3, used=0)

    r = await client.patch(
        f"/characters/{char_id}/spell_slots/{slot_id}",
        json={"used": 1},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["used"] == 1
    assert body["available"] == 2

    notifs = body.get("homebrew_notifications") or []
    assert any("Spell consumed!" in n["message"] for n in notifs), notifs
    n = next(n for n in notifs if "Spell consumed!" in n["message"])
    assert n["severity"] == "info"
    assert n["rule_id"] is not None
    assert n["rule_name"] == "Spell Cast Notice"


@pytest.mark.asyncio
async def test_spell_cast_no_event_when_used_unchanged(client, char_id):
    """PATCH that doesn't increment `used` (no-op or refund) must NOT fire spell_cast."""
    r = await client.post(
        f"/characters/{char_id}/homebrew/rules",
        json=_notify_rule("spell_cast", "Should not fire!", name="Should Not Fire"),
    )
    assert r.status_code == 201

    # Start with `used=2` so we can test both no-op and refund paths.
    slot_id = await _create_spell_slot(client, char_id, level=1, total=3, used=2)

    # No-op PATCH: only update `total`, leave `used` alone.
    r = await client.patch(
        f"/characters/{char_id}/spell_slots/{slot_id}",
        json={"total": 4},
    )
    assert r.status_code == 200, r.text
    assert r.json().get("homebrew_notifications") is None

    # Refund: decrement `used` from 2 → 1. spell_cast must not fire.
    r = await client.patch(
        f"/characters/{char_id}/spell_slots/{slot_id}",
        json={"used": 1},
    )
    assert r.status_code == 200, r.text
    assert r.json().get("homebrew_notifications") is None


# ---------------------------------------------------------------------------
# ability_used (abilities.update_ability)
# ---------------------------------------------------------------------------

async def _create_ability(
    client,
    char_id: int,
    name: str = "Second Wind",
    max_uses: int = 1,
    uses: int = 1,
) -> int:
    r = await client.post(
        f"/characters/{char_id}/abilities",
        json={
            "name": name,
            "description": "Test ability",
            "max_uses": max_uses,
            "uses": uses,
            "is_active": True,
            "restoration_type": "short_rest",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


@pytest.mark.asyncio
async def test_ability_used_fires_event(client, char_id):
    """PATCH ability with decremented `uses` → ability_used rule fires and notifies."""
    r = await client.post(
        f"/characters/{char_id}/homebrew/rules",
        json=_notify_rule("ability_used", "Ability spent!", name="Ability Used Notice"),
    )
    assert r.status_code == 201

    ability_id = await _create_ability(client, char_id, max_uses=3, uses=3)

    r = await client.patch(
        f"/characters/{char_id}/abilities/{ability_id}",
        json={"uses": 2},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["uses"] == 2
    assert body["max_uses"] == 3

    notifs = body.get("homebrew_notifications") or []
    assert any("Ability spent!" in n["message"] for n in notifs), notifs
    n = next(n for n in notifs if "Ability spent!" in n["message"])
    assert n["severity"] == "info"
    assert n["rule_id"] is not None
    assert n["rule_name"] == "Ability Used Notice"


@pytest.mark.asyncio
async def test_ability_used_no_event_when_uses_unchanged(client, char_id):
    """PATCH that doesn't decrement `uses` (no-op, restore, or max-only) must NOT fire."""
    r = await client.post(
        f"/characters/{char_id}/homebrew/rules",
        json=_notify_rule("ability_used", "Should not fire!", name="Should Not Fire"),
    )
    assert r.status_code == 201

    # Start with uses=1 / max_uses=3 so we can test no-op, restore, and max-only.
    ability_id = await _create_ability(client, char_id, max_uses=3, uses=1)

    # 1) max-only PATCH: change max_uses, leave uses alone.
    r = await client.patch(
        f"/characters/{char_id}/abilities/{ability_id}",
        json={"max_uses": 4},
    )
    assert r.status_code == 200, r.text
    assert r.json().get("homebrew_notifications") is None

    # 2) No-op PATCH on uses: set uses to its current value (1 → 1).
    r = await client.patch(
        f"/characters/{char_id}/abilities/{ability_id}",
        json={"uses": 1},
    )
    assert r.status_code == 200, r.text
    assert r.json().get("homebrew_notifications") is None

    # 3) Restore: increment uses from 1 → 3 (e.g. after a rest). Must not fire.
    r = await client.patch(
        f"/characters/{char_id}/abilities/{ability_id}",
        json={"uses": 3},
    )
    assert r.status_code == 200, r.text
    assert r.json().get("homebrew_notifications") is None
