"""Notes endpoints.

Notes are stored as a JSON dict on the Character model:
  {title: body_string, ...}

Voice notes are stored with body = "[VOICE:unavailable]" (display only).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.auth import get_current_user
from api.database import get_db
from bot.db.models import Character, CharacterClass

router = APIRouter(prefix="/characters", tags=["notes"])


class NoteRead(BaseModel):
    title: str
    body: str
    is_voice: bool = False


class NoteCreate(BaseModel):
    title: str
    body: str


class NoteUpdate(BaseModel):
    body: str


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
    return [
        NoteRead(
            title=title,
            body=body,
            is_voice=isinstance(body, str) and body.startswith("[VOICE:"),
        )
        for title, body in notes.items()
    ]


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
    notes[body.title] = body.body
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
    notes[title] = body.body
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
    del notes[title]
    char.notes = notes
    return _notes_list(char)
