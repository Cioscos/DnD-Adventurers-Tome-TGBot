"""Notes endpoints.

Notes are stored as a JSON dict on the Character model. Two value shapes are
supported for backward compatibility:

  Legacy (string): {title: body_string, ...}
  Current (dict):  {title: {body, created_at, updated_at?, tags?}, ...}

Voice notes carry body = "[VOICE:{relative_path}]" in either shape.
Audio files are saved under data/voice_notes/{char_id}/.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.auth import DEV_USER_ID, get_current_user, verify_init_data
from api.database import get_db
from core.db.models import Character, CharacterClass

router = APIRouter(prefix="/characters", tags=["notes"])

_VOICE_DIR = Path("data/voice_notes")
_ALLOWED_AUDIO_EXTS = {".webm", ".ogg", ".mp3", ".wav", ".m4a", ".aac"}
_MAX_VOICE_SIZE = 5 * 1024 * 1024  # 5 MB


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _unpack(value) -> dict:
    """Return a normalized record for a stored note value (legacy str or dict)."""
    if isinstance(value, dict):
        return {
            "body": str(value.get("body", "")),
            "created_at": value.get("created_at"),
            "updated_at": value.get("updated_at"),
            "tags": list(value.get("tags") or []),
        }
    return {"body": str(value or ""), "created_at": None, "updated_at": None, "tags": []}


class NoteRead(BaseModel):
    title: str
    body: str
    is_voice: bool = False
    created_at: str | None = None
    updated_at: str | None = None
    tags: list[str] = Field(default_factory=list)


class NoteCreate(BaseModel):
    title: str
    body: str
    tags: list[str] = Field(default_factory=list)


class NoteUpdate(BaseModel):
    body: str
    tags: list[str] | None = None


async def _get_owned(char_id: int, user_id: int, session: AsyncSession) -> Character:
    result = await session.execute(
        select(Character).where(Character.id == char_id)
    )
    char = result.scalar_one_or_none()
    if char is None:
        raise HTTPException(status_code=404, detail="Character not found")
    if char.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not your character")
    return char


def _notes_list(char: Character) -> list[NoteRead]:
    notes = char.notes or {}
    out: list[NoteRead] = []
    for title, value in notes.items():
        rec = _unpack(value)
        out.append(
            NoteRead(
                title=title,
                body=rec["body"],
                is_voice=rec["body"].startswith("[VOICE:"),
                created_at=rec["created_at"],
                updated_at=rec["updated_at"],
                tags=rec["tags"],
            )
        )
    return out


@router.get("/{char_id}/notes", response_model=list[NoteRead])
async def list_notes(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[NoteRead]:
    char = await _get_owned(char_id, user_id, session)
    return _notes_list(char)


@router.post("/{char_id}/notes", response_model=list[NoteRead], status_code=201)
async def add_note(
    char_id: int,
    body: NoteCreate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[NoteRead]:
    char = await _get_owned(char_id, user_id, session)
    notes = dict(char.notes or {})
    if body.title in notes:
        raise HTTPException(status_code=409, detail="A note with this title already exists")
    notes[body.title] = {
        "body": body.body,
        "created_at": _now_iso(),
        "tags": list(body.tags or []),
    }
    char.notes = notes
    return _notes_list(char)


@router.patch("/{char_id}/notes/{title}", response_model=list[NoteRead])
async def update_note(
    char_id: int,
    title: str,
    body: NoteUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[NoteRead]:
    char = await _get_owned(char_id, user_id, session)
    notes = dict(char.notes or {})
    if title not in notes:
        raise HTTPException(status_code=404, detail="Note not found")
    existing = _unpack(notes[title])
    notes[title] = {
        "body": body.body,
        "created_at": existing["created_at"],
        "updated_at": _now_iso(),
        "tags": list(body.tags) if body.tags is not None else existing["tags"],
    }
    char.notes = notes
    return _notes_list(char)


@router.delete("/{char_id}/notes/{title}", response_model=list[NoteRead])
async def delete_note(
    char_id: int,
    title: str,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[NoteRead]:
    char = await _get_owned(char_id, user_id, session)
    notes = dict(char.notes or {})
    if title not in notes:
        raise HTTPException(status_code=404, detail="Note not found")
    body_str = _unpack(notes[title])["body"]
    # Clean up voice file if applicable
    if body_str.startswith("[VOICE:") and body_str.endswith("]"):
        file_path = Path(body_str[7:-1])
        if file_path.exists():
            file_path.unlink()
    del notes[title]
    char.notes = notes
    return _notes_list(char)


# ---------------------------------------------------------------------------
# Voice notes
# ---------------------------------------------------------------------------

@router.post("/{char_id}/notes/voice", response_model=list[NoteRead], status_code=201)
async def upload_voice_note(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    title: str = Form(...),
    file: UploadFile = File(...),
) -> list[NoteRead]:
    """Upload a voice note (audio file) and associate it with the character."""
    char = await _get_owned(char_id, user_id, session)

    notes = dict(char.notes or {})
    if title in notes:
        raise HTTPException(status_code=409, detail="A note with this title already exists")

    # Validate file extension
    original_name = file.filename or "voice.webm"
    suffix = Path(original_name).suffix.lower()
    if suffix not in _ALLOWED_AUDIO_EXTS:
        raise HTTPException(
            status_code=400,
            detail=f"Audio format not allowed. Allowed: {', '.join(_ALLOWED_AUDIO_EXTS)}",
        )

    # Read file content with size check
    content = await file.read()
    if len(content) > _MAX_VOICE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 5 MB)")

    # Save to data/voice_notes/{char_id}/{uuid}.{ext}
    char_dir = _VOICE_DIR / str(char_id)
    char_dir.mkdir(parents=True, exist_ok=True)
    file_name = f"{uuid.uuid4().hex}{suffix}"
    file_path = char_dir / file_name
    file_path.write_bytes(content)

    # Store reference in notes dict
    notes[title] = {
        "body": f"[VOICE:{file_path}]",
        "created_at": _now_iso(),
        "tags": [],
    }
    char.notes = notes
    return _notes_list(char)


@router.get("/{char_id}/notes/voice/{filename}", response_model=None)
async def get_voice_file(
    char_id: int,
    filename: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    x_telegram_init_data: str = Header("", alias="X-Telegram-Init-Data"),
    init_data: str = Query(""),
):
    """Serve a voice note audio file."""
    # <audio src> cannot set custom headers, so accept init_data as query param fallback.
    if DEV_USER_ID is not None:
        user_id = DEV_USER_ID
    else:
        raw = x_telegram_init_data or init_data
        if not raw:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing auth")
        user_id = verify_init_data(raw)
    await _get_owned(char_id, user_id, session)

    file_path = _VOICE_DIR / str(char_id) / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Voice file not found")

    # Prevent path traversal
    if not file_path.resolve().is_relative_to(_VOICE_DIR.resolve()):
        raise HTTPException(status_code=400, detail="Invalid filename")

    media_map = {
        ".webm": "audio/webm", ".ogg": "audio/ogg",
        ".mp3": "audio/mpeg", ".wav": "audio/wav",
        ".m4a": "audio/mp4", ".aac": "audio/aac",
    }
    content_type = media_map.get(file_path.suffix.lower(), "application/octet-stream")
    return FileResponse(file_path, media_type=content_type)
