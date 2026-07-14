"""Snapshot di condivisione (content_shares): creazione, import, cleanup.

Il mittente congela item/note in una riga ContentShare; il destinatario la
riscatta via POST /shares/{token}/import ottenendo una COPIA indipendente.
Le note vocali portano con sé una copia del file audio in SHARED_VOICE_DIR,
così la condivisione sopravvive alla cancellazione dell'originale.
"""
from __future__ import annotations

import secrets
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models import Character, ContentShare, Item

SHARE_TTL_DAYS = 30
SHARED_VOICE_DIR = Path("data/shared_voice")
# Deve combaciare con _VOICE_DIR in api/routers/notes.py
VOICE_NOTES_DIR = Path("data/voice_notes")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_token() -> str:
    # 12 char URL-safe [A-Za-z0-9_-]: charset ammesso dal parametro startapp
    return secrets.token_urlsafe(9)


def is_expired(share: ContentShare) -> bool:
    return share.expires_at < _now().isoformat()


def create_item_share(item: Item, char: Character, user_id: int) -> ContentShare:
    now = _now()
    return ContentShare(
        token=_new_token(),
        kind="item",
        payload={
            "name": item.name,
            "description": item.description,
            "weight": item.weight or 0.0,
            "quantity": item.quantity or 1,
            "item_type": item.item_type or "generic",
            "item_metadata": item.item_metadata,
        },
        voice_file_path=None,
        created_by=user_id,
        sender_char_name=char.name,
        created_at=now.isoformat(),
        expires_at=(now + timedelta(days=SHARE_TTL_DAYS)).isoformat(),
    )


def create_note_share(
    title: str, body: str, tags: list[str], char: Character, user_id: int,
) -> ContentShare:
    """Nota testuale o vocale. Per le vocali copia il file in SHARED_VOICE_DIR.

    Solleva FileNotFoundError se il body referenzia un audio inesistente.
    """
    token = _new_token()
    voice_file_path: Optional[str] = None
    stored_body = body
    if body.startswith("[VOICE:") and body.endswith("]"):
        src = Path(body[7:-1])
        if not src.exists():
            raise FileNotFoundError(str(src))
        SHARED_VOICE_DIR.mkdir(parents=True, exist_ok=True)
        dest = SHARED_VOICE_DIR / f"{token}{src.suffix}"
        shutil.copyfile(src, dest)
        voice_file_path = str(dest)
        # Segnaposto: il file vero è voice_file_path, risolto all'import
        stored_body = "[VOICE:shared]"
    now = _now()
    return ContentShare(
        token=token,
        kind="note",
        payload={"title": title, "body": stored_body, "tags": list(tags or [])},
        voice_file_path=voice_file_path,
        created_by=user_id,
        sender_char_name=char.name,
        created_at=now.isoformat(),
        expires_at=(now + timedelta(days=SHARE_TTL_DAYS)).isoformat(),
    )


def unique_note_title(existing: dict, title: str) -> str:
    """Le note sono un dict chiave=titolo: risolvi le collisioni con " (n)"."""
    if title not in existing:
        return title
    n = 2
    while f"{title} ({n})" in existing:
        n += 1
    return f"{title} ({n})"


def import_item(share: ContentShare, char: Character) -> Item:
    """Costruisce la copia dell'item per `char` (il chiamante fa db.add)."""
    p = share.payload or {}
    return Item(
        character_id=char.id,
        name=str(p.get("name") or "?"),
        description=p.get("description"),
        weight=float(p.get("weight") or 0.0),
        quantity=int(p.get("quantity") or 1),
        item_type=str(p.get("item_type") or "generic"),
        item_metadata=p.get("item_metadata"),
        is_equipped=False,
        equipment_slot=None,
    )


def import_note(share: ContentShare, char: Character) -> str:
    """Copia la nota in `char.notes` e ritorna il titolo finale.

    Per le vocali copia l'audio condiviso in VOICE_NOTES_DIR/{char_id}/.
    Solleva FileNotFoundError se l'audio condiviso non esiste più su disco.
    """
    p = share.payload or {}
    notes = dict(char.notes or {})
    title = unique_note_title(notes, str(p.get("title") or "Nota"))
    body = str(p.get("body") or "")
    if share.voice_file_path:
        src = Path(share.voice_file_path)
        if not src.exists():
            raise FileNotFoundError(share.voice_file_path)
        dest_dir = VOICE_NOTES_DIR / str(char.id)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"{uuid.uuid4().hex}{src.suffix}"
        shutil.copyfile(src, dest)
        body = f"[VOICE:{dest}]"
    notes[title] = {
        "body": body,
        "created_at": _now().isoformat(),
        "tags": list(p.get("tags") or []),
    }
    char.notes = notes
    return title


async def cleanup_expired(db: AsyncSession) -> int:
    """Elimina snapshot scaduti + relativi file audio. Ritorna quanti erano."""
    now_iso = _now().isoformat()
    rows = (await db.execute(
        select(ContentShare).where(ContentShare.expires_at < now_iso)
    )).scalars().all()
    for row in rows:
        if row.voice_file_path:
            Path(row.voice_file_path).unlink(missing_ok=True)
        await db.delete(row)
    return len(rows)
