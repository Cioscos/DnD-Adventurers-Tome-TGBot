"""Custom paper-doll silhouette: upload, serve, delete (mirror del pattern mappe)."""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.auth import DEV_USER_ID, get_current_user, verify_init_data
from api.database import get_db
from api.schemas.character import CharacterFull
from api.services.character_response import build_character_response
from core.db.models import Character, CharacterClass

router = APIRouter(prefix="/characters", tags=["silhouette"])

_SIL_DIR = Path("data/silhouettes")
_ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
_MEDIA = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".webp": "image/webp", ".gif": "image/gif",
}


async def _get_owned(char_id: int, user_id: int, session: AsyncSession) -> Character:
    result = await session.execute(select(Character).where(Character.id == char_id))
    char = result.scalar_one_or_none()
    if char is None:
        raise HTTPException(status_code=404, detail="Character not found")
    if char.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not your character")
    return char


async def _get_owned_full(char_id: int, user_id: int, session: AsyncSession) -> Character:
    result = await session.execute(
        select(Character)
        .options(
            selectinload(Character.classes).selectinload(CharacterClass.resources),
            selectinload(Character.ability_scores),
            selectinload(Character.spells),
            selectinload(Character.spell_slots),
            selectinload(Character.items),
            selectinload(Character.currency),
            selectinload(Character.abilities),
            selectinload(Character.maps),
        )
        .where(Character.id == char_id)
    )
    char = result.scalar_one_or_none()
    if char is None:
        raise HTTPException(status_code=404, detail="Character not found")
    if char.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not your character")
    return char


@router.post("/{char_id}/silhouette", response_model=CharacterFull)
async def upload_silhouette(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(...),
) -> CharacterFull:
    char = await _get_owned_full(char_id, user_id, session)

    suffix = Path(file.filename or "upload").suffix.lower()
    if suffix not in _ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type not allowed. Allowed: {', '.join(sorted(_ALLOWED_EXTENSIONS))}")

    content = await file.read()
    if len(content) > _MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 10 MB)")

    # Remove the previous custom file, if any.
    if char.silhouette_path:
        old = Path(char.silhouette_path)
        if old.exists():
            try:
                old.unlink()
            except OSError:
                pass

    char_dir = _SIL_DIR / str(char_id)
    char_dir.mkdir(parents=True, exist_ok=True)
    file_path = char_dir / f"{uuid.uuid4().hex}{suffix}"
    file_path.write_bytes(content)
    char.silhouette_path = str(file_path)

    return await build_character_response(session, char)


@router.get("/{char_id}/silhouette/file")
async def get_silhouette_file(
    char_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
    x_telegram_init_data: str = Header("", alias="X-Telegram-Init-Data"),
    init_data: str = Query(""),
):
    # Auth: DEV_USER_ID -> header -> query param (come maps/{id}/file, per <img src>).
    if DEV_USER_ID is not None:
        user_id = DEV_USER_ID
    else:
        raw = x_telegram_init_data or init_data
        if not raw:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing auth")
        user_id = verify_init_data(raw)
    char = await _get_owned(char_id, user_id, session)
    if not char.silhouette_path:
        raise HTTPException(status_code=404, detail="No custom silhouette")
    path = Path(char.silhouette_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Silhouette file not found on disk")
    return FileResponse(path, media_type=_MEDIA.get(path.suffix.lower(), "application/octet-stream"))


@router.delete("/{char_id}/silhouette", response_model=CharacterFull)
async def delete_silhouette(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CharacterFull:
    char = await _get_owned_full(char_id, user_id, session)
    if char.silhouette_path:
        path = Path(char.silhouette_path)
        if path.exists():
            try:
                path.unlink()
            except OSError:
                pass
        char.silhouette_path = None
    return await build_character_response(session, char)
