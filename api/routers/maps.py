"""Map endpoints including Telegram file_id proxy."""

from __future__ import annotations

import os
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user
from api.database import get_db
from bot.db.models import Character, Map
from api.schemas.common import MapRead

router = APIRouter(prefix="/characters", tags=["maps"])

_BOT_TOKEN = os.environ.get("BOT_TOKEN", "")


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


@router.get("/{char_id}/maps/{map_id}/file")
async def get_map_file(
    char_id: int,
    map_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> StreamingResponse:
    """Proxy the Telegram file so the browser can display it as <img> or download it."""
    await _get_owned(char_id, user_id, session)
    map_row = await _get_map(map_id, char_id, session)

    if not _BOT_TOKEN:
        raise HTTPException(status_code=500, detail="BOT_TOKEN not configured")

    # Get Telegram file path (temporary URL)
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"https://api.telegram.org/bot{_BOT_TOKEN}/getFile",
            params={"file_id": map_row.file_id},
        )
    if resp.status_code != 200 or not resp.json().get("ok"):
        raise HTTPException(status_code=502, detail="Failed to retrieve file from Telegram")

    file_path = resp.json()["result"]["file_path"]
    file_url = f"https://api.telegram.org/file/bot{_BOT_TOKEN}/{file_path}"

    # Stream file to client
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


@router.delete("/{char_id}/maps/{map_id}", status_code=204)
async def delete_map(
    char_id: int,
    map_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await _get_owned(char_id, user_id, session)
    map_row = await _get_map(map_id, char_id, session)
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
        await session.delete(m)
