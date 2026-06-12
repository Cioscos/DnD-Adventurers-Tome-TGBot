"""PATCH /characters/{id}/death_saves (manual actions) + POST /characters/{id}/revive.

Manual death-state transitions driven from the UI (the dice-roll path lives in
``test_death_save_roll.py``):

- ``SUCCESS`` x3 ⇒ stable; ``FAILURE`` x3 ⇒ dead.
- ``STABILIZE`` marks the character stable; HP stay at 0 (RAW: stabilizing is
  not healing — the creature remains unconscious until actually healed).
- ``RESET`` clears the tracker.
- Damage interplay (RAW): dropping from positive HP to 0 starts a fresh dying
  state (any stale ``stable`` flag is cleared); damage taken while stable at
  0 HP makes the creature dying again with a fresh tracker (old failures from
  before the stabilization do not carry over).
- Once dead the endpoint is inert (no further mutation); only ``/revive`` brings
  the character back, at 1 HP, with a cleared tracker. ``/revive`` is a no-op on a
  living character.
"""
from __future__ import annotations


async def _create_character(client) -> int:
    r = await client.post("/characters", json={"name": "DS Test"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _action(client, cid: int, action: str):
    r = await client.patch(f"/characters/{cid}/death_saves", json={"action": action})
    assert r.status_code == 200, r.text
    return r.json()


async def test_success_increments_then_stabilises_at_three(client):
    cid = await _create_character(client)
    assert (await _action(client, cid, "success"))["death_saves"]["successes"] == 1
    await _action(client, cid, "success")
    body = await _action(client, cid, "success")
    assert body["death_saves"]["successes"] == 3
    assert body["death_saves"]["stable"] is True


async def test_three_failures_kill(client):
    cid = await _create_character(client)
    await _action(client, cid, "failure")
    await _action(client, cid, "failure")
    body = await _action(client, cid, "failure")
    assert body["death_saves"]["failures"] == 3
    assert body["is_dead"] is True


async def test_stabilize_keeps_hp_at_zero(client):
    cid = await _create_character(client)
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": 20})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 20})
    # Porta a 0 senza sforamento massiccio (20 esatti: overflow 0 < max 20).
    await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 20})
    body = await _action(client, cid, "stabilize")
    assert body["death_saves"]["stable"] is True
    assert body["current_hit_points"] == 0  # RAW: stabilizzare non cura
    assert body["is_dead"] is False


async def test_drop_to_zero_clears_stale_stable(client):
    """Scendere da HP positivi a 0 inizia sempre una condizione di morente
    fresca: un flag ``stable`` residuo (es. dato legacy) non deve sopravvivere."""
    cid = await _create_character(client)
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": 20})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 20})
    # stable=True con HP positivi (le azioni manuali non richiedono 0 HP).
    for _ in range(3):
        await _action(client, cid, "success")
    body = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 20})
    ds = body.json()["death_saves"]
    assert ds == {"successes": 0, "failures": 0, "stable": False}


async def test_damage_while_stable_at_zero_restarts_dying_fresh(client):
    """Danno a una creatura stabile a 0 HP: torna morente con tracker fresco —
    i fallimenti accumulati prima della stabilizzazione non si sommano."""
    cid = await _create_character(client)
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": 20})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 20})
    await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 20})
    await _action(client, cid, "failure")
    await _action(client, cid, "failure")          # 2 fallimenti, poi stabilizzato
    await _action(client, cid, "stabilize")
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 5})
    body = r.json()
    ds = body["death_saves"]
    assert ds["stable"] is False
    assert ds["failures"] == 1                     # fresco: NON 3 (= morte)
    assert body["is_dead"] is False


async def test_reset_clears_tracker(client):
    cid = await _create_character(client)
    await _action(client, cid, "success")
    await _action(client, cid, "failure")
    body = await _action(client, cid, "reset")
    ds = body["death_saves"]
    assert ds["successes"] == 0 and ds["failures"] == 0 and ds["stable"] is False


async def test_dead_character_ignores_further_actions(client):
    cid = await _create_character(client)
    for _ in range(3):
        await _action(client, cid, "failure")  # 3 failures ⇒ dead
    body = await _action(client, cid, "success")  # inert once dead
    assert body["is_dead"] is True
    assert body["death_saves"]["failures"] == 3
    assert body["death_saves"]["successes"] == 0


async def test_revive_brings_dead_back_with_one_hp(client):
    cid = await _create_character(client)
    for _ in range(3):
        await _action(client, cid, "failure")
    r = await client.post(f"/characters/{cid}/revive")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["is_dead"] is False
    assert body["current_hit_points"] == 1
    ds = body["death_saves"]
    assert ds["successes"] == 0 and ds["failures"] == 0 and ds["stable"] is False


async def test_revive_is_noop_when_alive(client):
    cid = await _create_character(client)
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": 20})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 10})
    r = await client.post(f"/characters/{cid}/revive")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["is_dead"] is False
    assert body["current_hit_points"] == 10  # unchanged — no forced 1 HP
