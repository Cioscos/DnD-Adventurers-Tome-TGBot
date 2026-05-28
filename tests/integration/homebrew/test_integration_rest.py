"""Integration tests for long_rest_taken / short_rest_taken events."""
from __future__ import annotations

import pytest


def _notify_rule(event: str, message: str, name: str = "Test Rest Rule") -> dict:
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
