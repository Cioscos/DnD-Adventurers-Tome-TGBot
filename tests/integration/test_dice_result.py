"""POST /characters/{id}/dice/result — record a client-rolled dice result.

The server does NOT roll: the FE rolls (or the 3D physics engine reports faces)
and submits the values. The endpoint therefore validates each value against its
die range, computes the displayed total (client override else ``sum + modifier``),
infers a notation when one is not supplied, optionally consumes the heroic
inspiration token (409 if absent), and appends to the capped roll history.

Contract: the response is a ``DiceRollResult`` (notation / rolls / total) and the
request body is ``DiceResultRequest`` === the FE ``DiceResultRequestBody``.
"""
from __future__ import annotations


async def _create_character(client) -> int:
    r = await client.post("/characters", json={"name": "Roller"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _grant_inspiration(client, cid: int) -> None:
    r = await client.patch(f"/characters/{cid}/inspiration", json={"heroic_inspiration": True})
    assert r.status_code == 200, r.text


async def test_simple_roll_sums_and_infers_notation(client):
    cid = await _create_character(client)
    r = await client.post(
        f"/characters/{cid}/dice/result",
        json={"rolls": [{"kind": "d20", "value": 14}], "modifier": 3},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["rolls"] == [14]
    assert body["total"] == 17           # 14 + 3
    assert body["notation"] == "d20+3"   # inferred: single die + positive modifier


async def test_negative_modifier_notation(client):
    cid = await _create_character(client)
    r = await client.post(
        f"/characters/{cid}/dice/result",
        json={"rolls": [{"kind": "d20", "value": 10}], "modifier": -2},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 8
    assert body["notation"] == "d20-2"


async def test_repeated_die_notation_infers_count(client):
    cid = await _create_character(client)
    r = await client.post(
        f"/characters/{cid}/dice/result",
        json={"rolls": [{"kind": "d6", "value": 3}, {"kind": "d6", "value": 5}]},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 8            # sum, no modifier
    assert body["notation"] == "2d6"     # n > 1 → "2d6"


async def test_total_override_and_explicit_notation_keep_high(client):
    """4d6kh3 stat roll: total is the kept-dice sum (client override), not all dice."""
    cid = await _create_character(client)
    r = await client.post(
        f"/characters/{cid}/dice/result",
        json={
            "rolls": [{"kind": "d6", "value": 6}, {"kind": "d6", "value": 5},
                      {"kind": "d6", "value": 4}, {"kind": "d6", "value": 1}],
            "notation": "4d6kh3",
            "total": 15,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["rolls"] == [6, 5, 4, 1]
    assert body["total"] == 15           # client override, NOT 16 (sum of all four)
    assert body["notation"] == "4d6kh3"


async def test_value_out_of_range_is_400(client):
    cid = await _create_character(client)
    r = await client.post(
        f"/characters/{cid}/dice/result",
        json={"rolls": [{"kind": "d6", "value": 7}]},  # 7 > 6
    )
    assert r.status_code == 400, r.text


async def test_with_inspiration_consumes_the_token(client):
    cid = await _create_character(client)
    await _grant_inspiration(client, cid)
    r = await client.post(
        f"/characters/{cid}/dice/result",
        json={"rolls": [{"kind": "d20", "value": 10}], "with_inspiration": True},
    )
    assert r.status_code == 200, r.text
    g = await client.get(f"/characters/{cid}")
    assert g.json()["heroic_inspiration"] is False


async def test_with_inspiration_without_token_is_409(client):
    cid = await _create_character(client)
    r = await client.post(
        f"/characters/{cid}/dice/result",
        json={"rolls": [{"kind": "d20", "value": 10}], "with_inspiration": True},
    )
    assert r.status_code == 409, r.text


async def test_history_records_roll_then_clears(client):
    cid = await _create_character(client)
    r = await client.post(
        f"/characters/{cid}/dice/result",
        json={"rolls": [{"kind": "d20", "value": 18}], "label": "Iniziativa", "source": "init"},
    )
    assert r.status_code == 200, r.text

    h = await client.get(f"/characters/{cid}/dice/history")
    assert h.status_code == 200, h.text
    history = h.json()
    assert len(history) == 1
    entry = history[0]
    assert entry["notation"] == "d20"
    assert entry["total"] == 18
    assert entry["source"] == "init"
    assert entry["label"] == "Iniziativa"

    d = await client.delete(f"/characters/{cid}/dice/history")
    assert d.status_code == 204, d.text
    h2 = await client.get(f"/characters/{cid}/dice/history")
    assert h2.json() == []
