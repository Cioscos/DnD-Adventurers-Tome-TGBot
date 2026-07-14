"""Ciclo di condivisione con import: snapshot, bottone deep-link, riscatto.

Copre l'estensione di share_item (Task 2), share_note (Task 3) e il router
/shares (Task 4). Telegram è mockato via _telegram_stub.
"""
from __future__ import annotations

from tests.integration._encounter_helpers import PLAYER_ID, as_user
from tests.integration._telegram_stub import install_fake_telegram
from tests.integration.conftest import TEST_USER_ID

from core.db.models import ContentShare


async def _make_char(client, name: str = "Merlino") -> int:
    r = await client.post("/characters", json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _prepared_calls(captured: list[dict]) -> list[dict]:
    return [c for c in captured if "savePreparedInlineMessage" in c["url"]]


def _button_of(captured: list[dict]) -> dict:
    return _prepared_calls(captured)[-1]["json"]["result"]["reply_markup"]["inline_keyboard"][0][0]


def _token_of(captured: list[dict]) -> str:
    url = _button_of(captured)["url"]
    assert url.startswith("https://t.me/testbot?startapp=shr_"), url
    return url.split("startapp=shr_")[1]


async def _make_item(client, cid: int, name: str = "Corda di seta") -> int:
    r = await client.post(f"/characters/{cid}/items",
                          json={"name": name, "item_type": "gear", "quantity": 1})
    assert r.status_code == 201, r.text
    items = (await client.get(f"/characters/{cid}/items")).json()
    return next(i["id"] for i in items if i["name"] == name)


async def test_share_item_adds_deeplink_button_and_snapshot(
        client, test_session_factory, monkeypatch):
    captured = install_fake_telegram(monkeypatch)
    cid = await _make_char(client)
    item_id = await _make_item(client, cid)

    r = await client.post(f"/characters/{cid}/share/items/{item_id}")
    assert r.status_code == 200, r.text
    assert r.json() == {"prepared_message_id": "prep-1"}

    token = _token_of(captured)
    async with test_session_factory() as s:
        share = await s.get(ContentShare, token)
    assert share is not None
    assert share.kind == "item"
    assert share.created_by == TEST_USER_ID
    assert share.sender_char_name == "Merlino"
    assert share.payload["name"] == "Corda di seta"
    assert share.expires_at > share.created_at


async def test_share_note_text_has_preview_and_button(
        client, test_session_factory, monkeypatch):
    captured = install_fake_telegram(monkeypatch)
    cid = await _make_char(client)
    r = await client.post(f"/characters/{cid}/notes",
                          json={"title": "Piano segreto", "body": "Entrare dal retro",
                                "tags": ["missione"]})
    assert r.status_code == 201, r.text

    r = await client.post(f"/characters/{cid}/share/notes/Piano%20segreto")
    assert r.status_code == 200, r.text

    payload = _prepared_calls(captured)[-1]["json"]
    text = payload["result"]["input_message_content"]["message_text"]
    assert "Piano segreto" in text
    assert "Entrare dal retro" in text
    token = _token_of(captured)
    async with test_session_factory() as s:
        share = await s.get(ContentShare, token)
    assert share.kind == "note"
    assert share.payload["title"] == "Piano segreto"
    assert share.payload["tags"] == ["missione"]

    assert (await client.post(f"/characters/{cid}/share/notes/Inesistente")).status_code == 404


async def test_share_note_voice_copies_audio(client, monkeypatch, tmp_path):
    import api.routers.notes as notes_router
    import api.services.content_shares as cs
    monkeypatch.setattr(notes_router, "_VOICE_DIR", tmp_path / "voice_notes")
    monkeypatch.setattr(cs, "SHARED_VOICE_DIR", tmp_path / "shared")
    captured = install_fake_telegram(monkeypatch)
    cid = await _make_char(client)

    r = await client.post(
        f"/characters/{cid}/notes/voice",
        data={"title": "Memo vocale"},
        files={"file": ("memo.webm", b"finto-audio", "audio/webm")},
    )
    assert r.status_code == 201, r.text

    r = await client.post(f"/characters/{cid}/share/notes/Memo%20vocale")
    assert r.status_code == 200, r.text

    text = _prepared_calls(captured)[-1]["json"]["result"]["input_message_content"]["message_text"]
    assert "Memo vocale" in text
    assert "finto-audio" not in text  # niente body per le vocali
    shared_files = list((tmp_path / "shared").iterdir())
    assert len(shared_files) == 1
    assert shared_files[0].read_bytes() == b"finto-audio"


# ---------------------------------------------------------------------------
# GET /shares/{token} + POST /shares/{token}/import
# ---------------------------------------------------------------------------

from datetime import datetime, timedelta, timezone


async def _expire(test_session_factory, token: str) -> None:
    async with test_session_factory() as s:
        share = await s.get(ContentShare, token)
        share.expires_at = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        await s.commit()


async def test_preview_and_import_item_by_other_user(
        client, test_session_factory, monkeypatch):
    captured = install_fake_telegram(monkeypatch)
    cid = await _make_char(client)
    item_id = await _make_item(client, cid, name="Pozione rara")
    assert (await client.post(f"/characters/{cid}/share/items/{item_id}")).status_code == 200
    token = _token_of(captured)

    # Il mittente cancella l'originale: lo snapshot sopravvive
    assert (await client.delete(f"/characters/{cid}/items/{item_id}")).status_code in (200, 204)

    as_user(PLAYER_ID)
    dest_cid = await _make_char(client, name="Rico")

    r = await client.get(f"/shares/{token}")
    assert r.status_code == 200, r.text
    preview = r.json()
    assert preview["kind"] == "item"
    assert preview["title"] == "Pozione rara"
    assert preview["sender_char_name"] == "Merlino"

    r = await client.post(f"/shares/{token}/import", json={"char_id": dest_cid})
    assert r.status_code == 200, r.text
    assert r.json()["kind"] == "item"
    items = (await client.get(f"/characters/{dest_cid}/items")).json()
    assert any(i["name"] == "Pozione rara" and not i["is_equipped"] for i in items)

    # Multi-import: una seconda copia è legittima
    assert (await client.post(f"/shares/{token}/import", json={"char_id": dest_cid})).status_code == 200
    as_user(TEST_USER_ID)


async def test_import_note_with_collision_gets_suffix(
        client, test_session_factory, monkeypatch):
    captured = install_fake_telegram(monkeypatch)
    cid = await _make_char(client)
    assert (await client.post(f"/characters/{cid}/notes",
            json={"title": "Piano", "body": "condiviso", "tags": []})).status_code == 201
    assert (await client.post(f"/characters/{cid}/share/notes/Piano")).status_code == 200
    token = _token_of(captured)

    as_user(PLAYER_ID)
    dest_cid = await _make_char(client, name="Rico")
    assert (await client.post(f"/characters/{dest_cid}/notes",
            json={"title": "Piano", "body": "mio", "tags": []})).status_code == 201

    r = await client.post(f"/shares/{token}/import", json={"char_id": dest_cid})
    assert r.status_code == 200, r.text
    assert r.json()["title"] == "Piano (2)"
    titles = {n["title"] for n in (await client.get(f"/characters/{dest_cid}/notes")).json()}
    assert {"Piano", "Piano (2)"} <= titles
    as_user(TEST_USER_ID)


async def test_import_voice_note_copies_audio_missing_file_410(
        client, test_session_factory, monkeypatch, tmp_path):
    import api.routers.notes as notes_router
    import api.services.content_shares as cs
    monkeypatch.setattr(notes_router, "_VOICE_DIR", tmp_path / "voice_notes")
    monkeypatch.setattr(cs, "SHARED_VOICE_DIR", tmp_path / "shared")
    monkeypatch.setattr(cs, "VOICE_NOTES_DIR", tmp_path / "voice_notes")
    captured = install_fake_telegram(monkeypatch)
    cid = await _make_char(client)
    assert (await client.post(
        f"/characters/{cid}/notes/voice",
        data={"title": "Memo"},
        files={"file": ("memo.webm", b"finto-audio", "audio/webm")},
    )).status_code == 201
    assert (await client.post(f"/characters/{cid}/share/notes/Memo")).status_code == 200
    token = _token_of(captured)

    as_user(PLAYER_ID)
    dest_cid = await _make_char(client, name="Rico")
    r = await client.post(f"/shares/{token}/import", json={"char_id": dest_cid})
    assert r.status_code == 200, r.text
    notes = (await client.get(f"/characters/{dest_cid}/notes")).json()
    assert any(n["title"] == "Memo" and n["is_voice"] for n in notes)

    # Audio condiviso rimosso a mano dal disco → 410 e snapshot eliminato
    for f in (tmp_path / "shared").iterdir():
        f.unlink()
    assert (await client.post(f"/shares/{token}/import",
                              json={"char_id": dest_cid})).status_code == 410
    assert (await client.get(f"/shares/{token}")).status_code == 404
    as_user(TEST_USER_ID)


async def test_share_guards(client, test_session_factory, monkeypatch):
    captured = install_fake_telegram(monkeypatch)
    cid = await _make_char(client)
    item_id = await _make_item(client, cid, name="Scudo")
    assert (await client.post(f"/characters/{cid}/share/items/{item_id}")).status_code == 200
    token = _token_of(captured)

    # Token ignoto
    assert (await client.get("/shares/tokenfinto1")).status_code == 404
    # Import su PG di un ALTRO utente
    as_user(PLAYER_ID)
    assert (await client.post(f"/shares/{token}/import",
                              json={"char_id": cid})).status_code == 403
    as_user(TEST_USER_ID)
    # Scaduto
    await _expire(test_session_factory, token)
    assert (await client.get(f"/shares/{token}")).status_code == 410
    assert (await client.post(f"/shares/{token}/import",
                              json={"char_id": cid})).status_code == 410
