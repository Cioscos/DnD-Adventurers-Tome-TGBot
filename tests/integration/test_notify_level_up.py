"""Notifica «level-up» SOLO all'attraversamento di soglia XP (update_xp).

Soglie 5e: 300 XP = liv. 2, 900 XP = liv. 3.
"""
from __future__ import annotations

from tests.integration._telegram_stub import install_fake_telegram
from tests.integration.conftest import TEST_USER_ID


async def _make_char(client, name: str = "Scalatore") -> int:
    r = await client.post("/characters", json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_crossing_threshold_notifies_with_xp_link(client, monkeypatch):
    captured = install_fake_telegram(monkeypatch)
    cid = await _make_char(client)
    r = await client.patch(f"/characters/{cid}/xp", json={"set": 300})
    assert r.status_code == 200, r.text
    assert len(captured) == 1
    payload = captured[0]["json"]
    assert payload["chat_id"] == TEST_USER_ID
    url = payload["reply_markup"]["inline_keyboard"][0][0]["web_app"]["url"]
    assert url.endswith(f"#/char/{cid}/xp")


async def test_same_level_change_is_silent(client, monkeypatch):
    captured = install_fake_telegram(monkeypatch)
    cid = await _make_char(client)
    await client.patch(f"/characters/{cid}/xp", json={"set": 300})
    captured.clear()
    r = await client.patch(f"/characters/{cid}/xp", json={"add": 50})  # 350: ancora liv. 2
    assert r.status_code == 200, r.text
    assert captured == []


async def test_xp_decrease_is_silent(client, monkeypatch):
    captured = install_fake_telegram(monkeypatch)
    cid = await _make_char(client)
    await client.patch(f"/characters/{cid}/xp", json={"set": 300})
    captured.clear()
    await client.patch(f"/characters/{cid}/xp", json={"set": 0})
    assert captured == []


async def test_opt_out_is_silent(client, monkeypatch):
    captured = install_fake_telegram(monkeypatch)
    cid = await _make_char(client)
    r = await client.patch(f"/characters/{cid}", json={
        "settings": {"notifications": {"level_up": False}}})
    assert r.status_code == 200, r.text
    await client.patch(f"/characters/{cid}/xp", json={"set": 300})
    assert captured == []
