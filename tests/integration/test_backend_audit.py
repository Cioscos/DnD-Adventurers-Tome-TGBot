"""Difetti di sicurezza dell'audit backend del 2026-11-18: ogni test fallisce se il difetto torna."""
from __future__ import annotations

import hashlib
import hmac
import json
from urllib.parse import quote

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect

from api import auth
from api.locks import lock_key
from api.routers import notes as notes_router
from api.schemas.item import ItemCreate
from api.services.dice_notation import DICE_RE, roll_dice
from api.services.game_sessions import touch
from core.db.engine import _migrate_schema
from core.db.models import Base, Character, GameSession, SessionStatus
from tests.integration.conftest import TEST_USER_ID

TOKEN = "123:abc"


def _init_data(first_name: str) -> str:
    """initData come lo manda Telegram: valori percent-encoded, firma sulle coppie in chiaro."""
    pairs = {"auth_date": str(int(__import__("time").time())), "user": json.dumps({"id": 7, "first_name": first_name})}
    check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
    pairs["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return "&".join(f"{k}={quote(v, safe='')}" for k, v in pairs.items())


@pytest.mark.parametrize("name", ["Mario", "Tom & Jerry", "A+B", "100% x", "a=b"])
def test_init_data_with_special_chars_in_name(name):
    assert auth.verify_init_data_full(_init_data(name), TOKEN).first_name == name


async def test_deleting_a_forged_voice_note_never_deletes_outside_the_voice_folder(client, test_session_factory, tmp_path, monkeypatch):
    monkeypatch.setattr(notes_router, "_VOICE_DIR", tmp_path / "voice_notes")
    victim = tmp_path / "dnd_bot.db"
    victim.write_text("dati")
    async with test_session_factory() as s:
        char = Character(user_id=TEST_USER_ID, name="Nota")
        s.add(char)
        await s.commit()
        cid = char.id
    own = tmp_path / "voice_notes" / str(cid) / "a.webm"
    own.parent.mkdir(parents=True)
    own.write_text("audio")
    for title, path in (("finta", victim), ("vera", own)):
        r = await client.post(f"/characters/{cid}/notes", json={"title": title, "body": f"[VOICE:{path}]"})
        assert r.status_code == 201, r.text
        assert (await client.delete(f"/characters/{cid}/notes/{title}")).status_code == 200
    assert victim.exists() and not own.exists()


@pytest.mark.parametrize("notation", ["99999999d6", "1000d6", "1d0", "1d99999"])
def test_huge_or_zero_dice_are_not_rolled(notation):
    assert DICE_RE.match(notation) is None and roll_dice(notation) == ([0], 0)


def test_normal_dice_still_roll():
    rolls, bonus = roll_dice("8d6+3")
    assert len(rolls) == 8 and bonus == 3 and roll_dice("100d100")[0]


def test_versatile_dice_are_capped_in_the_schema():
    with pytest.raises(ValidationError):
        ItemCreate(name="Spada", item_type="weapon", item_metadata={"versatile_dice": "99999999d6"})


def test_lock_key_covers_session_routes_and_ignores_non_numeric_ids():
    assert lock_key("/characters/4/hp", {"char_id": 4}) == "char:4"
    assert lock_key("/sessions/9/trade", {"session_id": 9}) == "session:9"
    assert lock_key("/characters/abc/hp", {"char_id": "abc"}) is None  # niente lock per id inventati
    assert lock_key("/share/recap/9", {"session_id": 9}) is None  # legge e aspetta Telegram


def test_touch_writes_at_most_once_a_minute():
    fresh = GameSession(code="AAAAAA", gm_user_id=1, status=SessionStatus.ACTIVE, created_at="x", last_activity_at="2000-01-01T00:00:00")
    touch(fresh)
    stamp = fresh.last_activity_at
    assert stamp != "2000-01-01T00:00:00"
    fresh.last_activity_at = stamp[:16] + ":00"
    touch(fresh)
    assert fresh.last_activity_at == stamp[:16] + ":00"


def test_migration_adds_character_id_indexes_to_old_tables(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP INDEX ix_items_character_id")  # DB nato prima dell'indice
        _migrate_schema(conn)
        assert "ix_items_character_id" in {i["name"] for i in inspect(conn).get_indexes("items")}
