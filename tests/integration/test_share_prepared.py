"""Endpoint di condivisione via messaggi preparati (savePreparedInlineMessage).

La Mini App chiede all'API un prepared_message_id e poi chiama
Telegram.WebApp.shareMessage(id). Qui si verifica il payload inviato al Bot
API (testo, bottone deep-link, permessi chat) e le guardie 403/404/502/503.
"""
from __future__ import annotations

from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, seed_session
from tests.integration._telegram_stub import clear_bot_token, install_fake_telegram
from tests.integration.conftest import TEST_USER_ID


async def _make_char(client, name: str = "Condivisore") -> int:
    r = await client.post("/characters", json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _prepared_calls(captured: list[dict]) -> list[dict]:
    return [c for c in captured if "savePreparedInlineMessage" in c["url"]]


async def test_share_card_builds_prepared_message(client, monkeypatch):
    captured = install_fake_telegram(monkeypatch)
    cid = await _make_char(client)
    r = await client.post(f"/characters/{cid}/classes",
                          json={"class_name": "fighter", "level": 3, "hit_die": 10})
    assert r.status_code in (200, 201), r.text

    r = await client.post(f"/characters/{cid}/share/card")
    assert r.status_code == 200, r.text
    assert r.json() == {"prepared_message_id": "prep-1"}

    calls = _prepared_calls(captured)
    assert len(calls) == 1
    payload = calls[0]["json"]
    assert payload["user_id"] == TEST_USER_ID
    assert payload["allow_group_chats"] is True
    text = payload["result"]["input_message_content"]["message_text"]
    assert "Condivisore" in text
    assert "Fighter 3" in text


async def test_share_item_includes_name_and_404_on_foreign(client, monkeypatch):
    captured = install_fake_telegram(monkeypatch)
    cid = await _make_char(client)
    r = await client.post(f"/characters/{cid}/items",
                          json={"name": "Pozione di cura", "item_type": "generic", "quantity": 3})
    assert r.status_code == 201, r.text
    items = (await client.get(f"/characters/{cid}/items")).json()
    item_id = next(i["id"] for i in items if i["name"] == "Pozione di cura")

    r = await client.post(f"/characters/{cid}/share/items/{item_id}")
    assert r.status_code == 200, r.text
    text = _prepared_calls(captured)[0]["json"]["result"]["input_message_content"]["message_text"]
    assert "Pozione di cura" in text and "×3" in text

    assert (await client.post(f"/characters/{cid}/share/items/999999")).status_code == 404


async def test_share_invite_gm_only_with_deeplink_button(
        client, test_session_factory, monkeypatch):
    captured = install_fake_telegram(monkeypatch)
    sid, _cid = await seed_session(test_session_factory)

    as_user(GM_ID)
    r = await client.post(f"/sessions/{sid}/share/invite")
    assert r.status_code == 200, r.text
    payload = _prepared_calls(captured)[0]["json"]
    button = payload["result"]["reply_markup"]["inline_keyboard"][0][0]
    assert button["url"] == "https://t.me/testbot?startapp=join_ABC123"
    assert "ABC123" in payload["result"]["input_message_content"]["message_text"]

    as_user(PLAYER_ID)
    assert (await client.post(f"/sessions/{sid}/share/invite")).status_code == 403


async def test_share_without_token_is_503(client, monkeypatch):
    clear_bot_token(monkeypatch)
    cid = await _make_char(client)
    assert (await client.post(f"/characters/{cid}/share/card")).status_code == 503


async def test_share_telegram_failure_is_502(client, monkeypatch):
    install_fake_telegram(monkeypatch, status_code=500)
    cid = await _make_char(client)
    assert (await client.post(f"/characters/{cid}/share/card")).status_code == 502
