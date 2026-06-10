"""Notifica «incontro iniziato» ai giocatori quando il GM apre un encounter."""
from __future__ import annotations

from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, seed_session
from tests.integration._telegram_stub import install_fake_telegram


async def test_create_encounter_notifies_players_not_gm(
        client, test_session_factory, monkeypatch):
    captured = install_fake_telegram(monkeypatch)
    sid, _cid = await seed_session(test_session_factory)
    as_user(GM_ID)
    r = await client.post(f"/sessions/{sid}/encounter", json={"mode": "light"})
    assert r.status_code == 201, r.text
    chats = [c["json"]["chat_id"] for c in captured]
    assert chats == [PLAYER_ID]
    payload = captured[0]["json"]
    assert "Incontro iniziato" in payload["text"]
    url = payload["reply_markup"]["inline_keyboard"][0][0]["web_app"]["url"]
    assert url.endswith(f"#/session/{sid}")


async def test_opt_out_is_silent(client, test_session_factory, monkeypatch):
    from core.db.models import Character
    captured = install_fake_telegram(monkeypatch)
    sid, cid = await seed_session(test_session_factory)
    async with test_session_factory() as s:
        char = await s.get(Character, cid)
        char.settings = {"notifications": {"encounter": False}}
        await s.commit()
    as_user(GM_ID)
    r = await client.post(f"/sessions/{sid}/encounter", json={"mode": "light"})
    assert r.status_code == 201, r.text
    assert captured == []
