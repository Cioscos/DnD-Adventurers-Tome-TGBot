"""Integration tests for the ``level_up`` event fired by ``classes.update_class``.

Covers:
  - level_up fires on a strict level INCREASE (notify + apply_modifier_once)
  - no event when level is unchanged (no-op PATCH or other-field PATCH)
  - no event on level DECREASE (semantic-correct interpretation: we don't fire
    level_up on demotions because the canonical effect — apply_modifier_once
    granting +HP per level — would be asymmetric and incorrect on level-down).
    This deviates from the plan literal (`new_level != old_level`); see the
    inline note in ``api/routers/classes.py::update_class``.
"""
from __future__ import annotations

import pytest

from tests.integration.homebrew.conftest import notify_rule as _notify_rule


async def _create_class(
    client,
    char_id: int,
    *,
    class_name: str = "fighter",
    level: int = 1,
    hit_die: int = 10,
) -> int:
    """POST a class to the character and return the created CharacterClass id."""
    r = await client.post(
        f"/characters/{char_id}/classes",
        json={"class_name": class_name, "level": level, "hit_die": hit_die},
    )
    assert r.status_code == 201, r.text
    classes = r.json()["classes"]
    created = next(c for c in classes if c["class_name"] == class_name)
    return created["id"]


@pytest.mark.asyncio
async def test_level_up_fires_event(client, char_id):
    """PATCH class level 1 → 2 surfaces the notify message on the response."""
    r = await client.post(
        f"/characters/{char_id}/homebrew/rules",
        json=_notify_rule("level_up", "Level up!", name="Level Up Notice"),
    )
    assert r.status_code == 201

    class_id = await _create_class(client, char_id, class_name="fighter", level=1)

    r = await client.patch(
        f"/characters/{char_id}/classes/{class_id}",
        json={"level": 2},
    )
    assert r.status_code == 200, r.text
    body = r.json()

    # Mutation actually applied
    patched = next(c for c in body["classes"] if c["id"] == class_id)
    assert patched["level"] == 2

    notifs = body.get("homebrew_notifications") or []
    assert any("Level up!" in n["message"] for n in notifs), notifs
    n = next(n for n in notifs if "Level up!" in n["message"])
    assert n["severity"] == "info"
    assert n["rule_id"] is not None
    assert n["rule_name"] == "Level Up Notice"


@pytest.mark.asyncio
async def test_level_up_apply_modifier_once_increments_hp_max(client, char_id):
    """Plan's example test — apply_modifier_once on level_up grants +2 max HP.

    Confirms that the dispatcher's preload of ``classes`` makes
    ``char.total_level`` accurate POST-update, and that the action effect lands
    in the response body's ``hit_points`` value.
    """
    r = await client.post(
        f"/characters/{char_id}/homebrew/rules",
        json={
            "name": "Robusto",
            "description": "+2 PF per livello",
            "enabled": True,
            "dsl": {
                "version": 1,
                "subject": {"type": "character"},
                "triggers": [
                    {
                        "event": "level_up",
                        "filters": [],
                        "effects": [
                            {
                                "action": "apply_modifier_once",
                                "target": "character.hit_points_max",
                                "delta": 2,
                                "label": "+2 PF per livello",
                            }
                        ],
                    }
                ],
            },
        },
    )
    assert r.status_code == 201, r.text

    class_id = await _create_class(client, char_id, class_name="fighter", level=1)

    # Snapshot HP max pre-update so we can assert the +2 delta deterministically.
    r = await client.get(f"/characters/{char_id}")
    assert r.status_code == 200
    hp_before = r.json()["hit_points"]

    r = await client.patch(
        f"/characters/{char_id}/classes/{class_id}",
        json={"level": 2},
    )
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["hit_points"] == hp_before + 2, body


@pytest.mark.asyncio
async def test_no_event_when_level_unchanged(client, char_id):
    """Same-value PATCH on level (no-op) must NOT fire level_up."""
    r = await client.post(
        f"/characters/{char_id}/homebrew/rules",
        json=_notify_rule("level_up", "Should not fire!", name="Level Up NoFire"),
    )
    assert r.status_code == 201

    class_id = await _create_class(client, char_id, class_name="fighter", level=2)

    # 1) Same-value PATCH (2 → 2) — must not fire.
    r = await client.patch(
        f"/characters/{char_id}/classes/{class_id}",
        json={"level": 2},
    )
    assert r.status_code == 200, r.text
    assert r.json().get("homebrew_notifications") is None

    # 2) PATCH that doesn't touch `level` at all (e.g. subclass rename).
    r = await client.patch(
        f"/characters/{char_id}/classes/{class_id}",
        json={"subclass": "Champion"},
    )
    assert r.status_code == 200, r.text
    assert r.json().get("homebrew_notifications") is None


@pytest.mark.asyncio
async def test_level_decrease_does_not_fire_level_up(client, char_id):
    """Level DOWN must NOT fire level_up (semantic-correct deviation from plan).

    See the inline rationale in ``api/routers/classes.py::update_class``: firing
    level_up on a demotion would incorrectly trigger asymmetric effects such as
    the canonical apply_modifier_once +HP-per-level (which would *grant* extra
    HP on a level loss). If we later need a symmetric event, we will introduce
    ``level_down`` explicitly.
    """
    r = await client.post(
        f"/characters/{char_id}/homebrew/rules",
        json=_notify_rule("level_up", "Should not fire (down)!", name="Level Down NoFire"),
    )
    assert r.status_code == 201

    class_id = await _create_class(client, char_id, class_name="fighter", level=3)

    # Level DOWN: 3 → 2.
    r = await client.patch(
        f"/characters/{char_id}/classes/{class_id}",
        json={"level": 2},
    )
    assert r.status_code == 200, r.text
    patched = next(c for c in r.json()["classes"] if c["id"] == class_id)
    assert patched["level"] == 2
    assert r.json().get("homebrew_notifications") is None
