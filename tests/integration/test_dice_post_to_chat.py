"""POST /characters/{id}/dice/post-to-chat — routers/dice.py.

Relays a formatted dice result to the user's private Telegram chat via the Bot
API (the authenticated replacement for ``Telegram.WebApp.sendData()``). This is
the only dice endpoint still uncovered (result/history were already mapped).

The endpoint talks to ``api.telegram.org`` through the shared
``api.services.telegram_notify`` service. We never hit the network: the fake
transport from ``_telegram_stub`` is monkeypatched into the service so we can
assert the exact ``sendMessage`` payload (chat_id = the authenticated user,
Markdown text), plus the guard rails:
  - ownership is checked *before* the token (404 missing / 403 foreign);
  - no ``BOT_TOKEN`` configured → 503;
  - Telegram returning a non-2xx → 502.
"""
from __future__ import annotations

from core.db.models import Character
from tests.integration._telegram_stub import clear_bot_token, install_fake_telegram

TEST_USER_ID = 1234  # mirrors tests/integration/conftest.py


async def _make_char(client) -> int:
    r = await client.post("/characters", json={"name": "Roller"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_unknown_character_is_404(client):
    r = await client.post(
        "/characters/999999/dice/post-to-chat",
        json={"notation": "d20", "rolls": [12], "total": 12},
    )
    assert r.status_code == 404, r.text


async def test_other_owner_is_403_before_token_check(client, test_session_factory):
    # Ownership is verified before BOT_TOKEN, so this is 403 even with no token.
    async with test_session_factory() as s:
        other = Character(user_id=TEST_USER_ID + 1, name="NotMine")
        s.add(other)
        await s.commit()
        other_id = other.id
    r = await client.post(
        f"/characters/{other_id}/dice/post-to-chat",
        json={"notation": "d20", "rolls": [12], "total": 12},
    )
    assert r.status_code == 403, r.text


async def test_missing_bot_token_is_503(client, monkeypatch):
    clear_bot_token(monkeypatch)
    cid = await _make_char(client)
    r = await client.post(
        f"/characters/{cid}/dice/post-to-chat",
        json={"notation": "d20", "rolls": [12], "total": 12},
    )
    assert r.status_code == 503, r.text


async def test_single_roll_sends_to_authenticated_chat(client, monkeypatch):
    captured = install_fake_telegram(monkeypatch)
    cid = await _make_char(client)
    r = await client.post(
        f"/characters/{cid}/dice/post-to-chat",
        json={"notation": "d20", "rolls": [18], "total": 18},
    )
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True}
    assert len(captured) == 1
    sent = captured[0]
    assert sent["url"].endswith("/sendMessage")
    assert sent["json"]["chat_id"] == TEST_USER_ID
    assert sent["json"]["parse_mode"] == "Markdown"
    # single roll → "🎲 d20: *18*" (no "a + b =" expansion)
    assert sent["json"]["text"] == "🎲 d20: *18*"


async def test_multi_roll_joins_individual_values(client, monkeypatch):
    captured = install_fake_telegram(monkeypatch)
    cid = await _make_char(client)
    r = await client.post(
        f"/characters/{cid}/dice/post-to-chat",
        json={"notation": "2d6", "rolls": [3, 5], "total": 8},
    )
    assert r.status_code == 200, r.text
    assert captured[0]["json"]["text"] == "🎲 2d6: 3 + 5 = *8*"


async def test_telegram_failure_is_502(client, monkeypatch):
    install_fake_telegram(monkeypatch, status_code=500)
    cid = await _make_char(client)
    r = await client.post(
        f"/characters/{cid}/dice/post-to-chat",
        json={"notation": "d20", "rolls": [18], "total": 18},
    )
    assert r.status_code == 502, r.text
