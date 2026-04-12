"""Map endpoints including Telegram file_id proxy and local file upload."""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user
from api.database import get_db
from bot.db.models import Character, Map
from api.schemas.common import MapRead

router = APIRouter(prefix="/characters", tags=["maps"])

_BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
_MAPS_DIR = Path("data/maps")
_ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".pdf"}
_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


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


async def _get_map(map_id: int, char_id: int, session: AsyncSession) -> Map:
    result = await session.execute(
        select(Map).where(Map.id == map_id, Map.character_id == char_id)
    )
    m = result.scalar_one_or_none()
    if m is None:
        raise HTTPException(status_code=404, detail="Map not found")
    return m


@router.get("/{char_id}/maps", response_model=list[MapRead])
async def list_maps(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[Map]:
    await _get_owned(char_id, user_id, session)
    result = await session.execute(
        select(Map).where(Map.character_id == char_id).order_by(Map.zone_name)
    )
    return list(result.scalars().all())


@router.get("/{char_id}/maps/{map_id}/file", response_model=None)
async def get_map_file(
    char_id: int,
    map_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    """Serve a map file — from local disk if uploaded via webapp, or proxied from Telegram."""
    await _get_owned(char_id, user_id, session)
    map_row = await _get_map(map_id, char_id, session)

    # Local file (uploaded via webapp)
    if map_row.local_file_path:
        local_path = Path(map_row.local_file_path)
        if not local_path.exists():
            raise HTTPException(status_code=404, detail="Local file not found on disk")
        suffix = local_path.suffix.lower()
        media_map = {
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".png": "image/png", ".gif": "image/gif",
            ".webp": "image/webp", ".bmp": "image/bmp",
            ".pdf": "application/pdf",
        }
        content_type = media_map.get(suffix, "application/octet-stream")
        return FileResponse(local_path, media_type=content_type)

    # Telegram file proxy (existing behaviour)
    if not _BOT_TOKEN:
        raise HTTPException(status_code=500, detail="BOT_TOKEN not configured")

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"https://api.telegram.org/bot{_BOT_TOKEN}/getFile",
            params={"file_id": map_row.file_id},
        )
    if resp.status_code != 200 or not resp.json().get("ok"):
        raise HTTPException(status_code=502, detail="Failed to retrieve file from Telegram")

    file_path = resp.json()["result"]["file_path"]
    file_url = f"https://api.telegram.org/file/bot{_BOT_TOKEN}/{file_path}"

    async def _stream():
        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream("GET", file_url) as r:
                async for chunk in r.aiter_bytes(chunk_size=8192):
                    yield chunk

    content_type = (
        "image/jpeg"
        if map_row.file_type == "photo"
        else "application/octet-stream"
    )
    return StreamingResponse(_stream(), media_type=content_type)


# ---------------------------------------------------------------------------
# Upload map from webapp
# ---------------------------------------------------------------------------

@router.post("/{char_id}/maps/upload", response_model=MapRead, status_code=201)
async def upload_map(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    zone_name: str = Form(...),
    file: UploadFile = File(...),
) -> Map:
    """Upload a map image from the webapp and associate it with a zone."""
    await _get_owned(char_id, user_id, session)

    # Validate file extension
    original_name = file.filename or "upload"
    suffix = Path(original_name).suffix.lower()
    if suffix not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed: {', '.join(_ALLOWED_EXTENSIONS)}",
        )

    # Read file content (with size check)
    content = await file.read()
    if len(content) > _MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 10 MB)")

    # Save to data/maps/{char_id}/{uuid}.{ext}
    char_dir = _MAPS_DIR / str(char_id)
    char_dir.mkdir(parents=True, exist_ok=True)

    file_name = f"{uuid.uuid4().hex}{suffix}"
    file_path = char_dir / file_name
    file_path.write_bytes(content)

    # Determine file_type
    image_exts = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
    file_type = "photo" if suffix in image_exts else "document"

    map_row = Map(
        character_id=char_id,
        zone_name=zone_name.strip(),
        file_id="",
        file_type=file_type,
        local_file_path=str(file_path),
    )
    session.add(map_row)
    await session.flush()
    return map_row


@router.delete("/{char_id}/maps/{map_id}", status_code=204)
async def delete_map(
    char_id: int,
    map_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await _get_owned(char_id, user_id, session)
    map_row = await _get_map(map_id, char_id, session)
    # Clean up local file if exists
    if map_row.local_file_path:
        local_path = Path(map_row.local_file_path)
        if local_path.exists():
            local_path.unlink()
    await session.delete(map_row)


@router.delete("/{char_id}/maps/zone/{zone_name}", status_code=204)
async def delete_map_zone(
    char_id: int,
    zone_name: str,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await _get_owned(char_id, user_id, session)
    result = await session.execute(
        select(Map).where(Map.character_id == char_id, Map.zone_name == zone_name)
    )
    maps = result.scalars().all()
    for m in maps:
        # Clean up local files
        if m.local_file_path:
            local_path = Path(m.local_file_path)
            if local_path.exists():
                local_path.unlink()
        await session.delete(m)
