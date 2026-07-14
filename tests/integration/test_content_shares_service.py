"""Unit del servizio content_shares: snapshot, import, scadenza, cleanup."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import select

import api.services.content_shares as cs
from core.db.models import Character, ContentShare, EquipmentSlot, Item


def _char(**kw) -> Character:
    return Character(user_id=1, name="Merlino", **kw)


def test_create_item_share_freezes_payload():
    item = Item(character_id=1, name="Pozione", description="Cura 2d4+2",
                weight=0.5, quantity=3, item_type="consumable",
                item_metadata='{"subtype": "potion"}')
    share = cs.create_item_share(item, _char(), user_id=42)
    assert share.kind == "item"
    assert share.created_by == 42
    assert share.sender_char_name == "Merlino"
    assert share.payload["name"] == "Pozione"
    assert share.payload["quantity"] == 3
    assert share.voice_file_path is None
    assert len(share.token) >= 8
    assert share.expires_at > share.created_at


def test_create_note_share_copies_voice_file(tmp_path, monkeypatch):
    monkeypatch.setattr(cs, "SHARED_VOICE_DIR", tmp_path / "shared")
    src = tmp_path / "voice" / "abc.webm"
    src.parent.mkdir(parents=True)
    src.write_bytes(b"audio")
    share = cs.create_note_share("Memo", f"[VOICE:{src}]", [], _char(), user_id=1)
    assert share.kind == "note"
    assert share.voice_file_path is not None
    copied = Path(share.voice_file_path)
    assert copied.read_bytes() == b"audio"
    src.unlink()  # il mittente cancella l'originale: la copia sopravvive
    assert copied.exists()


def test_create_note_share_missing_voice_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(cs, "SHARED_VOICE_DIR", tmp_path / "shared")
    with pytest.raises(FileNotFoundError):
        cs.create_note_share("Memo", "[VOICE:/non/esiste.webm]", [], _char(), user_id=1)


def test_unique_note_title_suffixes():
    existing = {"Piano": 1, "Piano (2)": 1}
    assert cs.unique_note_title(existing, "Piano") == "Piano (3)"
    assert cs.unique_note_title(existing, "Altro") == "Altro"


def test_is_expired():
    now = datetime.now(timezone.utc)
    share = ContentShare(token="t", kind="item", payload={}, created_by=1,
                         sender_char_name="X",
                         created_at=now.isoformat(),
                         expires_at=(now - timedelta(seconds=1)).isoformat())
    assert cs.is_expired(share)


def test_import_item_resets_equip_state():
    src_item = Item(character_id=1, name="Spada", weight=3.0, quantity=1,
                    item_type="weapon", is_equipped=True,
                    equipment_slot=EquipmentSlot.MAIN_HAND)
    share = cs.create_item_share(src_item, _char(), user_id=1)
    dest = Character(id=7, user_id=2, name="Rico")
    item = cs.import_item(share, dest)
    assert item.character_id == 7
    assert item.name == "Spada"
    assert item.is_equipped is False
    assert item.equipment_slot is None


def test_import_note_text_with_title_collision():
    share = cs.create_note_share("Piano", "corpo", ["tag1"], _char(), user_id=1)
    dest = Character(id=9, user_id=2, name="Rico",
                     notes={"Piano": {"body": "già mio"}})
    title = cs.import_note(share, dest)
    assert title == "Piano (2)"
    assert dest.notes["Piano (2)"]["body"] == "corpo"
    assert dest.notes["Piano (2)"]["tags"] == ["tag1"]
    assert dest.notes["Piano"]["body"] == "già mio"  # intatta


def test_import_note_voice_copies_into_char_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(cs, "SHARED_VOICE_DIR", tmp_path / "shared")
    monkeypatch.setattr(cs, "VOICE_NOTES_DIR", tmp_path / "voice_notes")
    src = tmp_path / "orig.webm"
    src.write_bytes(b"audio")
    share = cs.create_note_share("Memo", f"[VOICE:{src}]", [], _char(), user_id=1)
    dest = Character(id=9, user_id=2, name="Rico")
    title = cs.import_note(share, dest)
    body = dest.notes[title]["body"]
    assert body.startswith("[VOICE:") and body.endswith("]")
    copied = Path(body[7:-1])
    assert copied.exists()
    assert copied.parent == tmp_path / "voice_notes" / "9"


def test_import_note_voice_missing_file_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(cs, "SHARED_VOICE_DIR", tmp_path / "shared")
    monkeypatch.setattr(cs, "VOICE_NOTES_DIR", tmp_path / "voice_notes")
    src = tmp_path / "orig.webm"
    src.write_bytes(b"audio")
    share = cs.create_note_share("Memo", f"[VOICE:{src}]", [], _char(), user_id=1)
    Path(share.voice_file_path).unlink()  # disco ripulito a mano
    with pytest.raises(FileNotFoundError):
        cs.import_note(share, Character(id=9, user_id=2, name="Rico"))


async def test_cleanup_expired_removes_rows_and_files(
        test_session_factory, tmp_path, monkeypatch):
    monkeypatch.setattr(cs, "SHARED_VOICE_DIR", tmp_path)
    now = datetime.now(timezone.utc)
    dead_file = tmp_path / "dead.webm"
    dead_file.write_bytes(b"x")
    async with test_session_factory() as s:
        s.add(ContentShare(token="dead", kind="note", payload={}, created_by=1,
                           sender_char_name="X", voice_file_path=str(dead_file),
                           created_at=(now - timedelta(days=40)).isoformat(),
                           expires_at=(now - timedelta(days=10)).isoformat()))
        s.add(ContentShare(token="alive", kind="item", payload={}, created_by=1,
                           sender_char_name="X",
                           created_at=now.isoformat(),
                           expires_at=(now + timedelta(days=30)).isoformat()))
        await s.commit()
    async with test_session_factory() as s:
        removed = await cs.cleanup_expired(s)
        await s.commit()
    assert removed == 1
    assert not dead_file.exists()
    async with test_session_factory() as s:
        rows = (await s.execute(select(ContentShare.token))).scalars().all()
    assert rows == ["alive"]


def test_share_and_import_preserve_zero_quantity():
    item = Item(character_id=1, name="Pozione esaurita", weight=0.5,
                quantity=0, item_type="consumable")
    share = cs.create_item_share(item, _char(), user_id=1)
    assert share.payload["quantity"] == 0
    imported = cs.import_item(share, Character(id=7, user_id=2, name="Rico"))
    assert imported.quantity == 0
