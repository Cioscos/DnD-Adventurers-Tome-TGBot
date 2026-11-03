"""Campaign atlas: GM-uploaded maps (hidden until revealed); markers are added on top in Task 2."""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import DEV_USER_ID, get_current_user, verify_init_data
from api.database import get_db
from api.routers.campaigns import _active_session_id
from api.routers.lore import _access
from api.routers.sessions import _touch
from api.schemas.atlas import AtlasMapDeleted, AtlasMapRead, AtlasMapRename
from api.services import campaigns as svc
from api.services.atlas import map_visible, marker_visible
from api.services.campaigns import unlink_file
from core.db.models import CampaignMap, CampaignMapMarker, GameSession, SessionMessage, SessionRole

router = APIRouter(prefix="/campaigns/{campaign_id}/atlas", tags=["atlas"])

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
_MAX_IMAGE = 10 * 1024 * 1024
_MEDIA = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}


def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")  # naive UTC, like lore._now()


async def _read(db: AsyncSession, m: CampaignMap, user_id: int) -> AtlasMapRead:
    # Own + public markers, for the GM too: player-private ones never count.
    count = (await db.execute(
        select(func.count()).select_from(CampaignMapMarker)
        .where(CampaignMapMarker.map_id == m.id, marker_visible(user_id))
    )).scalar_one()
    return AtlasMapRead(
        id=m.id, name=m.name, revealed=m.revealed_at is not None, revealed_at=m.revealed_at,
        updated_at=m.updated_at, marker_count=count,
    )


async def _map(db: AsyncSession, campaign_id: int, map_id: int, is_gm: bool) -> CampaignMap:
    m = await db.get(CampaignMap, map_id)
    if m is None or m.campaign_id != campaign_id or not map_visible(m, is_gm):
        raise HTTPException(status_code=404, detail="map_not_found")
    return m


async def _gm_map(db: AsyncSession, campaign_id: int, map_id: int, user_id: int) -> CampaignMap:
    if not await _access(db, campaign_id, user_id):
        raise HTTPException(status_code=403, detail="gm_only")
    return await _map(db, campaign_id, map_id, True)


async def _save(campaign_id: int, file: UploadFile) -> str:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in _IMAGE_EXTS:
        raise HTTPException(status_code=400, detail=f"File format not allowed. Allowed: {', '.join(sorted(_IMAGE_EXTS))}")
    content = await file.read()
    if len(content) > _MAX_IMAGE:
        raise HTTPException(status_code=400, detail=f"File too large (max {_MAX_IMAGE // (1024 * 1024)} MB)")
    folder = svc.ATLAS_DIR / str(campaign_id)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{uuid.uuid4().hex}{suffix}"
    path.write_bytes(content)
    return str(path)


@router.get("/maps", response_model=list[AtlasMapRead])
async def list_maps(
    campaign_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[AtlasMapRead]:
    is_gm = await _access(db, campaign_id, user_id)
    rows = (await db.execute(
        select(CampaignMap).where(CampaignMap.campaign_id == campaign_id)
        .order_by(CampaignMap.created_at, CampaignMap.id)
    )).scalars().all()
    return [await _read(db, m, user_id) for m in rows if map_visible(m, is_gm)]


@router.post("/maps", response_model=AtlasMapRead, status_code=201)
async def create_map(
    campaign_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    name: str = Form(..., min_length=1, max_length=80),
    file: UploadFile = File(...),
) -> AtlasMapRead:
    if not await _access(db, campaign_id, user_id):
        raise HTTPException(status_code=403, detail="gm_only")
    clean = name.strip()
    if not clean:  # validated before any file is written
        raise HTTPException(status_code=422, detail="invalid_name")
    now = _now()
    m = CampaignMap(campaign_id=campaign_id, name=clean, image_path=await _save(campaign_id, file),
                    created_at=now, updated_at=now)
    db.add(m)
    await db.flush()
    return await _read(db, m, user_id)


@router.patch("/maps/{map_id}", response_model=AtlasMapRead)
async def rename_map(
    campaign_id: int, map_id: int, body: AtlasMapRename,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AtlasMapRead:
    m = await _gm_map(db, campaign_id, map_id, user_id)
    m.name, m.updated_at = body.name.strip(), _now()
    await db.flush()
    return await _read(db, m, user_id)


@router.put("/maps/{map_id}/image", response_model=AtlasMapRead)
async def replace_image(
    campaign_id: int, map_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(...),
) -> AtlasMapRead:
    m = await _gm_map(db, campaign_id, map_id, user_id)
    old, m.image_path = m.image_path, await _save(campaign_id, file)
    m.updated_at = _now()
    await db.flush()
    unlink_file(old)
    return await _read(db, m, user_id)


@router.post("/maps/{map_id}/reveal", response_model=AtlasMapRead)
async def reveal_map(
    campaign_id: int, map_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AtlasMapRead:
    m = await _gm_map(db, campaign_id, map_id, user_id)
    if m.revealed_at is None:
        m.revealed_at = m.updated_at = _now()
        session_id = await _active_session_id(db, campaign_id)
        if session_id is not None:
            _touch(await db.get(GameSession, session_id))
            db.add(SessionMessage(
                session_id=session_id, user_id=user_id, role=SessionRole.GAME_MASTER,
                body=f"Il master ha rivelato: {m.name}", sent_at=m.revealed_at,
                sender_display_name="__GM__",
                trade_payload=json.dumps(
                    {"kind": "atlas_reveal", "map_id": m.id, "marker_id": None, "title": m.name}),
            ))
        await db.flush()
    return await _read(db, m, user_id)


@router.post("/maps/{map_id}/hide", response_model=AtlasMapRead)
async def hide_map(
    campaign_id: int, map_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AtlasMapRead:
    m = await _gm_map(db, campaign_id, map_id, user_id)
    if m.revealed_at is not None:
        m.revealed_at, m.updated_at = None, _now()
        await db.flush()
    return await _read(db, m, user_id)


@router.delete("/maps/{map_id}", response_model=AtlasMapDeleted)
async def delete_map(
    campaign_id: int, map_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AtlasMapDeleted:
    m = await _gm_map(db, campaign_id, map_id, user_id)
    path = m.image_path
    # Explicit delete: SQLite FK cascades are not guaranteed on, and the count is in the response.
    removed = (await db.execute(delete(CampaignMapMarker).where(CampaignMapMarker.map_id == map_id))).rowcount
    await db.delete(m)
    await db.flush()
    unlink_file(path)
    return AtlasMapDeleted(deleted_markers=removed)


@router.get("/maps/{map_id}/image", response_model=None)
async def get_map_image(
    campaign_id: int, map_id: int, db: Annotated[AsyncSession, Depends(get_db)],
    x_telegram_init_data: str = Header("", alias="X-Telegram-Init-Data"),
    init_data: str = Query(""),
):
    # <img> cannot set headers: accept init_data as query param fallback.
    if DEV_USER_ID is not None:
        user_id = DEV_USER_ID
    else:
        raw = x_telegram_init_data or init_data
        if not raw:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing auth")
        user_id = verify_init_data(raw)
    is_gm = await _access(db, campaign_id, user_id)
    try:
        m = await _map(db, campaign_id, map_id, is_gm)
    except HTTPException:
        raise HTTPException(status_code=404, detail="file_not_found")
    path = Path(m.image_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="file_not_found")
    if not path.resolve().is_relative_to(svc.ATLAS_DIR.resolve()):
        raise HTTPException(status_code=400, detail="Invalid path")
    return FileResponse(path, media_type=_MEDIA.get(path.suffix.lower(), "application/octet-stream"))
