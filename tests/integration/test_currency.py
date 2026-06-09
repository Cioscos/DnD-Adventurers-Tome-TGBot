"""Integration tests for the currency endpoints (GET / PATCH / convert).

Pins the D&D 5e coin economy enforced by ``core.db.models.Currency``:
conversion rates to copper are cp=1, sp=10, ep=50, gp=100, pp=1000. The
convert endpoint rejects bad input (unknown coin, same source/target,
non-positive amount, insufficient funds) and, when converting "up" into a
larger coin, returns the floor in the target plus the remainder as copper so
no value is ever silently destroyed.
"""
from __future__ import annotations

import pytest


async def _create_character(client) -> int:
    r = await client.post("/characters", json={"name": "Coin Purse"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


@pytest.mark.asyncio
async def test_get_currency_creates_empty_wallet(client):
    char_id = await _create_character(client)

    r = await client.get(f"/characters/{char_id}/currency")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "id" in body
    assert {body["copper"], body["silver"], body["electrum"], body["gold"], body["platinum"]} == {0}


@pytest.mark.asyncio
async def test_patch_sets_coins(client):
    char_id = await _create_character(client)

    r = await client.patch(
        f"/characters/{char_id}/currency", json={"gold": 10, "silver": 5}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["gold"] == 10
    assert body["silver"] == 5
    assert body["copper"] == 0  # untouched fields stay at default


@pytest.mark.asyncio
async def test_patch_clamps_negative_to_zero(client):
    char_id = await _create_character(client)

    r = await client.patch(f"/characters/{char_id}/currency", json={"copper": -50})
    assert r.status_code == 200, r.text
    assert r.json()["copper"] == 0


@pytest.mark.asyncio
async def test_convert_gold_to_silver_uses_official_rate(client):
    """1 gp = 10 sp."""
    char_id = await _create_character(client)
    await client.patch(f"/characters/{char_id}/currency", json={"gold": 2})

    r = await client.post(
        f"/characters/{char_id}/currency/convert",
        json={"source": "gold", "target": "silver", "amount": 1},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["gold"] == 1
    assert body["silver"] == 10


@pytest.mark.asyncio
async def test_convert_up_returns_remainder_as_copper(client):
    """5 sp (=50 cp) → gold floors to 0 gp, the 50 cp remainder lands in copper."""
    char_id = await _create_character(client)
    await client.patch(f"/characters/{char_id}/currency", json={"silver": 5})

    r = await client.post(
        f"/characters/{char_id}/currency/convert",
        json={"source": "silver", "target": "gold", "amount": 5},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["silver"] == 0
    assert body["gold"] == 0
    assert body["copper"] == 50


@pytest.mark.asyncio
async def test_convert_insufficient_funds_is_rejected(client):
    char_id = await _create_character(client)
    # wallet is empty
    r = await client.post(
        f"/characters/{char_id}/currency/convert",
        json={"source": "gold", "target": "silver", "amount": 1},
    )
    assert r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_convert_rejects_same_source_and_target(client):
    char_id = await _create_character(client)
    r = await client.post(
        f"/characters/{char_id}/currency/convert",
        json={"source": "gold", "target": "gold", "amount": 1},
    )
    assert r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_convert_rejects_non_positive_amount(client):
    char_id = await _create_character(client)
    r = await client.post(
        f"/characters/{char_id}/currency/convert",
        json={"source": "gold", "target": "silver", "amount": 0},
    )
    assert r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_convert_rejects_unknown_coin(client):
    char_id = await _create_character(client)
    r = await client.post(
        f"/characters/{char_id}/currency/convert",
        json={"source": "doubloons", "target": "gold", "amount": 1},
    )
    assert r.status_code == 400, r.text
